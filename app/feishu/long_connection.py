from __future__ import annotations

import argparse
from dataclasses import dataclass
from multiprocessing import Process

from app.feishu.config import get_feishu_bot_app_config_by_employee_id, get_feishu_bot_app_configs
from app.feishu.services import feishu_sdk_event_to_payload, get_feishu_surface_adapter_service


@dataclass
class FeishuLongConnectionBinding:
    employee_id: str
    app_id: str
    display_name: str


def build_long_connection_bindings() -> list[FeishuLongConnectionBinding]:
    bindings: list[FeishuLongConnectionBinding] = []
    for config in get_feishu_bot_app_configs():
        bindings.append(
            FeishuLongConnectionBinding(
                employee_id=config.employee_id,
                app_id=config.app_id,
                display_name=config.display_name or config.employee_id,
            )
        )
    return bindings


def run_long_connections(employee_ids: list[str] | None = None) -> None:
    selected_ids = set(employee_ids or [])
    try:
        import lark_oapi as lark
    except ModuleNotFoundError as exc:
        raise RuntimeError("lark-oapi 未安装，无法启动 Feishu 长连接。") from exc

    configs = [
        config
        for config in get_feishu_bot_app_configs()
        if not selected_ids or config.employee_id in selected_ids
    ]
    if not configs:
        raise RuntimeError("FEISHU_BOT_APPS_JSON 为空，无法启动 Feishu 长连接。")

    print("Starting Feishu long connections...")
    for config in configs:
        print(f" - {config.display_name or config.employee_id}: {config.app_id}")

    if len(configs) == 1:
        _run_single_connection(configs[0].employee_id)
        return

    processes: list[Process] = []
    for config in configs:
        process = Process(
            target=_run_single_connection,
            args=(config.employee_id,),
            name=f"feishu-long-conn-{config.employee_id}",
        )
        process.start()
        processes.append(process)

    for process in processes:
        process.join()


def _run_single_connection(employee_id: str) -> None:
    try:
        import lark_oapi as lark
    except ModuleNotFoundError as exc:
        raise RuntimeError("lark-oapi 未安装，无法启动 Feishu 长连接。") from exc

    config = get_feishu_bot_app_config_by_employee_id(employee_id)
    if config is None:
        raise RuntimeError(f"未找到 employee_id={employee_id} 的 Feishu bot 配置。")

    adapter = get_feishu_surface_adapter_service()
    verification_token = config.verification_token or ""
    encrypt_key = config.encrypt_key or ""

    def on_message(event, app_id=config.app_id):
        payload = feishu_sdk_event_to_payload(event)
        payload["header"] = {
            **(payload.get("header") or {}),
            "app_id": app_id,
        }
        adapter.handle_payload(payload)

    dispatcher = (
        lark.EventDispatcherHandler.builder(encrypt_key, verification_token)
        .register_p2_im_message_receive_v1(on_message)
        .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(lambda event: None)
        .register_p2_im_chat_member_bot_added_v1(lambda event: None)
        .register_p2_im_chat_updated_v1(lambda event: None)
        .build()
    )

    client = lark.ws.Client(
        config.app_id,
        config.app_secret,
        event_handler=dispatcher,
    )
    client.start()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Feishu long connection listeners for configured bot apps.")
    parser.add_argument(
        "employee_ids",
        nargs="*",
        help="Optional employee_id list. Omit to start all configured bots.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_long_connections(args.employee_ids)
