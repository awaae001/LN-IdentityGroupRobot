import discord
import os
import json
import logging
from discord import Interaction

logger = logging.getLogger('discord_bot.cogs.remove_role')

class RemoveRoleButton(discord.ui.View):
    def __init__(self, role: discord.Role):
        super().__init__(timeout=None)
        self.role = role

    @discord.ui.button(label="移除身份组", style=discord.ButtonStyle.danger, custom_id="remove_role_button")
    async def remove_role(self, button_interaction: discord.Interaction, button: discord.ui.Button):
        member = button_interaction.user
        # 检查用户是否有该身份组
        if self.role not in member.roles:
            await button_interaction.response.send_message(f"你没有身份组：{self.role.name}。", ephemeral=True)
            return
        try:
            await member.remove_roles(self.role, reason="用户自助移除")
            logger.info(f"用户 {member.name} ({member.id}) 成功移除身份组 {self.role.name} ({self.role.id})。")
            await button_interaction.response.send_message(f"已移除你的身份组：{self.role.name}。", ephemeral=True)
            # 日志推送
            await send_remove_role_log(
                button_interaction,
                self.role.id,
                "自助移除身份组",
                extra_lines=[f"身份组名: {self.role.name}"]
            )
            # 数据持久化
            roleid = str(self.role.id)
            data_dir = "data"
            os.makedirs(data_dir, exist_ok=True)
            file_path = os.path.join(data_dir, f"removed/{roleid}.json")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            # 读取原有数据
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        role_data = json.load(f)
                    except Exception:
                        role_data = {}
            else:
                role_data = {}
            # 组织数据结构
            if "roleid" not in role_data:
                role_data["roleid"] = roleid
            if "data" not in role_data or not isinstance(role_data["data"], list):
                role_data["data"] = []
            user_id = str(member.id)
            if user_id not in role_data["data"]:
                role_data["data"].append(user_id)
            # 写回文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(role_data, f, ensure_ascii=False, indent=2)
        except discord.Forbidden:
            if not button_interaction.response.is_done():
                await button_interaction.response.send_message("机器人权限不足，无法移除该身份组。", ephemeral=True)
        except Exception as e:
            if not button_interaction.response.is_done():
                await button_interaction.response.send_message(f"移除身份组时发生错误：{e}", ephemeral=True)
            logger.error(f"用户 {member.name} ({member.id}) 移除身份组 {self.role.name} ({self.role.id}) 时发生错误: {e}", exc_info=True)

async def handle_remove_role(interaction: Interaction, role_id_str: str):
    try:
        role_id = int(role_id_str)
    except ValueError:
        await interaction.response.send_message("无效的身份组ID，请输入正确的数字ID。", ephemeral=True)
        return

    guild = interaction.guild
    role = guild.get_role(role_id)
    if not role:
        await interaction.response.send_message(f"未找到ID为 {role_id} 的身份组。", ephemeral=True)
        return

    embed = discord.Embed(
        title="自助退出身份组",
        description=f"点击下方按钮可自动退出身份组：**{role.name}**   \n 操作无法回滚",
        color=discord.Color.blue()
    )
    embed.set_footer(text="枫叶 丨 身份组退出")

    view = RemoveRoleButton(role)
    await interaction.response.send_message(embed=embed, view=view)


async def send_remove_role_log(interaction, role_id, action_desc, extra_lines=None):
    """
    发送自助移除身份组操作日志到日志频道（嵌入式消息 Embed）
    :param interaction: discord.Interaction
    :param role_id: int
    :param action_desc: str 操作描述
    :param extra_lines: list[str] 附加内容
    """
    try:
        from config import LOG_CHANNEL_ID
    except ImportError:
        LOG_CHANNEL_ID = None

    if not LOG_CHANNEL_ID:
        logger.warning("未配置 LOG_CHANNEL_ID，无法发送日志到频道。")
        return
    try:
        log_channel = interaction.client.get_channel(int(LOG_CHANNEL_ID))
        if not log_channel:
            logger.warning(f"未找到日志频道: {LOG_CHANNEL_ID}")
            return
        user_mention = f"<@{interaction.user.id}>"
        channel_mention = f"<#{interaction.channel.id}>" if interaction.channel else "未知频道"
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
