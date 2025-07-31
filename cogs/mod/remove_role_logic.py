import discord
import os
import json
import logging
from discord import Interaction, SelectOption
from discord.ui import Select, View
from .remove_role_state import save_panel_state, load_panel_state

logger = logging.getLogger('discord_bot.cogs.remove_role')

class RemoveRoleSelectView(View):
    def __init__(self, roles: list[discord.Role], persist_list: bool = False, custom_id_suffix: str = ""):
        super().__init__(timeout=None)
        self.roles = roles
        self.persist_list = persist_list
        
        # 构建唯一的 custom_id
        # 基础 ID: "remove_role_select"
        # 后缀: 通常是消息 ID，例如 ":1234567890"
        # 最终 custom_id: "remove_role_select:1234567890"
        base_custom_id = "remove_role_select"
        final_custom_id = f"{base_custom_id}{custom_id_suffix}"

        options = [
            SelectOption(label=getattr(role, 'name', f'ID: {role.id}'), value=str(role.id), description=f"点击移除身份组: {getattr(role, 'name', f'ID: {role.id}')}")
            for role in self.roles
        ]
        
        select = Select(
            placeholder="请选择要移除的身份组...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=final_custom_id
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: Interaction):
        # 从交互中获取消息 ID
        message_id = interaction.message.id
        
        # 加载此面板的状态
        panel_state = load_panel_state(message_id)
        if not panel_state:
            await interaction.response.send_message("错误：找不到此面板的状态信息，可能已被删除或已过期。", ephemeral=True)
            logger.warning(f"无法为消息 ID {message_id} 加载面板状态。")
            return

        persist_list = panel_state.get('persist_list', False)
        
        selected_role_id = int(interaction.data['values'][0])
        guild = interaction.guild
        role = guild.get_role(selected_role_id)
        member = interaction.user

        if not role:
            await interaction.response.send_message("选择的身份组不存在或已被删除", ephemeral=True)
            return

        # 确认所选角色是否是此面板的一部分
        if role.id not in panel_state.get('role_ids', []):
            await interaction.response.send_message("错误：无效的选择。", ephemeral=True)
            logger.warning(f"用户 {member.name} 尝试从未经授权的面板 (msg_id: {message_id}) 移除角色 (role_id: {role.id})")
            return

        if role not in member.roles:
            await interaction.response.send_message(f"你没有身份组：{role.name}", ephemeral=True)
            return

        try:
            await member.remove_roles(role, reason="用户自助移除")
            logger.info(f"用户 {member.name} ({member.id}) 成功移除身份组 {role.name} ({role.id})")
            await interaction.response.send_message(f"已移除你的身份组：{role.name}", ephemeral=True)
            
            await send_remove_role_log(
                interaction,
                role.id,
                "自助移除身份组",
                extra_lines=[f"身份组名: {role.name}"]
            )

            if persist_list:
                self.persist_user_removal(role, member)

        except discord.Forbidden:
            await interaction.response.send_message("机器人权限不足，无法移除该身份组", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"移除身份组时发生错误：{e}", ephemeral=True)
            logger.error(f"用户 {member.name} ({member.id}) 移除身份组 {role.name} ({role.id}) 时发生错误: {e}", exc_info=True)

    def persist_user_removal(self, role: discord.Role, member: discord.Member):
        role_id_str = str(role.id)
        data_dir = "data"
        file_path = os.path.join(data_dir, f"removed/{role_id_str}.json")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    role_data = json.load(f)
            else:
                role_data = {}
        except (json.JSONDecodeError, IOError):
            role_data = {}

        if "roleid" not in role_data:
            role_data["roleid"] = role_id_str
        if "data" not in role_data or not isinstance(role_data.get("data"), list):
            role_data["data"] = []

        user_id_str = str(member.id)
        if user_id_str not in role_data["data"]:
            role_data["data"].append(user_id_str)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(role_data, f, ensure_ascii=False, indent=2)


async def handle_remove_role(interaction: Interaction, role_ids_str: str, persist_list: bool = False):
    role_id_list = [rid.strip() for rid in role_ids_str.split(',')]
    roles = []
    invalid_ids = []
    role_ids_for_state = []

    for role_id_str in role_id_list:
        try:
            role_id = int(role_id_str)
            role = interaction.guild.get_role(role_id)
            if role:
                roles.append(role)
                role_ids_for_state.append(role.id)
            else:
                invalid_ids.append(role_id_str)
        except ValueError:
            invalid_ids.append(role_id_str)

    if not roles:
        await interaction.response.send_message(f"提供的所有ID均无效或找不到对应的身份组: {', '.join(invalid_ids)}", ephemeral=True)
        return

    # 延迟响应，以获得更长的处理时间并能够发送 followup 消息
    await interaction.response.defer(ephemeral=True, thinking=True)

    if invalid_ids:
        # 发送一个临时的警告消息
        await interaction.followup.send(f"警告：以下ID无效或未找到: {', '.join(invalid_ids)}", ephemeral=True)

    embed = discord.Embed(
        title="自助移除身份组",
        description="从下面的菜单中选择你想要移除的身份组\n操作无法回滚",
        color=discord.Color.blue()
    )
    embed.set_footer(text="枫叶 丨 身份组移除")

    view = RemoveRoleSelectView(roles, persist_list, custom_id_suffix="")
    
    # 发送一个占位消息，以便稍后编辑并添加正确的视图
    try:
        # 先用一个不带 view 的 embed 发送，获取 message 对象
        public_message = await interaction.channel.send(embed=embed)
        message_id = public_message.id
    except discord.Forbidden:
        await interaction.followup.send("错误：机器人没有在此频道发送消息的权限。", ephemeral=True)
        return
    except Exception as e:
        await interaction.followup.send(f"错误：发送面板时发生未知问题: {e}", ephemeral=True)
        logger.error(f"发送移除角色面板时出错: {e}", exc_info=True)
        return

    # 现在我们有了 message_id，可以创建带有正确 custom_id 的视图
    final_view = RemoveRoleSelectView(roles, persist_list, custom_id_suffix=f":{message_id}")

    # 保存状态
    save_panel_state(message_id, role_ids_for_state, persist_list)
    await public_message.edit(embed=embed, view=final_view)
    await interaction.edit_original_response(content="移除角色面板已成功创建！")


async def send_remove_role_log(interaction, role_id, action_desc, extra_lines=None):
    """
    发送自助移除身份组操作日志到日志频道（嵌入式消息 Embed）
    """
    try:
        from config import LOG_CHANNEL_ID
    except ImportError:
        LOG_CHANNEL_ID = None

    if not LOG_CHANNEL_ID:
        logger.warning("未配置 LOG_CHANNEL_ID，无法发送日志到频道")
        return
    try:
        log_channel = interaction.client.get_channel(int(LOG_CHANNEL_ID))
        if not log_channel:
            logger.warning(f"未找到日志频道: {LOG_CHANNEL_ID}")
            return
        
        user_mention = f"<@{interaction.user.id}>"
        embed = discord.Embed(
            title="身份组成员操作日志",
            description=f"**操作类型：** {action_desc}\n"
                        f"**身份组ID：** `{role_id}`\n"
                        f"**用户：** {user_mention}\n",
            color=discord.Color.orange()
        )
        if extra_lines:
            embed.add_field(
                name="附加信息",
                value="\n".join(extra_lines),
                inline=False
            )
        embed.set_footer(text="枫叶 · remove_role_logic.py")
        await log_channel.send(embed=embed)
    except Exception as e:
        logger.error(f"发送自助移除身份组日志到频道失败: {e}")
