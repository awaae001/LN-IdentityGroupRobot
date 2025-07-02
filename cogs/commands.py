import discord
from discord.ext import commands
from discord import app_commands, Interaction
import logging
import config
from .mod.role_assigner_logic import handle_assign_roles
from .mod import status_utils 
from .mod.role_members_logic import handle_list_role_members
from .mod.role_sync_logic import handle_sync_role
from utils.auth_utils import is_authorized
from .mod.remove_role_logic import handle_remove_role
from .ui.identity_group_view import IdentityGroupView

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
        message_link="包含@用户的消息链接 (可选)",
        fade_flag="处理标记(可选): true/1 表示跳过自动褪色，false/0 或不填为默认",
        time="过期时间(天数，可选): 默认为90天"
    )
    @is_authorized() 
    async def assign_roles(self, interaction: Interaction, role_id_str: str, role_id_str_1: str = None, role_id_str_2: str = None, user_ids_str: str = None, message_link: str = None, fade_flag: str = None, time: int = None):
        fade = False
        if fade_flag is not None and str(fade_flag).lower() in ("true", "1", "yes", "y"):
            fade = True

        await handle_assign_roles(interaction, role_id_str, user_ids_str, message_link, role_id_str_1, role_id_str_2, fade=fade, time=time)

    @app_commands.command(name="status", description="显示系统和机器人状态")
    async def status_command(self, interaction: discord.Interaction):
        """显示系统和机器人状态"""
        await status_utils.handle_status_command(interaction, self.bot)

    @app_commands.command(name="remov_role", description="创建一个带下拉选单的嵌入消息，用户可自助移除指定的身份组")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        role_ids_str="要移除的身份组ID列表，多个ID用逗号分隔",
        persist_list="是否启用退出人员列表持久化 (默认关闭)"
    )
    @is_authorized()
    async def remov_role(self, interaction: Interaction, role_ids_str: str, persist_list: bool = False):
        """管理员创建嵌入消息，用户通过下拉选单可自助移除指定身份组"""
        await handle_remove_role(interaction, role_ids_str, persist_list)

    @app_commands.command(name="sync_role", description="手动同步两个服务器的身份组成员")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        role_id_1="本服务器的身份组ID",
        server_id="远端服务器的ID",
        role_id_2="远端服务器的身份组ID",
        action="选择同步操作"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="双向同步 (默认)", value="bidirectional"),
        app_commands.Choice(name="仅推送到远端", value="push"),
        app_commands.Choice(name="仅同步到本地", value="pull"),
        app_commands.Choice(name="移除本地同步身份组", value="remove_local"),
    ])
    @is_authorized()
    async def sync_role(self, interaction: Interaction, role_id_1: str, server_id: str, role_id_2: str, action: str = "bidirectional"):
        """
        比对两个服务器的身份组成员差异并进行同步。
        """
        logger.info(f"开始处理 /sync_role 命令，参数: role_id_1={role_id_1}, server_id={server_id}, role_id_2={role_id_2}, action={action}")
        await handle_sync_role(interaction, role_id_1, server_id, role_id_2, action)
        
    @app_commands.command(name="identity_group_manager", description="唤出管理身份组面板")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @is_authorized()
    async def identity_group_manager(self, interaction: Interaction):
        """
        显示一个身份组管理器，允许用户管理自己的身份组。
        优先尝试在当前频道发送面板，如果无权限则回退为向用户发送临时消息。
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        view = IdentityGroupView()
        embed = discord.Embed(
            title="🆔 杯赛身份组管理器",
            description="欢迎使用杯赛身份组管理器！\n\n请点击下方按钮来佩戴或移除您的身份组。",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text="请选择您要执行的操作。")

        try:
            # 尝试在频道中直接发送消息
            await interaction.channel.send(embed=embed, view=view)
            await interaction.followup.send("✅ 管理面板已发送至当前频道。", ephemeral=True)
        except discord.Forbidden:
            # 如果没有权限，则作为临时消息发送给用户
            logger.warning(f"无法在频道 {interaction.channel.name} ({interaction.channel.id}) 中发送身份组管理器，回退到临时消息。")
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"发送身份组管理器时发生未知错误: {e}", exc_info=True)
            await interaction.followup.send("发送管理面板时发生未知错误，请联系管理员。", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        """处理 Cog 内应用程序命令的错误"""
        # 仅处理此 Cog 的命令错误
        if interaction.command is None or interaction.command.name != 'assign_roles':
             return

        
        if isinstance(error, app_commands.CheckFailure):
            logger.info(f"命令 /{interaction.command.name} 的权限检查失败，用户: {interaction.user.name} ({interaction.user.id})。已由 is_authorized 处理。")
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
