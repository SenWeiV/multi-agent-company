from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.feishu.models import FeishuBotAppConfig


@lru_cache
def get_feishu_bot_app_configs() -> list[FeishuBotAppConfig]:
    raw = _resolve_bot_apps_json()
    if not raw:
        return []
    payload = json.loads(raw)
    return [FeishuBotAppConfig.model_validate(item) for item in payload]


def _resolve_bot_apps_json() -> str:
    raw = get_settings().feishu_bot_apps_json.strip()
    if raw and not _looks_like_placeholder(raw):
        return raw
    return _load_from_dotenv("FEISHU_BOT_APPS_JSON") or raw


def _looks_like_placeholder(raw: str) -> bool:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, list):
        return False
    for item in payload:
        if not isinstance(item, dict):
            continue
        values = [str(value) for value in item.values() if value is not None]
        if any("xxx" in value.lower() for value in values):
            return True
    return False


def _load_from_dotenv(name: str) -> str:
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.exists():
        return ""
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip() == name:
            return raw_value.strip().strip("'").strip('"')
    return ""


def get_feishu_bot_app_config_by_app_id(app_id: str) -> FeishuBotAppConfig | None:
    for config in get_feishu_bot_app_configs():
        if config.app_id == app_id:
            return config
    return None


def get_feishu_bot_app_config_by_employee_id(employee_id: str) -> FeishuBotAppConfig | None:
    for config in get_feishu_bot_app_configs():
        if config.employee_id == employee_id:
            return config
    return None
