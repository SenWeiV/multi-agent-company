from __future__ import annotations

import argparse

from app.skills.services import sync_skill_repositories


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync GitHub-backed skill sources into third_party/skills.")
    parser.add_argument("--repo", default="", help="Reserved for future selective sync; current implementation syncs all locked repos.")
    parser.parse_args()
    synced = sync_skill_repositories()
    print(f"synced {len(synced)} skill source files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
