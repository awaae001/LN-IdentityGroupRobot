import discord
from discord.ext import commands
from discord import app_commands, Interaction
import logging
import config
from .mod.role_assigner_logic import handle_assign_roles

logger = logging.getLogger('discord_bot.cogs.role_assigner')


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
 
        # 检查是否拥有授权身份组 (从 config 读取)
        # 直接使用 config.AUTHORIZED_ROLE_IDS
        if config.AUTHORIZED_ROLE_IDS: 
            member = guild.get_member(interaction.user.id) # 获取成员对象以检查角色
            if member and member.roles:
                user_role_ids = {str(role.id) for role in member.roles} 
                # config.AUTHORIZED_ROLE_IDS 已经是列表，直接转换为集合
                authorized_role_ids_set = set(config.AUTHORIZED_ROLE_IDS) 
                if not user_role_ids.isdisjoint(authorized_role_ids_set): 
                    logger.debug(f"用户 {interaction.user.name} ({user_id_str}) 因拥有授权角色而通过权限检查。")
                    return True
            else: 
                logger.warning(f"无法获取用户 {interaction.user.name} ({user_id_str}) 的成员信息或角色列表。")


        # 如果两种检查都未通过
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


class RoleAssigner(commands.Cog):
    """包含与角色分配相关的命令的 Cog。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_id = config.GUILD_ID
        if self.guild_id is None:
            logger.error("GUILD_ID 未在配置中正确加载，RoleAssigner Cog 可能无法正常工作。")

    @app_commands.command(name="assign_roles", description="批量为用户分配身份组(可同时分配两个身份组)。")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        role_id_str="要分配的第一个身份组 ID",
        role_id_str_1="要分配的第二个身份组 ID (可选)",
        role_id_str_2="要分配的第三个身份组 ID (可选)",
        user_ids_str="用户 ID 列表 (可选, 如果提供了消息链接)",
        message_link="包含用户提及的消息链接 (可选)"
    )
    @is_authorized() # 应用新的自定义权限检查
    async def assign_roles(self, interaction: Interaction, role_id_str: str, role_id_str_1: str = None, role_id_str_2: str = None, user_ids_str: str = None, message_link: str = None):
        """
        批量为指定用户分配身份组 (Cog 版本，使用 ID)。
        可以从提供的用户 ID 字符串或消息链接中获取用户。
        """
        # 调用分离的逻辑处理函数
        await handle_assign_roles(interaction, role_id_str, user_ids_str, message_link, role_id_str_1, role_id_str_2)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        """处理 Cog 内应用程序命令的错误"""
        # 仅处理此 Cog 的命令错误
        if interaction.command is None or interaction.command.name != 'assign_roles':
             return

        # 特别处理 CheckFailure，因为 is_authorized 已经发送了消息
        if isinstance(error, app_commands.CheckFailure):
            logger.info(f"命令 /{interaction.command.name} 的权限检查失败，用户: {interaction.user.name} ({interaction.user.id})。已由 is_authorized 处理。")
            # 不需要再发送通用错误消息，因为 is_authorized 应该已经发送了具体的权限错误
            return

        # 处理其他类型的错误
        logger.error(f"Cog 'RoleAssigner' 中的命令 /{interaction.command.name} 发生错误: {error}", exc_info=True)
        error_message = "执行命令时发生未知错误。"

        if isinstance(error, app_commands.MissingPermissions):
            # 这个分支理论上不应该被触发，因为 is_authorized 覆盖了权限检查
            # 但保留以防万一
            error_message = '错误：你没有足够的权限来执行此命令。'
        elif isinstance(error, app_commands.CommandInvokeError):
            original_error = error.original
            error_message = f"命令执行中发生内部错误: {original_error}"
            # 可以在这里添加更具体的错误处理逻辑

        # 尝试发送错误消息（仅对非 CheckFailure 错误）
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
