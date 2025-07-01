import discord
from discord.ext import commands, tasks
import logging
import json
import os
import time
from datetime import datetime

# 导入共享的日志加载/保存函数
try:
    from ..mod.role_assigner_logic import _load_assignment_log
    import config
except ImportError:
    from cogs.mod.role_assigner_logic import _load_assignment_log
    import config

# 设置日志记录器
logger = logging.getLogger('discord_bot.cogs.tasks.user_role_formatter')
logger.setLevel(logging.DEBUG)

# 用户角色分配文件路径
USER_ROLE_ASSIGNMENTS_FILE = "data/user_role_assignments.json"

def _ensure_data_dir():
    """确保数据目录存在"""
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

def _save_user_role_assignments(data):
    """保存用户角色分配数据"""
    _ensure_data_dir()
    try:
        with open(USER_ROLE_ASSIGNMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.debug(f"已保存用户角色分配数据到 {USER_ROLE_ASSIGNMENTS_FILE}")
    except Exception as e:
        logger.error(f"保存用户角色分配数据时出错: {e}", exc_info=True)

def format_role_assignments():
    """将角色分配数据从以角色为中心转换为以用户为中心"""
    try:
        # 加载角色分配日志
        role_assignments = _load_assignment_log()
        if not isinstance(role_assignments, list):
            logger.error("角色分配日志格式不正确，应为列表")
            return {}

        # 创建以用户为中心的数据结构
        user_role_assignments = {}

        # 遍历所有操作
        for operation_entry in role_assignments:
            if not isinstance(operation_entry, list) or len(operation_entry) != 2:
                continue

            operation_id, details = operation_entry
            if not isinstance(details, dict) or 'data' not in details:
                continue

            assignment_details_list = details.get('data', [])
            if not isinstance(assignment_details_list, list):
                continue

            # 遍历每个服务器的分配详情
            for assignment in assignment_details_list:
                if not isinstance(assignment, dict):
                    continue

                guild_id = assignment.get('guild_id')
                role_ids = assignment.get('role_ids', [])
                assigned_user_ids = assignment.get('assigned_user_ids', [])

                if not all([guild_id, isinstance(role_ids, list), isinstance(assigned_user_ids, list)]):
                    continue

                # 为每个用户添加角色信息
                for user_id in assigned_user_ids:
                    user_id_str = str(user_id)
                    
                    # 如果用户不在字典中，初始化
                    if user_id_str not in user_role_assignments:
                        user_role_assignments[user_id_str] = {}
                    
                    # 如果服务器不在用户的字典中，初始化
                    guild_id_str = str(guild_id)
                    if guild_id_str not in user_role_assignments[user_id_str]:
                        user_role_assignments[user_id_str][guild_id_str] = []
                    
                    # 添加角色ID到用户的服务器角色列表中
                    for role_id in role_ids:
                        if role_id not in user_role_assignments[user_id_str][guild_id_str]:
                            user_role_assignments[user_id_str][guild_id_str].append(role_id)

        return user_role_assignments
    
    except Exception as e:
        logger.error(f"格式化角色分配数据时出错: {e}", exc_info=True)
        return {}

class UserRoleFormatter(commands.Cog):
    """
    将角色分配数据从以角色为中心转换为以用户为中心的定时任务
    """
    def __init__(self, bot):
        self.bot = bot
        self.format_user_roles.start()

    def cog_unload(self):
        self.format_user_roles.cancel()

    @tasks.loop(hours=1.0)
    async def format_user_roles(self):
        """定期将角色分配数据格式化为以用户为中心的结构"""
        logger.debug("开始格式化用户角色分配数据...")
        try:
            # 格式化角色分配数据
            user_role_assignments = format_role_assignments()
            
            # 保存格式化后的数据
            if user_role_assignments:
                _save_user_role_assignments(user_role_assignments)
                logger.info(f"已成功格式化 {len(user_role_assignments)} 个用户的角色分配数据")
            else:
                logger.warning("未找到有效的角色分配数据")
        
        except Exception as e:
            logger.error(f"格式化用户角色分配数据时出错: {e}", exc_info=True)

    @format_user_roles.before_loop
    async def before_format_user_roles(self):
        """在任务循环开始前等待机器人准备就绪"""
        await self.bot.wait_until_ready()

    @format_user_roles.error
    async def format_user_roles_error(self, error):
        """处理任务循环中的错误"""
        logger.error(f"任务错误: {error}", exc_info=True)

async def setup(bot):
    # 确保数据目录存在
    _ensure_data_dir()
    
    # 立即执行一次格式化
    user_role_assignments = format_role_assignments()
    if user_role_assignments:
        _save_user_role_assignments(user_role_assignments)
        logger.info(f"初始化时已格式化 {len(user_role_assignments)} 个用户的角色分配数据")
    
    # 添加Cog
    await bot.add_cog(UserRoleFormatter(bot))
