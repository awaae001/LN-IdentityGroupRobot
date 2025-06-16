import discord
import logging
from discord import Interaction, app_commands
import config

logger = logging.getLogger('discord_bot.cogs.auth_utils')

def is_authorized():
    """自定义检查，验证用户是否有权执行命令。"""
    async def predicate(interaction: Interaction) -> bool:
        user_id_str = str(interaction.user.id)
        guild = interaction.guild
        # 确保在服务器环境内执行
        if not guild:
             logger.warning(f"命令 /{interaction.command.name} 尝试在非服务器环境（可能是 DM）中执行，用户: {interaction.user.name} ({user_id_str})")
             # 可以在这里发送消息或直接返回 False
             message = "❌ 此命令只能在服务器内使用。"
             try:
                 if not interaction.response.is_done():
                     await interaction.response.send_message(message, ephemeral=True)
                 else:
                     await interaction.followup.send(message, ephemeral=True)
             except Exception as e:
                 logger.error(f"发送 '仅限服务器' 错误消息失败: {e}")
             return False
 
         
        if config.ADMIN_USER_IDS and user_id_str in config.ADMIN_USER_IDS:
            logger.debug(f"管理员用户 {interaction.user.name} ({user_id_str}) 通过权限检查。")
            return True
 
        if config.AUTHORIZED_ROLE_IDS: 
            member = guild.get_member(interaction.user.id) # 获取成员对象以检查角色
            if member and member.roles:
                user_role_ids = {str(role.id) for role in member.roles} 
                authorized_role_ids_set = set(config.AUTHORIZED_ROLE_IDS) 
                if not user_role_ids.isdisjoint(authorized_role_ids_set): 
                    logger.debug(f"用户 {interaction.user.name} ({user_id_str}) 因拥有授权角色而通过权限检查。")
                    return True
            else: 
                logger.warning(f"无法获取用户 {interaction.user.name} ({user_id_str}) 的成员信息或角色列表。")


        logger.warning(f"未授权用户 {interaction.user.name} ({user_id_str}) 尝试使用命令 /{interaction.command.name}")
        message = "❌ 抱歉，你没有使用此命令的权限。"
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(message, ephemeral=True)
            else:
                # 避免重复响应
                logger.warning(f"交互已响应，无法向用户 {interaction.user.name} 发送权限错误消息。")
        except discord.InteractionResponded:
             try:
                 await interaction.followup.send(message, ephemeral=True)
             except Exception as e:
                 logger.error(f"尝试发送后续权限错误消息失败: {e}")
        except Exception as e:
            logger.error(f"发送权限错误消息时发生意外错误: {e}")
        return False
    return app_commands.check(predicate)
