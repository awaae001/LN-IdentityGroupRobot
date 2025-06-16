import discord
from discord.ext import commands
from discord import app_commands, Interaction
import logging
import config
from .mod.role_assigner_logic import handle_assign_roles
from .mod import status_utils 
from .mod.role_members_logic import handle_list_role_members
from utils.auth_utils import is_authorized

logger = logging.getLogger('discord_bot.cogs.role_assigner')


class RoleAssigner(commands.Cog):
    """包含与角色分配相关的命令的 Cog。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_id = config.GUILD_ID
        if self.guild_id is None:
            logger.error("GUILD_ID 未在配置中正确加载，RoleAssigner Cog 可能无法正常工作。")

    @app_commands.command(name="list_role_members", description="查找某个身份组下的全部成员并可进行批量操作")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        role_id_str="要查询的身份组ID"
    )
    @is_authorized()
    async def list_role_members(self, interaction: Interaction, role_id_str: str):
        """
        查找某个身份组下的全部成员，并通过选单选择后续操作
        """
        await handle_list_role_members(interaction, role_id_str)

    @app_commands.command(name="assign_roles", description="批量为用户分配身份组(可同时分配两个身份组)。")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        role_id_str="第一个要分配的身份组ID",
        role_id_str_1="第二个要分配的身份组ID (可选)",
        role_id_str_2="第三个要分配的身份组ID (可选)", 
        user_ids_str="用户ID列表，多个ID用逗号分隔 (可选)",
        message_link="包含@用户的消息链接 (可选)"
    )
    @is_authorized() 
    async def assign_roles(self, interaction: Interaction, role_id_str: str, role_id_str_1: str = None, role_id_str_2: str = None, user_ids_str: str = None, message_link: str = None):

        await handle_assign_roles(interaction, role_id_str, user_ids_str, message_link, role_id_str_1, role_id_str_2)

    @app_commands.command(name="status", description="显示系统和机器人状态")
    async def status_command(self, interaction: discord.Interaction):
        """显示系统和机器人状态"""
        await status_utils.handle_status_command(interaction, self.bot)
        
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        """处理 Cog 内应用程序命令的错误"""
        # 仅处理此 Cog 的命令错误
        if interaction.command is None or interaction.command.name != 'assign_roles':
             return

        
        if isinstance(error, app_commands.CheckFailure):
            logger.info(f"命令 /{interaction.command.name} 的权限检查失败，用户: {interaction.user.name} ({interaction.user.id})。已由 is_authorized 处理。")
            # 不需要再发送通用错误消息，因为 is_authorized 应该已经发送了具体的权限错误
            return
        
        logger.error(f"Cog 'RoleAssigner' 中的命令 /{interaction.command.name} 发生错误: {error}", exc_info=True)
        error_message = "执行命令时发生未知错误。"

        if isinstance(error, app_commands.MissingPermissions):
            error_message = '错误：你没有足够的权限来执行此命令。'
        elif isinstance(error, app_commands.CommandInvokeError):
            original_error = error.original
            error_message = f"命令执行中发生内部错误: {original_error}"

        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except discord.InteractionResponded:
            try:
                await interaction.followup.send(error_message, ephemeral=True)
            except Exception as e_followup:
                logger.error(f"尝试发送后续错误消息失败，交互已响应: {e_followup}")
        except Exception as e_send:
            logger.error(f"发送错误消息时发生意外错误: {e_send}")


async def setup(bot: commands.Bot):
    """异步 setup 函数，用于加载 Cog。"""
    if not config.GUILD_IDS:
        logger.critical("无法加载 RoleAssigner Cog，因为 GUILD_IDS 未配置。")
        return

    await bot.add_cog(RoleAssigner(bot), guilds=[discord.Object(id=gid) for gid in config.GUILD_IDS])
    logger.info("RoleAssigner Cog 已成功加载。")
