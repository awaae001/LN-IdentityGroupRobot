import discord
import json

def load_json_file(file_path):
    """Helper function to load a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json_file(file_path, data):
    """Helper function to save data to a JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user_assignable_roles(user: discord.Member, action: str):
    """
    Get the roles that a user can add or remove based on their assignments.
    """
    guild_roles = load_json_file('data/role_mapping.json')
    user_roles_data = load_json_file('data/user_role_assignments.json')
    user_id_str = str(user.id)
    
    options = []
    user_current_role_ids = {role.id for role in user.roles}
    
    if user_id_str in user_roles_data:
        assigned_roles = user_roles_data[user_id_str].get(str(user.guild.id), [])
        
        for role_id in assigned_roles:
            role_id_str = str(role_id)
            role_name = None
            for group in guild_roles.values():
                if role_id_str in group.get('data', {}):
                    role_name = group['data'][role_id_str]
                    break
            
            if role_name:
                if action == "add_role" and role_id not in user_current_role_ids:
                    options.append(discord.SelectOption(label=role_name, value=role_id_str))
                elif action == "remove_role" and role_id in user_current_role_ids:
                    options.append(discord.SelectOption(label=role_name, value=role_id_str))
    return options

async def handle_role_update(interaction: discord.Interaction, selected_role_id: int, action: str):
    """
    Handles the logic of adding or removing a role from a member.
    """
    role = interaction.guild.get_role(selected_role_id)
    member = interaction.user

    if not role:
        embed = discord.Embed(title="错误", description="选择的身份组不存在或已被删除。", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)
        return

    try:
        log_file = 'data/role_removal_log.json'
        removal_log = load_json_file(log_file)
        role_id_str = str(selected_role_id)
        user_id_str = str(member.id)

        if action == "add":
            if role in member.roles:
                embed = discord.Embed(title="提示", description=f"您已经拥有身份组：**{role.name}**。", color=discord.Color.gold())
            else:
                await member.add_roles(role, reason="用户通过身份组管理器佩戴")
                embed = discord.Embed(title="✅ 操作成功", description=f"已为您佩戴身份组：**{role.name}**。", color=discord.Color.green())
                
                if role_id_str in removal_log and user_id_str in removal_log[role_id_str]:
                    removal_log[role_id_str].remove(user_id_str)
                    if not removal_log[role_id_str]:
                        del removal_log[role_id_str]
                    save_json_file(log_file, removal_log)

        elif action == "remove":
            if role not in member.roles:
                embed = discord.Embed(title="提示", description=f"您没有身份组：**{role.name}**。", color=discord.Color.gold())
            else:
                await member.remove_roles(role, reason="用户通过身份组管理器移除")
                embed = discord.Embed(title="✅ 操作成功", description=f"已移除您的身份组：**{role.name}**。", color=discord.Color.green())
                
                if role_id_str not in removal_log:
                    removal_log[role_id_str] = []
                if user_id_str not in removal_log[role_id_str]:
                    removal_log[role_id_str].append(user_id_str)
                save_json_file(log_file, removal_log)
        
        await interaction.response.edit_message(embed=embed, view=None)

    except discord.Forbidden:
        embed = discord.Embed(title="❌ 权限错误", description="机器人权限不足，无法操作该身份组。", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)
    except Exception as e:
        embed = discord.Embed(title="❌ 未知错误", description=f"操作身份组时发生错误：\n```\n{e}\n```", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)

async def handle_view_my_roles(interaction: discord.Interaction):
    """
    Handles the logic to view the user's current roles.
    """
    user = interaction.user
    guild_roles_map = load_json_file('data/role_mapping.json')
    
    all_managed_roles = {}
    for group in guild_roles_map.values():
        all_managed_roles.update(group.get('data', {}))

    user_roles = []
    for role in user.roles:
        role_id_str = str(role.id)
        if role_id_str in all_managed_roles:
            user_roles.append(f"- {role.mention} (`{all_managed_roles[role_id_str]}`)")

    if not user_roles:
        description = "您当前没有任何通过身份组管理器获取的身份组。"
    else:
        description = "\n".join(user_roles)

    embed = discord.Embed(
        title=f"✨ {user.display_name} 的身份组",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"共找到 {len(user_roles)} 个身份组。")

    await interaction.response.send_message(embed=embed, ephemeral=True)
