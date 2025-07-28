import discord
import re
from discord.ui import Modal, TextInput, View, Button

class ApplyModal(Modal, title='申请身份组'):
    def __init__(self, role_id: int, required_reactions: int, forum_channel_id: int):
        super().__init__()
        self.role_id = role_id
        self.required_reactions = required_reactions
        self.forum_channel_id = forum_channel_id
        self.add_item(TextInput(label="帖子链接", placeholder="请输入你的帖子链接..."))

    async def on_submit(self, interaction: discord.Interaction):
        link = self.children[0].value
        # 修正正则表达式以正确解析帖子链接
        match = re.match(r"https://discord.com/channels/(\d+)/(\d+)", link)

        if not match:
            await interaction.response.send_message("无效的帖子链接格式。请提供一个有效的帖子链接。", ephemeral=True)
            return

        guild_id_from_link = int(match.group(1))
        thread_id = int(match.group(2))

        if guild_id_from_link != interaction.guild.id:
            await interaction.response.send_message("该链接不属于当前服务器。", ephemeral=True)
            return

        try:
            # 获取帖子（线程）对象
            thread = await interaction.guild.fetch_channel(thread_id)
            if not isinstance(thread, discord.Thread):
                 await interaction.response.send_message("链接指向的不是一个有效的帖子（线程）。", ephemeral=True)
                 return
        except discord.NotFound:
            await interaction.response.send_message("找不到该帖子，请检查链接是否正确。", ephemeral=True)
            return

        # 验证帖子的父频道是否为指定的作用域
        if thread.parent_id != self.forum_channel_id:
            forum_channel = interaction.guild.get_channel(self.forum_channel_id)
            await interaction.response.send_message(f"该帖子不属于指定的论坛频道 ({forum_channel.mention if forum_channel else '未知频道'})。", ephemeral=True)
            return

        if thread.owner_id != interaction.user.id:
            await interaction.response.send_message("帖子的作者不是你，无法申请", ephemeral=True)
            return

        try:
            # 论坛帖子的起始消息ID与帖子本身的ID相同
            start_message = await thread.fetch_message(thread.id)
        except discord.NotFound:
            await interaction.response.send_message("无法获取帖子的起始消息。", ephemeral=True)
            return

        if not start_message.reactions:
            await interaction.response.send_message(f"你的帖子还没有任何反应，需要 {self.required_reactions} 个反应才能申请。", ephemeral=True)
            return
        
        highest_reaction_count = 0
        if start_message.reactions:
            highest_reaction_count = max(reaction.count for reaction in start_message.reactions)

        if highest_reaction_count < self.required_reactions:
            await interaction.response.send_message(f"你的帖子最高反应数（{highest_reaction_count}）未达到要求的 {self.required_reactions} 个", ephemeral=True)
            return
            
        role = interaction.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message("无法找到指定的身份组", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("你已经拥有该身份组了", ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"恭喜！你已成功申请并获得了 {role.name} 身份组！", ephemeral=True)

class RoleAutoApplyView(View):
    def __init__(self):
        super().__init__(timeout=None)
        # The button is defined here, but the logic is handled by a listener.
        # The custom_id set here is a placeholder. It will be overwritten in the command.
        self.add_item(Button(label="点击申请", style=discord.ButtonStyle.primary, custom_id="placeholder_auto_apply_id"))