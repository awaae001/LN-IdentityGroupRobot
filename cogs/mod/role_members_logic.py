import discord
import logging
from discord import Interaction, Embed
from .role_members import RoleActionView

logger = logging.getLogger(__name__)

async def handle_list_role_members(interaction: Interaction, role_id_str: str):
    """
    处理list_role_members命令的核心逻辑
    """
    logger.info(f"用户 {interaction.user.name}({interaction.user.id}) 请求了身份组 {role_id_str} 的成员列表")
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ 此命令只能在服务器内使用。", ephemeral=True, delete_after=120)
        return
    
    try:
        role_id = int(role_id_str)
    except ValueError:
        await interaction.response.send_message("❌ 请输入正确的身份组ID（数字）。", ephemeral=True, delete_after=120)
        return
    
    role = guild.get_role(role_id)
    if not role:
        await interaction.response.send_message(f"❌ 未找到ID为 {role_id} 的身份组。", ephemeral=True, delete_after=120)
        return
    
    members = role.members
    if not members:
        await interaction.response.send_message(f"身份组 <@&{role_id}> 下没有成员。", ephemeral=True, delete_after=120)
        return

    # 分页显示成员列表，每页最多30个成员
    chunks = [members[i:i + 30] for i in range(0, len(members), 30)]
    total_pages = len(chunks)
    logger.info(f"分页信息 - 总成员数: {len(members)}, 总页数: {total_pages}, 每页成员数: {[len(c) for c in chunks]}")
    
    first_chunk = chunks[0]
    member_list = "\n".join([f"{member.display_name}" for member in first_chunk])
    embed = Embed(
        title=f"身份组：{role.name} 的成员列表 (1/{total_pages})", 
        description=f"共有 {len(members)} 人 (当前页: {len(first_chunk)}人)",
        color=discord.Color.blue()
    )
    embed.add_field(name="成员列表", value=f"```\n{member_list}\n```", inline=False)
    
    # 添加交互组件
    view = RoleActionView(role_id, members, member_list, len(members), 1, total_pages)
    
    await interaction.response.send_message(
        embed=embed,
        view=view,
        delete_after=120,
        ephemeral=True
    )
