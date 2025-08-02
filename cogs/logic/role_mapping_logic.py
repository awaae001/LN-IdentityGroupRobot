import json
import os
import logging
from typing import Dict, Any, Optional, Tuple
from discord.ext import commands
import asyncio

logger = logging.getLogger(__name__)

class RoleMappingLogic(commands.Cog):
    """处理 role_mapping.json 数据交互的逻辑 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.file_path = 'data/role_mapping.json'
        self.lock = asyncio.Lock()
        self.mappings: Dict[str, Any] = {}
        self.load_mappings()

    def load_mappings(self):
        """从 JSON 文件加载角色映射"""
        if not os.path.exists(self.file_path):
            logger.warning(f"角色映射文件不存在: {self.file_path}，将创建一个空文件。")
            self.mappings = {}
            self.save_mappings()
            return

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.mappings = json.load(f)
            logger.info(f"成功从 {self.file_path} 加载角色映射。")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"加载角色映射文件 {self.file_path} 失败: {e}", exc_info=True)
            self.mappings = {}

    def save_mappings(self):
        """将当前角色映射保存到 JSON 文件"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.mappings, f, indent=4, ensure_ascii=False)
            logger.info(f"成功将角色映射保存到 {self.file_path}。")
        except IOError as e:
            logger.error(f"保存角色映射文件 {self.file_path} 失败: {e}", exc_info=True)

    async def add_role(self, group_id: str, role_id: str, role_name: str) -> Tuple[bool, str]:
        """
        向指定的映射组添加一个新的角色。

        Args:
            group_id (str): 映射组的 ID。
            role_id (str): 要添加的角色的 ID。
            role_name (str): 要添加的角色的名称。

        Returns:
            Tuple[bool, str]: 一个元组，包含操作是否成功和一条消息。
        """
        async with self.lock:
            if group_id not in self.mappings:
                return False, f"错误：找不到映射组 ID '{group_id}'。"
            
            group_data = self.mappings[group_id].get("data", {})
            if role_id in group_data:
                return False, f"错误：角色 ID '{role_id}' 已存在于该组中。"

            group_data[role_id] = role_name
            self.mappings[group_id]["data"] = group_data
            self.save_mappings()
            return True, f"成功将角色 '{role_name}' ({role_id}) 添加到组 '{self.mappings[group_id]['name']}'。"

    async def remove_role(self, group_id: str, role_id: str) -> Tuple[bool, str]:
        """
        从指定的映射组中移除一个角色。

        Args:
            group_id (str): 映射组的 ID。
            role_id (str): 要移除的角色的 ID。

        Returns:
            Tuple[bool, str]: 一个元组，包含操作是否成功和一条消息。
        """
        async with self.lock:
            if group_id not in self.mappings:
                return False, f"错误：找不到映射组 ID '{group_id}'。"

            group_data = self.mappings[group_id].get("data", {})
            if role_id not in group_data:
                return False, f"错误：角色 ID '{role_id}' 不在该组中。"

            removed_role_name = group_data.pop(role_id)
            self.mappings[group_id]["data"] = group_data
            self.save_mappings()
            return True, f"成功从组 '{self.mappings[group_id]['name']}' 中移除了角色 '{removed_role_name}' ({role_id})。"

    def get_all_group_ids(self) -> list:
        """获取所有映射组的 ID 和名称"""
        return [
            {"id": key, "name": value.get("name", "未命名组")}
            for key, value in self.mappings.items()
        ]

    def get_roles_in_group(self, group_id: str) -> list:
        """获取指定组内的所有角色 ID 和名称"""
        if group_id not in self.mappings:
            return []
        
        return [
            {"id": key, "name": value}
            for key, value in self.mappings[group_id].get("data", {}).items()
        ]

async def setup(bot: commands.Bot):
    """异步 setup 函数，用于加载 Cog"""
    # 这个 Cog 主要是为了被其他 Cog 调用，所以我们只添加实例
    # 如果需要它独立运行或监听事件，可以在这里添加
    await bot.add_cog(RoleMappingLogic(bot))
    logger.info("RoleMappingLogic Cog 已成功加载。")