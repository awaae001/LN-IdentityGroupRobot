import json
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger('discord_bot.cogs.remove_role_state')

STATE_FILE_PATH = os.path.join('data', 'remove_role_panels.json')

def _ensure_data_dir_exists():
    """确保 data 目录存在"""
    os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)

def save_panel_state(message_id: int, role_ids: List[int], persist_list: bool):
    """保存一个移除角色面板的状态"""
    _ensure_data_dir_exists()
    try:
        with open(STATE_FILE_PATH, 'r', encoding='utf-8') as f:
            all_panels = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_panels = {}

    all_panels[str(message_id)] = {
        'role_ids': role_ids,
        'persist_list': persist_list
    }

    with open(STATE_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_panels, f, indent=2, ensure_ascii=False)
    logger.info(f"已为消息 ID {message_id} 保存面板状态")

def load_panel_state(message_id: int) -> Optional[Dict]:
    """加载指定移除角色面板的状态"""
    try:
        with open(STATE_FILE_PATH, 'r', encoding='utf-8') as f:
            all_panels = json.load(f)
        return all_panels.get(str(message_id))
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def load_all_panel_states() -> Dict[str, Dict]:
    """加载所有移除角色面板的状态"""
    try:
        with open(STATE_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def remove_panel_state(message_id: int):
    """移除一个移除角色面板的状态"""
    _ensure_data_dir_exists()
    try:
        with open(STATE_FILE_PATH, 'r', encoding='utf-8') as f:
            all_panels = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    if str(message_id) in all_panels:
        del all_panels[str(message_id)]
        with open(STATE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_panels, f, indent=2, ensure_ascii=False)
        logger.info(f"已为消息 ID {message_id} 移除面板状态")