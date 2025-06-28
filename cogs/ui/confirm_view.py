import discord
from discord.ui import View, Button, button

class ConfirmView(View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)
        self.value = None

    @button(label="确认", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.value = True
        self.stop()
        # 禁用按钮，防止重复点击
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)


    @button(label="取消", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        self.value = False
        self.stop()
        # 禁用按钮，防止重复点击
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
