import discord
from discord.ext import commands
from discord import app_commands, Interaction
from typing import TYPE_CHECKING
import logging
import config
import os
from .mod.role_assigner_logic import handle_assign_roles
if TYPE_CHECKING:
    from .logic.role_distributor_logic import RoleDistributorLogic
from .mod import status_utils 
from .mod.role_members_logic import handle_list_role_members
from .mod.role_sync_logic import handle_sync_role
from utils.auth_utils import is_authorized
from .mod.remove_role_logic import handle_remove_role
from .ui.identity_group_view import IdentityGroupView
from .ui.role_distributor_view import RoleDistributorView
from .ui.role_auto_apply_view import RoleAutoApplyView, ApplyModal
from .logic.role_mapping_logic import RoleMappingLogic
from typing import List

logger = logging.getLogger('discord_bot.cogs.role_assigner')


def get_cog_names():
    """Dynamically gets all cog names from the cogs directory."""
    cog_names = []
    cogs_root_dir = os.path.join(os.path.dirname(__file__), '..', 'cogs')
    for root, dirs, files in os.walk(cogs_root_dir):
        # Exclude __pycache__ directories
        dirs[:] = [d for d in dirs if not d.startswith('__')]
        for filename in files:
            if filename.endswith('.py') and not filename.startswith('_'):
                # Construct the module name from the file path
                relative_path = os.path.relpath(os.path.join(root, filename), os.path.join(cogs_root_dir, '..'))
                module_name_parts = relative_path[:-3].split(os.sep)
                cog_name = '.'.join(module_name_parts)
                cog_names.append(cog_name)
    return cog_names

class RoleAssigner(commands.Cog):
    """包含与角色分配相关的命令的 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_id = config.GUILD_ID
        if self.guild_id is None:
            logger.error("GUILD_ID 未在配置中正确加载，RoleAssigner Cog 可能无法正常工作")

    async def handle_create_role_distributor(self, interaction: Interaction, channel: discord.TextChannel, role: discord.Role, title: str, content: str, name: str):
        """处理创建或更新身份组分发器的逻辑"""
        await interaction.response.defer(ephemeral=True)
        
        logic_cog: "RoleDistributorLogic" = self.bot.get_cog("RoleDistributorLogic")
        if not logic_cog:
            await interaction.followup.send("错误：RoleDistributorLogic 未加载", ephemeral=True)
            return

        try:
            # 准备嵌入消息
            embed = discord.Embed(title=title, description=content, color=discord.Color.blue())
            if interaction.guild.icon:
                embed.set_author(name=name, icon_url=interaction.guild.icon.url)
            else:
                embed.set_author(name=name)
            
            view = RoleDistributorView()
            
            # 发送消息
            message = await channel.send(embed=embed, view=view)
            
            # 更新或创建配置
            channel_id_str = str(channel.id)
            logic_cog.distributors[channel_id_str] = {
                "message_id": message.id,
                "role_id": role.id,
                "title": title,
                "content": content,
                "name": name
            }
            logic_cog.save_distributors()
            
            await interaction.followup.send(f"✅ 成功在 {channel.mention} 创建了身份组分发器", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ 错误：机器人没有权限在该频道发送消息", ephemeral=True)
        except Exception as e:
            logger.error(f"创建身份组分发器时出错: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 创建过程中发生未知错误: {e}", ephemeral=True)

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

    @app_commands.command(name="assign_roles", description="批量为用户分配身份组(可同时分配两个身份组)")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        role_id_str="第一个要分配的身份组ID",
        role_id_str_1="第二个要分配的身份组ID (可选)",
        role_id_str_2="第三个要分配的身份组ID (可选)",
        user_ids_str="用户ID列表，多个ID用逗号分隔 (可选)",
        message_link="包含@用户的消息链接 (可选)",
        operation_id="要补充人员的操作ID (可选, 提供此项时将忽略上方填写的身份组)",
        fade_flag="处理标记(可选): true/1 表示跳过自动褪色，false/0 或不填为默认",
        time="过期时间(天数，可选): 默认为90天"
    )
    @is_authorized()
    async def assign_roles(self, interaction: Interaction, role_id_str: str = None, role_id_str_1: str = None, role_id_str_2: str = None, user_ids_str: str = None, message_link: str = None, operation_id: str = None, fade_flag: str = None, time: int = None):
        fade = False
        if fade_flag is not None and str(fade_flag).lower() in ("true", "1", "yes", "y"):
            fade = True

        await handle_assign_roles(interaction, role_id_str, user_ids_str, message_link, role_id_str_1, role_id_str_2, fade=fade, time=time, operation_id=operation_id)

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
        比对两个服务器的身份组成员差异并进行同步
        """
        logger.info(f"开始处理 /sync_role 命令，参数: role_id_1={role_id_1}, server_id={server_id}, role_id_2={role_id_2}, action={action}")
        await handle_sync_role(interaction, role_id_1, server_id, role_id_2, action)

    @app_commands.command(name="create_role_distributor", description="在指定频道创建或更新一个身份组分发消息")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        channel="要发送消息的频道",
        role="要分发的身份组",
        title="嵌入消息的标题",
        content="嵌入消息的内容",
        name="机器人显示的名称"
    )
    @is_authorized()
    async def create_role_distributor(self, interaction: Interaction, channel: discord.TextChannel, role: discord.Role, title: str, content: str, name: str):
        """在指定频道创建或更新一个身份组分发消息"""
        await self.handle_create_role_distributor(interaction, channel, role, title, content, name)

    @app_commands.command(name="delete_role_distributor", description="删除一个已配置的身份组分发器")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(channel="要删除分发器的频道")
    @is_authorized()
    async def delete_role_distributor(self, interaction: Interaction, channel: str):
        """删除指定频道的身份组分发器"""
        await interaction.response.defer(ephemeral=True)
        
        logic_cog: "RoleDistributorLogic" = self.bot.get_cog("RoleDistributorLogic")
        if not logic_cog:
            await interaction.followup.send("错误：RoleDistributorLogic 未加载", ephemeral=True)
            return
        
        try:
            channel_id = int(channel)
            channel_obj = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not isinstance(channel_obj, discord.TextChannel):
                await interaction.followup.send("错误：提供的ID不是一个有效的文字频道", ephemeral=True)
                return
        except (ValueError, discord.NotFound, discord.Forbidden):
            await interaction.followup.send("错误：找不到提供的频道ID", ephemeral=True)
            return

        if await logic_cog.delete_distributor(channel_obj):
            await interaction.followup.send(f"✅ 成功删除了频道 {channel_obj.mention} 的身份组分发器", ephemeral=True)
        else:
            await interaction.followup.send(f"ℹ️ 频道 {channel_obj.mention} 中没有找到需要删除的身份组分发器", ephemeral=True)

    @delete_role_distributor.autocomplete('channel')
    async def delete_role_distributor_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        """为删除命令提供已配置频道的自动完成"""
        logic_cog: "RoleDistributorLogic" = self.bot.get_cog("RoleDistributorLogic")
        if not logic_cog:
            return []
            
        choices = []
        for channel_id_str in logic_cog.distributors.keys():
            channel = self.bot.get_channel(int(channel_id_str))
            if channel and (not current or current.lower() in channel.name.lower()):
                choices.append(app_commands.Choice(name=f"#{channel.name}", value=channel_id_str))
        
        return choices
    @app_commands.command(name="identity_group_manager", description="唤出管理身份组面板")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @is_authorized()
    async def identity_group_manager(self, interaction: Interaction):
        """
        显示一个身份组管理器，允许用户管理自己的身份组
        优先尝试在当前频道发送面板，如果无权限则回退为向用户发送临时消息
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 检查Cog是否加载
        if not self.bot.get_cog("IdentityGroupLogic"):
            logger.error("IdentityGroupLogic cog not loaded.")
            await interaction.followup.send("身份组管理功能当前不可用，请联系管理员", ephemeral=True)
            return

        view = IdentityGroupView()
        embed = discord.Embed(
            title="🆔 杯赛身份组管理器",
            description="欢迎使用杯赛身份组管理器！\n\n请点击下方按钮来佩戴或移除您的身份组",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text="请选择您要执行的操作")

        try:
            # 尝试在频道中直接发送消息
            await interaction.channel.send(embed=embed, view=view)
            await interaction.followup.send("✅ 管理面板已发送至当前频道", ephemeral=True)
        except discord.Forbidden:
            # 如果没有权限，则作为临时消息发送给用户
            logger.warning(f"无法在频道 {interaction.channel.name} ({interaction.channel.id}) 中发送身份组管理器，回退到临时消息")
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"发送身份组管理器时发生未知错误: {e}", exc_info=True)
            await interaction.followup.send("发送管理面板时发生未知错误，请联系管理员", ephemeral=True)

    @app_commands.command(name="reload", description="重载指定的机器人模块 (Cog)")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(cog_name="要重载的模块名称")
    @is_authorized()
    async def reload_cog(self, interaction: Interaction, cog_name: str):
        """重载指定的机器人模块 (Cog)"""
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.reload_extension(cog_name)
            logger.info(f"模块 {cog_name} 已由 {interaction.user.name} 重载")
            embed = discord.Embed(
                title="✅ 重载成功",
                description=f"模块 **{cog_name}** 已成功重载",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        except commands.ExtensionNotLoaded:
            embed = discord.Embed(
                title="❌ 重载失败",
                description=f"模块 **{cog_name}** 从未被加载过",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
        except commands.ExtensionNotFound:
            embed = discord.Embed(
                title="❌ 重载失败",
                description=f"找不到模块 **{cog_name}**",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"重载模块 {cog_name} 时发生错误: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ 重载失败",
                description=f"重载模块 **{cog_name}** 时发生未知错误\n```\n{e}\n```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

    @reload_cog.autocomplete('cog_name')
    async def reload_cog_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocompletes the cog_name parameter for the reload command."""
        cog_names = get_cog_names()
        return [
            app_commands.Choice(name=cog, value=cog)
            for cog in cog_names if current.lower() in cog.lower()
        ]

    @app_commands.command(name="role_auto_apply", description="创建一个自动申请身份组的嵌入式消息")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        space="选择一个论坛频道作为申请的作用域",
        role_id="输入当用户满足条件时给予的身份组ID",
        count="输入帖子需要达到的最高反应数"
    )
    @is_authorized()
    async def role_auto_apply(self, interaction: discord.Interaction, space: discord.ForumChannel, role_id: str, count: int):
        try:
            role_id_int = int(role_id)
        except ValueError:
            await interaction.response.send_message("身份组ID必须是一个有效的数字", ephemeral=True)
            return

        role = interaction.guild.get_role(role_id_int)
        if role is None:
            await interaction.response.send_message(f"找不到 ID 为 {role_id_int} 的身份组", ephemeral=True)
            return

        embed = discord.Embed(
            title="身份组自动申请",
            description=f"点击下方的按钮，按照提示输入你的帖子链接即可申请 **{role.name}** 身份组\n\n"
                        f"**申请条件:**\n"
                        f"- 帖子必须发布在 {space.mention} 频道\n"
                        f"- 你必须是帖子的作者\n"
                        f"- 帖子的最高反应数需要达到 **{count}** 个。",
            color=discord.Color.blue()
        )
        
        view = RoleAutoApplyView()
        # Get the button and set its dynamic custom_id
        button = view.children[0]
        button.custom_id = f"role_auto_apply:{role_id_int}:{count}:{space.id}"
        
        await interaction.response.send_message(embed=embed, view=view)

    @commands.Cog.listener("on_interaction")
    async def on_auto_apply_interaction(self, interaction: Interaction):
        if not interaction.data or 'custom_id' not in interaction.data:
            return

        custom_id = interaction.data['custom_id']
        if not custom_id.startswith("role_auto_apply:"):
            return

        try:
            _, role_id_str, reactions_str, forum_id_str = custom_id.split(':')
            role_id = int(role_id_str)
            required_reactions = int(reactions_str)
            forum_channel_id = int(forum_id_str)
            
            modal = ApplyModal(
                role_id=role_id,
                required_reactions=required_reactions,
                forum_channel_id=forum_channel_id
            )
            await interaction.response.send_modal(modal)
        
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing auto_apply custom_id '{custom_id}': {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("处理申请时发生内部错误，按钮数据格式无效。", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        """处理 Cog 内应用程序命令的错误"""
        # 仅处理此 Cog 的命令错误
        if interaction.command is None or interaction.command.name != 'assign_roles':
             return

        
        if isinstance(error, app_commands.CheckFailure):
            logger.info(f"命令 /{interaction.command.name} 的权限检查失败，用户: {interaction.user.name} ({interaction.user.id})已由 is_authorized 处理")
            return
        
        logger.error(f"Cog 'RoleAssigner' 中的命令 /{interaction.command.name} 发生错误: {error}", exc_info=True)
        error_message = "执行命令时发生未知错误"

        if isinstance(error, app_commands.MissingPermissions):
            error_message = '错误：你没有足够的权限来执行此命令'
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


    async def group_id_autocomplete(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """为 group_id 提供自动完成选项"""
        logic_cog: RoleMappingLogic = self.bot.get_cog("RoleMappingLogic")
        if not logic_cog:
            return []
        
        groups = logic_cog.get_all_group_ids()
        return [
            app_commands.Choice(name=f"{group['name']} ({group['id']})", value=group['id'])
            for group in groups if current.lower() in group['name'].lower() or current in group['id']
        ][:25]

    async def role_id_autocomplete(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """根据选择的 group_id 为 role_id 提供自动完成选项"""
        group_id = interaction.namespace.group_id
        if not group_id:
            return []

        logic_cog: RoleMappingLogic = self.bot.get_cog("RoleMappingLogic")
        if not logic_cog:
            return []

        roles = logic_cog.get_roles_in_group(group_id)
        return [
            app_commands.Choice(name=f"{role['name']} ({role['id']})", value=role['id'])
            for role in roles if current.lower() in role['name'].lower() or current in role['id']
        ][:25]

    @app_commands.command(name="manage_role", description="管理角色映射文件")
    @app_commands.guilds(*[discord.Object(id=gid) for gid in config.GUILD_IDS])
    @app_commands.describe(
        action="选择要执行的操作 (添加或删除)",
        group_id="目标组的ID",
        role_id="目标角色的ID",
        role_name="要添加的角色的名称 (仅在添加时需要)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="添加 (add)", value="add"),
        app_commands.Choice(name="删除 (remove)", value="remove"),
    ])
    @app_commands.autocomplete(group_id=group_id_autocomplete, role_id=role_id_autocomplete)
    @is_authorized()
    async def manage_role(self, interaction: Interaction, action: str, group_id: str, role_id: str, role_name: str = None):
        """处理角色映射的添加和删除"""
        await interaction.response.defer(ephemeral=True)

        logic_cog: RoleMappingLogic = self.bot.get_cog("RoleMappingLogic")
        if not logic_cog:
            await interaction.followup.send("错误: RoleMappingLogic 未加载。", ephemeral=True)
            return

        if action == "add":
            if not role_name:
                await interaction.followup.send("错误: 添加操作需要提供 `role_name`。", ephemeral=True)
                return
            success, message = await logic_cog.add_role(group_id, role_id, role_name)
            title = "添加角色映射"
        elif action == "remove":
            success, message = await logic_cog.remove_role(group_id, role_id)
            title = "移除角色映射"
        else:
            await interaction.followup.send("错误: 无效的操作。", ephemeral=True)
            return

        color = discord.Color.green() if success else discord.Color.red()
        embed = discord.Embed(title=title, description=message, color=color)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """异步 setup 函数，用于加载 Cog"""
    if not config.GUILD_IDS:
        logger.critical("无法加载 RoleAssigner Cog，因为 GUILD_IDS 未配置")
        return

    await bot.add_cog(RoleAssigner(bot), guilds=[discord.Object(id=gid) for gid in config.GUILD_IDS])
    logger.info("RoleAssigner Cog 已成功加载")

