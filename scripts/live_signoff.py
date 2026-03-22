from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CORE_EMPLOYEE_IDS = [
    "chief-of-staff",
    "product-lead",
    "research-lead",
    "delivery-lead",
    "design-lead",
    "engineering-lead",
    "quality-lead",
]

REQUIRED_ROOM_POLICIES = {
    "room-executive",
    "room-review",
    "room-project",
    "room-launch",
    "room-ops",
    "room-support",
}

REQUIRED_BOOTSTRAP_FILES = {
    "BOOTSTRAP.md",
    "AGENTS.md",
    "IDENTITY.md",
    "SOUL.md",
    "SKILLS.md",
    "TOOLS.md",
    "HEARTBEAT.md",
    "USER.md",
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    payload: Any | None = None


@dataclass
class SignoffReport:
    base_url: str
    checks: list[CheckResult] = field(default_factory=list)
    recent_runs: list[dict[str, Any]] = field(default_factory=list)
    recent_group_debug: list[dict[str, Any]] = field(default_factory=list)
    manual_signoff_items: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "ok": self.ok,
            "checks": [
                {
                    "name": item.name,
                    "ok": item.ok,
                    "detail": item.detail,
                    "payload": item.payload,
                }
                for item in self.checks
            ],
            "recent_runs": self.recent_runs,
            "recent_group_debug": self.recent_group_debug,
            "manual_signoff_items": self.manual_signoff_items,
        }


def _fetch_json(base_url: str, path: str, *, method: str = "GET") -> Any:
    req = Request(f"{base_url.rstrip('/')}{path}", method=method)
    with urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _safe_fetch_json(base_url: str, path: str, *, method: str = "GET") -> tuple[bool, Any]:
    try:
        return True, _fetch_json(base_url, path, method=method)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return False, str(exc)


def _append(report: SignoffReport, name: str, ok: bool, detail: str, payload: Any | None = None) -> None:
    report.checks.append(CheckResult(name=name, ok=ok, detail=detail, payload=payload))


def _check_health(report: SignoffReport) -> None:
    ok, payload = _safe_fetch_json(report.base_url, "/health")
    if not ok:
        _append(report, "app_health", False, f"/health request failed: {payload}")
        return
    passed = payload.get("status") == "ok"
    _append(report, "app_health", passed, f"status={payload.get('status')}", payload)


def _check_gateway_health(report: SignoffReport) -> None:
    ok, payload = _safe_fetch_json(report.base_url, "/openclaw/gateway/health")
    if not ok:
        _append(report, "gateway_health", False, f"/openclaw/gateway/health failed: {payload}")
        return
    passed = payload.get("status") == "healthy"
    _append(report, "gateway_health", passed, f"status={payload.get('status')}", payload)


def _check_openclaw_agents(report: SignoffReport) -> None:
    ok, payload = _safe_fetch_json(report.base_url, "/openclaw/agents")
    if not ok:
        _append(report, "openclaw_agents", False, f"/openclaw/agents failed: {payload}")
        return
    employee_ids = [item["employee_id"] for item in payload]
    passed = employee_ids == CORE_EMPLOYEE_IDS
    _append(report, "openclaw_agents", passed, f"employees={employee_ids}", employee_ids)


def _check_feishu_bots(report: SignoffReport) -> None:
    ok, payload = _safe_fetch_json(report.base_url, "/feishu/bot-apps")
    if not ok:
        _append(report, "feishu_bots", False, f"/feishu/bot-apps failed: {payload}")
        return
    employee_ids = [item["employee_id"] for item in payload]
    passed = employee_ids == CORE_EMPLOYEE_IDS
    _append(report, "feishu_bots", passed, f"employees={employee_ids}", employee_ids)


def _check_room_policies(report: SignoffReport) -> None:
    ok, payload = _safe_fetch_json(report.base_url, "/conversations/room-policies")
    if not ok:
        _append(report, "room_policies", False, f"/conversations/room-policies failed: {payload}")
        return
    room_policy_ids = {item["room_policy_id"] for item in payload}
    missing = sorted(REQUIRED_ROOM_POLICIES - room_policy_ids)
    passed = not missing
    detail = "all required room policies present" if passed else f"missing={missing}"
    _append(report, "room_policies", passed, detail, sorted(room_policy_ids))


def _check_skill_catalog(report: SignoffReport) -> None:
    ok, payload = _safe_fetch_json(report.base_url, "/persona/skill-catalog/validate")
    if not ok:
        _append(report, "skill_catalog_validation", False, f"/persona/skill-catalog/validate failed: {payload}")
        return
    passed = payload.get("ok") is True
    issues = payload.get("issues") or []
    _append(report, "skill_catalog_validation", passed, f"issues={len(issues)}", payload)


def _check_provision_sync(report: SignoffReport) -> None:
    ok, payload = _safe_fetch_json(report.base_url, "/openclaw/provision/sync", method="POST")
    if not ok:
        _append(report, "provision_sync", False, f"/openclaw/provision/sync failed: {payload}")
        return
    passed = payload.get("workspace_count") == len(CORE_EMPLOYEE_IDS)
    detail = (
        f"workspace_count={payload.get('workspace_count')}, "
        f"generated_file_count={payload.get('generated_file_count')}"
    )
    _append(report, "provision_sync", passed, detail, payload)


def _check_agent_details(report: SignoffReport) -> None:
    failures: list[str] = []
    detail_rows: list[dict[str, Any]] = []
    for employee_id in CORE_EMPLOYEE_IDS:
        ok, payload = _safe_fetch_json(report.base_url, f"/openclaw/agents/{employee_id}/sync", method="POST")
        if not ok:
            failures.append(f"{employee_id}: sync failed: {payload}")
            continue
        workspace_files = {item["path"] for item in payload["workspace_files"]}
        native_skills = payload["native_skills"]
        ready_count = sum(1 for skill in native_skills if skill["verification_status"] == "ready")
        discovered_count = sum(1 for skill in native_skills if skill["discovered"])
        missing_files = sorted(REQUIRED_BOOTSTRAP_FILES - workspace_files)
        if missing_files:
            failures.append(f"{employee_id}: missing bootstrap files {missing_files}")
        if len(native_skills) < 40:
            failures.append(f"{employee_id}: native skill count={len(native_skills)}")
        if ready_count < 40:
            failures.append(f"{employee_id}: ready skill count={ready_count}")
        if discovered_count < 40:
            failures.append(f"{employee_id}: discovered skill count={discovered_count}")
        detail_rows.append(
            {
                "employee_id": employee_id,
                "workspace_file_count": len(workspace_files),
                "native_skill_count": len(native_skills),
                "ready_skill_count": ready_count,
                "discovered_skill_count": discovered_count,
            }
        )

    passed = not failures
    detail = "all core agents synced with 40 ready/discovered native skills" if passed else "; ".join(failures)
    _append(report, "agent_detail_sync", passed, detail, detail_rows)


def _collect_recent_runs(report: SignoffReport, limit: int) -> None:
    ok, payload = _safe_fetch_json(report.base_url, f"/openclaw/gateway/recent-runs?limit={limit}")
    if not ok:
        report.recent_runs = [{"error": str(payload)}]
        return
    report.recent_runs = [
        {
            "runtrace_id": item.get("runtrace_id"),
            "surface": item.get("surface"),
            "status": item.get("status"),
            "handoff_count": item.get("handoff_count"),
            "stop_reason": item.get("stop_reason"),
            "repeat_invocation_source": item.get("repeat_invocation_source"),
            "collaboration_intent": item.get("collaboration_intent"),
            "latest_handoff_targets": item.get("latest_handoff_targets"),
        }
        for item in payload
    ]


def _collect_group_debug(report: SignoffReport, limit: int) -> None:
    ok, payload = _safe_fetch_json(report.base_url, f"/feishu/group-debug-events?limit={limit}")
    if not ok:
        report.recent_group_debug = [{"error": str(payload)}]
        return
    report.recent_group_debug = [
        {
            "debug_event_id": item.get("debug_event_id"),
            "processed_status": item.get("processed_status"),
            "dispatch_targets": item.get("dispatch_targets"),
            "collaboration_intent": item.get("collaboration_intent"),
            "dispatch_resolution_basis": item.get("dispatch_resolution_basis"),
            "target_resolution_basis": item.get("target_resolution_basis"),
            "detail": item.get("detail"),
        }
        for item in payload
    ]


def build_report(base_url: str, *, run_limit: int, group_debug_limit: int) -> SignoffReport:
    report = SignoffReport(
        base_url=base_url,
        manual_signoff_items=[
            "在真实 Feishu 中点击 approved 卡片，确认 approval gate / checkpoint / work ticket 同步更新。",
            "在真实 Feishu 中点击 rejected 卡片，确认审批拒绝闭环正常。",
            "群聊发送“最后还是你来收口一下”，确认 repeat recall 命中并由目标 bot 再次回复。",
            "分别在 Launch Room / Ops Room / Support Room 做一条真实多 bot 协作消息，确认 transcript 与 room policy 联动正常。",
        ],
    )
    _check_health(report)
    _check_gateway_health(report)
    _check_openclaw_agents(report)
    _check_feishu_bots(report)
    _check_room_policies(report)
    _check_skill_catalog(report)
    _check_provision_sync(report)
    _check_agent_details(report)
    _collect_recent_runs(report, run_limit)
    _collect_group_debug(report, group_debug_limit)
    return report


def _print_report(report: SignoffReport) -> None:
    print("# OPC V1.5 Live Signoff")
    print()
    print(f"- base_url: `{report.base_url}`")
    print(f"- overall: `{'PASS' if report.ok else 'FAIL'}`")
    print()
    print("## Automated Checks")
    for item in report.checks:
        status = "PASS" if item.ok else "FAIL"
        print(f"- [{status}] `{item.name}`: {item.detail}")
    print()
    print("## Recent Runs")
    if not report.recent_runs:
        print("- none")
    for item in report.recent_runs:
        print(f"- {item}")
    print()
    print("## Recent Group Debug")
    if not report.recent_group_debug:
        print("- none")
    for item in report.recent_group_debug:
        print(f"- {item}")
    print()
    print("## Manual Signoff Items")
    for item in report.manual_signoff_items:
        print(f"- {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the final V1.5 live signoff checks against the local OPC API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1", help="API base URL, defaults to local app-dev.")
    parser.add_argument("--run-limit", type=int, default=8, help="Number of recent runs to print.")
    parser.add_argument("--group-debug-limit", type=int, default=8, help="Number of recent group debug items to print.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text.")
    args = parser.parse_args()

    report = build_report(args.base_url, run_limit=max(1, args.run_limit), group_debug_limit=max(1, args.group_debug_limit))
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
