import discord
from discord import Interaction
import logging
from ..ui.confirm_view import ConfirmView

logger = logging.getLogger('discord_bot.cogs.role_sync_logic')

async def handle_sync_role(interaction: Interaction, role_id_1_str: str, server_id_str: str, role_id_2_str: str, action: str = "bidirectional"):
    """
    处理两个服务器之间身份组的成员同步。

    Args:
        interaction (Interaction): Discord 交互对象。
        role_id_1_str (str): 本服务器的身份组ID。
        server_id_str (str): 远端服务器的ID。
        role_id_2_str (str): 远端服务器的身份组ID。
        action (str): 同步操作类型 ('bidirectional', 'push', 'pull')。
    """
    await interaction.response.defer(ephemeral=True)

    try:
        # 1. 解析和验证ID
        role_id_1 = int(role_id_1_str)
        server_id = int(server_id_str)
        role_id_2 = int(role_id_2_str)

        # 2. 获取服务器对象
        guild_1 = interaction.guild
        guild_2 = interaction.client.get_guild(server_id)

        if guild_2 is None:
            await interaction.followup.send(f"错误：找不到 ID 为 {server_id} 的服务器。机器人可能不在该服务器中。", ephemeral=True)
            logger.error(f"无法找到 ID 为 {server_id} 的服务器。请检查机器人是否在该服务器中。")
            return

        # 3. 获取身份组对象
        role_1 = guild_1.get_role(role_id_1)
        if role_1 is None:
            await interaction.followup.send(f"错误：在当前服务器中找不到 ID 为 {role_id_1} 的身份组。", ephemeral=True)
            logger.error(f"在服务器 {guild_1.name} 中找不到 ID 为 {role_id_1} 的身份组。")
            return

        role_2 = guild_2.get_role(role_id_2)
        if role_2 is None:
            await interaction.followup.send(f"错误：在服务器 {guild_2.name} 中找不到 ID 为 {role_id_2} 的身份组。", ephemeral=True)
            logger.error(f"在服务器 {guild_2.name} 中找不到 ID 为 {role_id_2} 的身份组。")
            return

        # 4. 获取成员列表和服务器成员列表
        members_1_ids = {member.id for member in role_1.members}
        members_2_ids = {member.id for member in role_2.members}
        
        # 获取两个服务器的所有成员ID
        guild_1_member_ids = {member.id for member in guild_1.members}
        guild_2_member_ids = {member.id for member in guild_2.members}
        
        # 5. 找出差异（只考虑同时存在于两个服务器的成员）
        # to_add_to_2: 本地有且在远端服务器中存在但没有身份组 -> 推送
        to_add_to_2 = members_1_ids.intersection(guild_2_member_ids) - members_2_ids
        # to_add_to_1: 远端有且在本地服务器中存在但没有身份组 -> 拉取
        to_add_to_1 = members_2_ids.intersection(guild_1_member_ids) - members_1_ids
        
        # 记录日志，帮助调试
        logger.info(f"本地身份组成员数: {len(members_1_ids)}, 远端身份组成员数: {len(members_2_ids)}")
        logger.info(f"本地服务器成员数: {len(guild_1_member_ids)}, 远端服务器成员数: {len(guild_2_member_ids)}")
        logger.info(f"需要推送到远端的成员数: {len(to_add_to_2)}, 需要拉取到本地的成员数: {len(to_add_to_1)}")

        # 6. 构建确认消息
        if action != "remove_local" and not to_add_to_1 and not to_add_to_2:
            await interaction.followup.send("两个身份组的成员列表已经一致，无需同步。", ephemeral=True)
            logger.info(f"身份组 {role_1.name} 和 {role_2.name} 的成员列表已经一致，无需同步。")
            return

        action_text = {
            "bidirectional": "双向同步",
            "push": "仅推送到远端",
            "pull": "仅同步到本地",
            "remove_local": "移除本地同步身份组"
        }.get(action, "未知操作")

        embed = discord.Embed(
            title="身份组操作确认",
            description=f"**操作类型:** `{action_text}`",
            color=discord.Color.orange() if action == "remove_local" else discord.Color.blue()
        )

        if action in ["bidirectional", "pull"]:
            embed.add_field(
                name=f"⬇️ 拉取到本地 ({guild_1.name})",
                value=f"将向身份组 `{role_1.name}` 添加 **{len(to_add_to_1)}** 名成员。",
                inline=False
            )
        if action in ["bidirectional", "push"]:
            embed.add_field(
                name=f"⬆️ 推送到远端 ({guild_2.name})",
                value=f"将向身份组 `{role_2.name}` 添加 **{len(to_add_to_2)}** 名成员。",
                inline=False
            )
        if action == "remove_local":
            embed.add_field(
                name=f"🗑️ 移除本地身份组 ({guild_1.name})",
                value=f"将从 **{len(members_2_ids)}** 名成员身上移除身份组 `{role_1.name}`。\n**这是一个危险操作，请谨慎确认！**",
                inline=False
            )
        
        embed.set_footer(text="请确认是否执行此操作？")

        view = ConfirmView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        # 等待用户响应
        await view.wait()

        if view.value is None:
            await interaction.edit_original_response(content="操作超时，已取消同步。", embed=None, view=None)
            return
        if not view.value:
            await interaction.edit_original_response(content="操作已取消。", embed=None, view=None)
            return
        
        # 7. 执行同步
        processing_embed = discord.Embed(
            title="正在处理...",
            description=f"正在执行 **{action_text}** 操作，请稍候。",
            color=discord.Color.gold()
        )
        await interaction.edit_original_response(embed=processing_embed, view=None)

        added_to_1_count, failed_to_add_to_1 = 0, []
        added_to_2_count, failed_to_add_to_2 = 0, []
        removed_from_1_count, failed_to_remove_from_1 = 0, []

        if action in ["bidirectional", "pull"]:
            for member_id in to_add_to_1:
                try:
                    # 使用get_member而不是fetch_member，因为我们已经确认这些成员在本地服务器中
                    member = guild_1.get_member(member_id)
                    if member:
                        await member.add_roles(role_1, reason=f"同步自 {guild_2.name} 的 {role_2.name}")
                        added_to_1_count += 1
                    else:
                        logger.warning(f"成员 {member_id} 在本地服务器中不存在，跳过添加身份组")
                        failed_to_add_to_1.append(member_id)
                except Exception as e:
                    logger.error(f"无法将成员 {member_id} 添加到身份组 {role_1.name} ({role_1.id})：{e}")
                    failed_to_add_to_1.append(member_id)

        if action in ["bidirectional", "push"]:
            for member_id in to_add_to_2:
                try:
                    # 使用get_member而不是fetch_member，因为我们已经确认这些成员在远端服务器中
                    member = guild_2.get_member(member_id)
                    if member:
                        await member.add_roles(role_2, reason=f"同步自 {guild_1.name} 的 {role_1.name}")
                        added_to_2_count += 1
                    else:
                        logger.warning(f"成员 {member_id} 在远端服务器中不存在，跳过添加身份组")
                        failed_to_add_to_2.append(member_id)
                except Exception as e:
                    logger.error(f"无法将成员 {member_id} 添加到身份组 {role_2.name} ({role_2.id})：{e}")
                    failed_to_add_to_2.append(member_id)
        
        if action == "remove_local":
            # 只处理同时存在于本地服务器的成员
            members_to_process = members_2_ids.intersection(guild_1_member_ids)
            logger.info(f"移除本地身份组：远端身份组成员数 {len(members_2_ids)}，本地存在的成员数 {len(members_to_process)}")
            
            for member_id in members_to_process:
                try:
                    member = guild_1.get_member(member_id)
                    if member and role_1 in member.roles:
                        await member.remove_roles(role_1, reason=f"根据 {guild_2.name} 的 {role_2.name} 进行移除")
                        removed_from_1_count += 1
                except Exception as e:
                    logger.error(f"无法从成员 {member_id} 身上移除身份组 {role_1.name} ({role_1.id})：{e}")
                    failed_to_remove_from_1.append(member_id)

        # 8. 发送最终报告
        report_embed = discord.Embed(
            title="身份组操作完成",
            description=f"**操作类型:** `{action_text}`",
            color=discord.Color.green()
        )
        if action == "remove_local":
            report_embed.add_field(
                name=f"🗑️ 本地: {guild_1.name}",
                value=f"身份组: {role_1.mention}\n- 移除: **{removed_from_1_count}**\n- 失败: **{len(failed_to_remove_from_1)}**",
                inline=False
            )
        else:
            report_embed.add_field(
                name=f"⬇️ 本地: {guild_1.name}",
                value=f"身份组: {role_1.mention}\n- 新增: **{added_to_1_count}**\n- 失败: **{len(failed_to_add_to_1)}**",
                inline=True
            )
            report_embed.add_field(
                name=f"⬆️ 远端: {guild_2.name}",
                value=f"身份组: `{role_2.name}`\n- 新增: **{added_to_2_count}**\n- 失败: **{len(failed_to_add_to_2)}**",
                inline=True
            )

        # 9. 生成失败报告
        error_report = ""
        if failed_to_add_to_1:
            failed_members_details = []
            for member_id in failed_to_add_to_1:
                try:
                    user = await interaction.client.fetch_user(member_id)
                    failed_members_details.append(f"{user.name} ({user.id})")
                except discord.NotFound:
                    failed_members_details.append(f"未知用户 ({member_id})")
            error_report += f"\n**添加到 {role_1.name} 失败的成员:**\n```\n" + "\n".join(failed_members_details) + "\n```"

        if failed_to_add_to_2:
            failed_members_details = []
            for member_id in failed_to_add_to_2:
                try:
                    user = await interaction.client.fetch_user(member_id)
                    failed_members_details.append(f"{user.name} ({user.id})")
                except discord.NotFound:
                    failed_members_details.append(f"未知用户 ({member_id})")
            error_report += f"\n**添加到 {role_2.name} 失败的成员:**\n```\n" + "\n".join(failed_members_details) + "\n```"
        
        if failed_to_remove_from_1:
            failed_members_details = []
            for member_id in failed_to_remove_from_1:
                try:
                    user = await interaction.client.fetch_user(member_id)
                    failed_members_details.append(f"{user.name} ({user.id})")
                except discord.NotFound:
                    failed_members_details.append(f"未知用户 ({member_id})")
            error_report += f"\n**从 {role_1.name} 移除失败的成员:**\n```\n" + "\n".join(failed_members_details) + "\n```"

        await interaction.edit_original_response(embed=report_embed)
        if error_report:
            if len(error_report) > 2000:
                error_report = error_report[:1990] + "...`"
            await interaction.followup.send(content=error_report, ephemeral=True)


    except ValueError:
        await interaction.followup.send("错误：提供的ID无效，请输入纯数字ID。", ephemeral=True)
    except Exception as e:
        logger.error(f"处理身份组同步时发生错误: {e}", exc_info=True)
        error_embed = discord.Embed(
            title="发生错误",
            description=f"执行同步时发生未知错误: {e}",
            color=discord.Color.red()
        )
        # 确保即使在后续步骤出错，也能通知用户
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=error_embed, view=None)
        else:
            await interaction.followup.send(embed=error_embed, ephemeral=True)
