import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def _is_npm_network_error(output: str) -> bool:
    normalized = output.lower()
    return any(
        marker in normalized
        for marker in (
            "econreset",
            "network",
            "eai_again",
            "etimedout",
            "client network socket disconnected",
            "before secure tls connection was established",
        )
    )


def test_dashboard_frontend_build_smoke() -> None:
    npm = shutil.which("npm")
    assert npm is not None, "npm is required for dashboard frontend build"

    repo_root = Path(__file__).resolve().parents[1]
    dashboard_dir = repo_root / "dashboard-web"

    # Build in a clean temp copy so containerized Linux runs don't reuse host
    # node_modules with incompatible native optional bindings.
    with tempfile.TemporaryDirectory() as tmp_dir:
        sandbox_dir = Path(tmp_dir) / "dashboard-web"
        shutil.copytree(
            dashboard_dir,
            sandbox_dir,
            ignore=shutil.ignore_patterns(
                "node_modules",
                "dist",
                "playwright-report",
                "test-results",
            ),
        )

        used_local_node_modules_fallback = False
        install = subprocess.run(
            [npm, "ci", "--include=optional", "--no-fund", "--no-audit"],
            cwd=sandbox_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        install_output = install.stderr or install.stdout
        if install.returncode != 0:
            source_node_modules = dashboard_dir / "node_modules"
            if _is_npm_network_error(install_output) and source_node_modules.exists():
                shutil.copytree(source_node_modules, sandbox_dir / "node_modules", dirs_exist_ok=True)
                used_local_node_modules_fallback = True
            elif _is_npm_network_error(install_output):
                pytest.skip("npm registry unavailable during isolated frontend install")
            else:
                raise AssertionError(install_output)

        result = subprocess.run(
            [npm, "run", "build"],
            cwd=sandbox_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 and used_local_node_modules_fallback:
            pytest.skip("isolated npm install unavailable and local node_modules are not portable in this environment")

    assert result.returncode == 0, result.stderr or result.stdout
