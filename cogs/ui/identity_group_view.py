import discord
from discord.ui import View, Select
from cogs.logic import identity_group_logic

class IdentityGroupView(View):
    def __init__(self):
        super().__init__(timeout=None)
        # Add buttons for adding and removing roles
        self.add_item(self.create_action_button("➕ 佩戴身份组", "add_role", discord.ButtonStyle.primary))
        self.add_item(self.create_action_button("➖ 移除身份组", "remove_role", discord.ButtonStyle.danger))
        self.add_item(self.create_action_button("👀 查看我的身份组", "view_my_roles", discord.ButtonStyle.secondary))

    def create_action_button(self, label, custom_id, style: discord.ButtonStyle):
        button = discord.ui.Button(label=label, custom_id=custom_id, style=style)
        button.callback = self.button_callback
        return button

    async def button_callback(self, interaction: discord.Interaction):
        action = interaction.data['custom_id']

        if action == "view_my_roles":
            await identity_group_logic.handle_view_my_roles(interaction)
            return

        options = identity_group_logic.get_user_assignable_roles(interaction.user, action)

        if not options:
            action_text = "佩戴" if action == "add_role" else "移除"
            embed = discord.Embed(
                title="提示",
                description=f"您当前没有可 {action_text} 的身份组。",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        title, description, color = self.get_embed_details(action)
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="此消息将在3分钟后失效。")

        select = self.create_role_select(options, action)
        
        view = View(timeout=180)
        view.add_item(select)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def get_embed_details(self, action):
        if action == "add_role":
            return "佩戴身份组", "请从下面的菜单中选择您想佩戴的身份组。", discord.Color.blue()
        else: # remove_role
            return "移除身份组", "请从下面的菜单中选择您想移除的身份组。", discord.Color.red()

    def create_role_select(self, options, action):
        placeholder_text = f"✨ 选择要{'佩戴' if action == 'add_role' else '移除'}的身份组..."

        select = Select(
            placeholder=placeholder_text,
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"{action}_select",
            disabled=False
        )
        select.callback = self.select_callback
        return select

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.data['values'][0] == 'no_roles':
            embed = discord.Embed(title="提示", description="没有可操作的选项。", color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        selected_role_id = int(interaction.data['values'][0])
        action = interaction.data['custom_id'].split('_')[0]
        
        await identity_group_logic.handle_role_update(interaction, selected_role_id, action)
