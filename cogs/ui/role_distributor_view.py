import discord

class RoleDistributorView(discord.ui.View):
    """
    一个持久化视图，包含“获取身份组”和“退出身份组”按钮。
    这个视图的按钮回调会将交互委托给 RoleDistributorLogic Cog 来处理。
    """
    def __init__(self):
        super().__init__(timeout=None)

    async def _get_cog(self, interaction: discord.Interaction):
        """一个辅助函数，用于获取 RoleDistributorLogic cog 实例。"""
        cog = interaction.client.get_cog('RoleDistributorLogic')
        if not cog:
            await interaction.response.send_message("身份组分发器功能当前不可用，请联系管理员。", ephemeral=True)
        return cog

    @discord.ui.button(label="获取身份组", style=discord.ButtonStyle.success, custom_id="role_distributor:acquire")
    async def acquire_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """处理获取身份组按钮的点击事件。"""
        cog = await self._get_cog(interaction)
        if cog:
            await cog.handle_role_acquisition(interaction)

    @discord.ui.button(label="退出身份组", style=discord.ButtonStyle.danger, custom_id="role_distributor:release")
    async def release_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """处理退出身份组按钮的点击事件。"""
        cog = await self._get_cog(interaction)
        if cog:
            await cog.handle_role_release(interaction)