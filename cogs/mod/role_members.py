import discord
import logging
import csv
import os
import asyncio
from discord.ui import View, Select, Modal, TextInput
from config import LOG_CHANNEL_ID
from utils.progress_utils import create_progress_bar

logger = logging.getLogger(__name__)

async def send_log_to_channel(interaction, role_id, action_desc, extra_lines=None):
    """
    发送操作日志到日志频道（嵌入式消息 Embed）
    :param interaction: discord.Interaction
    :param role_id: int
    :param action_desc: str 操作描述
    :param extra_lines: list[str] 附加内容
    """
    if not LOG_CHANNEL_ID:
        logger.warning("未配置 LOG_CHANNEL_ID，无法发送日志到频道")
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
                        f"**用户：** {user_mention}\n"
                        f"**频道：** {channel_mention}",
            color=discord.Color.green()
        )
        if extra_lines:
            embed.add_field(
                name="附加信息",
                value="\n".join(extra_lines),
                inline=False
            )
        embed.set_footer(text="枫叶 · role_members.py")
        await log_channel.send(embed=embed)
    except Exception as e:
        logger.error(f"发送日志到频道失败: {e}")

class RoleActionSelect(Select):
    def __init__(self, role_id, members, member_list, max_length):
        self.role_id = role_id
        self.members = members
        self.member_list = member_list
        self.max_length = max_length
        
        options = [
            discord.SelectOption(label="仅打印成员名单", value="print", description="仅显示成员名单"),
            discord.SelectOption(label="移除这些人的身份组", value="remove", description="批量移除身份组"),
            discord.SelectOption(label="替换为新身份组", value="replace", description="移除原身份组并添加新身份组"),
        ]
        super().__init__(placeholder="请选择要执行的操作", min_values=1, max_values=1, options=options)

    async def callback(self, interaction2: discord.Interaction):
        action = self.values[0]
        guild = interaction2.guild
        role = guild.get_role(self.role_id)
        logger.info(f"用户 {interaction2.user} 选择了操作: {action} (身份组ID: {self.role_id})")
        
        if action == "print":
            # 生成CSV文件
            filename = f"role_{self.role_id}_members.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['昵称', 'UserID', '用户名'])
                for member in self.members:
                    writer.writerow([member.display_name, member.id, str(member)])
            
            # 发送CSV文件
            file = discord.File(filename)
            await interaction2.response.send_message(
                f"身份组 <@&{self.role_id}> 下的成员列表已生成CSV文件",
                file=file,
            )

            # 日志频道记录
            extra_lines = [f"导出成员数: {len(self.members)}"]
            await send_log_to_channel(
                interaction2,
                self.role_id,
                "导出身份组成员名单",
                extra_lines=extra_lines
            )
            
            # 延迟删除临时文件（后台任务）
            async def delete_file():
                await asyncio.sleep(5)  # 等待5秒确保文件发送完成
                try:
                    os.remove(filename)
                except Exception as e:
                    logger.warning(f"删除临时文件 {filename} 失败: {str(e)}")
            
            asyncio.create_task(delete_file())
        elif action == "remove":
            await self.handle_remove_action(interaction2, role)
        elif action == "replace":
            await self.handle_replace_action(interaction2, role)
        else:
            await interaction2.response.send_message("❌ 未知操作类型", ephemeral=True)

    async def handle_remove_action(self, interaction2: discord.Interaction, role):
        class ConfirmRemoveView(View):
            def __init__(self, role_id, members):
                super().__init__(timeout=30)
                self.role_id = role_id
                self.members = members
                self.value = None

            @discord.ui.button(label="确认批量移除身份组", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != interaction2.user.id:
                    await interaction.response.send_message("❌ 只有命令发起者可以确认操作", ephemeral=True)
                    return
                
                await interaction.response.defer()
                failed = []
                total_members = len(self.members)
                processed_count = 0
                logger.info(f"开始批量移除身份组 {self.role_id} 下的成员 (共 {total_members} 人)")

                progress_embed = discord.Embed(
                    title=f"正在移除身份组: {role.name}",
                    description=create_progress_bar(0, total_members),
                    color=discord.Color.blue()
                )
                progress_message = await interaction.followup.send(embed=progress_embed, wait=True)

                for member in self.members:
                    try:
                        await member.remove_roles(role, reason=f"通过命令移除身份组 {self.role_id}")
                        logger.debug(f"成功移除成员 {member.display_name} ({member.id}) 的身份组")
                    except Exception as e:
                        logger.error(f"移除成员 {member.display_name} ({member.id}) 身份组失败: {str(e)}")
                        failed.append(f"{member.display_name} ({member.id})")
                    
                    processed_count += 1
                    if processed_count % 5 == 0 or processed_count == total_members:
                        progress_embed.description = create_progress_bar(processed_count, total_members)
                        await progress_message.edit(embed=progress_embed)
                        await asyncio.sleep(0.5)

                await progress_message.delete()
                
                msg = f"已尝试移除身份组 <@&{self.role_id}> 下的所有成员\n"
                if failed:
                    msg += f"以下成员移除失败：\n" + "\n".join(failed)
                else:
                    msg += "全部成员移除成功"
                
                await interaction.followup.send(msg)
                # 日志频道记录
                extra_lines = [
                    f"批量移除身份组成员数: {len(self.members)}",
                ]
                if failed:
                    extra_lines.append("移除失败成员：")
                    extra_lines.extend(failed)
                await send_log_to_channel(
                    interaction,
                    self.role_id,
                    "批量移除身份组成员",
                    extra_lines=extra_lines
                )
                self.stop()

            @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != interaction2.user.id:
                    await interaction.response.send_message("❌ 只有命令发起者可以取消操作", ephemeral=True)
                    return
                await interaction.response.send_message("已取消批量移除操作", ephemeral=True)
                self.stop()

        await interaction2.response.send_message(
            f"⚠️ 确认要移除身份组 <@&{self.role_id}> 下的所有成员吗？此操作不可撤销",
            view=ConfirmRemoveView(self.role_id, self.members),
            ephemeral=True
        )

    async def handle_replace_action(self, interaction2: discord.Interaction, role):
        class ConfirmReplaceView(View):
            def __init__(self, role_id, members):
                super().__init__(timeout=30)
                self.role_id = role_id
                self.members = members

            @discord.ui.button(label="确认批量替换身份组", style=discord.ButtonStyle.primary)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != interaction2.user.id:
                    await interaction.response.send_message("❌ 只有命令发起者可以确认操作", ephemeral=True)
                    return

                class NewRoleModal(Modal, title="输入新身份组ID"):
                    new_role_id = TextInput(label="新身份组ID", placeholder="请输入新身份组ID", required=True)
                    
                    def __init__(self, role_id, members):
                        super().__init__()
                        self.role_id = role_id
                        self.members = members

                    async def on_submit(self, modal_interaction: discord.Interaction):
                        try:
                            new_role = interaction.guild.get_role(int(self.new_role_id.value))
                        except Exception:
                            new_role = None
                        
                        if not new_role:
                            await modal_interaction.response.send_message(
                                f"❌ 未找到新身份组ID {self.new_role_id.value}", 
                                ephemeral=True
                            )
                            return
                        
                        # 延迟响应，允许后续使用followup
                        await modal_interaction.response.defer(ephemeral=True)
                        
                        # 立即发送开始消息
                        await modal_interaction.followup.send(f"正在替换身份组 <@&{self.role_id}> 为 <@&{self.new_role_id.value}>...", ephemeral=True)
                        
                        # 在后台执行替换操作
                        async def do_replace():
                            failed_remove = []
                            failed_add = []
                            total_members = len(self.members)
                            processed_count = 0
                            logger.info(f"开始批量替换身份组 {self.role_id} -> {self.new_role_id.value} (共 {total_members} 人)")

                            progress_embed = discord.Embed(
                                title=f"正在替换身份组: {role.name} -> {new_role.name}",
                                description=create_progress_bar(0, total_members),
                                color=discord.Color.blue()
                            )
                            progress_message = await modal_interaction.channel.send(embed=progress_embed)

                            for member in self.members:
                                try:
                                    await member.remove_roles(
                                        role,
                                        reason=f"通过命令替换身份组 {self.role_id} -> {self.new_role_id.value}"
                                    )
                                    logger.info(f"成功移除成员 {member.display_name} ({member.id}) 的原身份组")
                                except Exception as e:
                                    logger.error(f"移除成员 {member.display_name} ({member.id}) 原身份组失败: {str(e)}")
                                    failed_remove.append(f"{member.display_name} ({member.id})")
                                try:
                                    await member.add_roles(
                                        new_role,
                                        reason=f"通过命令替换身份组 {self.role_id} -> {self.new_role_id.value}"
                                    )
                                    logger.info(f"成功为成员 {member.display_name} ({member.id}) 添加新身份组")
                                except Exception as e:
                                    logger.error(f"为成员 {member.display_name} ({member.id}) 添加新身份组失败: {str(e)}")
                                    failed_add.append(f"{member.display_name} ({member.id})")
                                
                                processed_count += 1
                                if processed_count % 5 == 0 or processed_count == total_members:
                                    progress_embed.description = create_progress_bar(processed_count, total_members)
                                    await progress_message.edit(embed=progress_embed)
                                    await asyncio.sleep(0.5)
                           
                            await progress_message.delete()
                            
                            # 准备结果消息
                            msg = f"已完成将身份组 <@&{self.role_id}> 下的成员替换为 <@&{self.new_role_id.value}>\n"
                            if failed_remove:
                                msg += f"以下成员移除原身份组失败：\n" + "\n".join(failed_remove) + "\n"
                            if failed_add:
                                msg += f"以下成员添加新身份组失败：\n" + "\n".join(failed_add)
                            if not failed_remove and not failed_add:
                                msg += "全部成员替换成功"
                            
                            # 发送结果消息
                            try:
                                await modal_interaction.followup.send(msg)
                            except Exception as e:
                                logger.error(f"发送结果消息失败: {str(e)}")
                            # 日志频道记录
                            extra_lines = [
                                f"批量替换身份组成员数: {len(self.members)}",
                                f"新身份组ID: {self.new_role_id.value}",
                            ]
                            if failed_remove:
                                extra_lines.append("移除原身份组失败成员：")
                                extra_lines.extend(failed_remove)
                            if failed_add:
                                extra_lines.append("添加新身份组失败成员：")
                                extra_lines.extend(failed_add)
                            await send_log_to_channel(
                                modal_interaction,
                                self.role_id,
                                f"批量替换身份组成员 -> 新ID: {self.new_role_id.value}",
                                extra_lines=extra_lines
                            )
                        
                        # 在后台执行替换操作
                        modal_interaction.client.loop.create_task(do_replace())
                        self.stop()

                await interaction.response.send_modal(NewRoleModal(self.role_id, self.members))

            @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != interaction2.user.id:
                    await interaction.response.send_message("❌ 只有命令发起者可以取消操作", ephemeral=True)
                    return
                await interaction.response.send_message("已取消批量替换操作", ephemeral=True)
                self.stop()

        await interaction2.response.send_message(
            f"⚠️ 确认要将身份组 <@&{self.role_id}> 下的所有成员替换为新身份组吗？此操作不可撤销",
            view=ConfirmReplaceView(self.role_id, self.members),
            ephemeral=True
        )


class RoleActionView(View):
    def __init__(self, role_id, members, member_list, max_length, current_page=1, total_pages=1):
        super().__init__(timeout=60)
        self.role_id = role_id
        self.members = members
        self.member_list = member_list
        self.max_length = max_length
        self.current_page = current_page
        self.total_pages = total_pages
        
        self.add_item(RoleActionSelect(role_id, members, member_list, max_length))
        
        if total_pages > 1:
            if current_page > 1:
                self.add_item(PageButton("上一页", "prev", discord.ButtonStyle.secondary))
            if current_page < total_pages:
                self.add_item(PageButton("下一页", "next", discord.ButtonStyle.primary))

class PageButton(discord.ui.Button):
    def __init__(self, label, custom_id, style):
        super().__init__(label=label, custom_id=custom_id, style=style)
    
    async def callback(self, interaction: discord.Interaction):
        view: RoleActionView = self.view
        new_page = view.current_page
        
        if self.custom_id == "prev":
            new_page -= 1
        elif self.custom_id == "next":
            new_page += 1
        
        # 获取对应分页的成员列表
        chunks = [view.members[i:i + 30] for i in range(0, len(view.members), 30)]
        chunk = chunks[new_page-1]
        member_list = "\n".join([f"{member.display_name}" for member in chunk])
        
        # 更新embed
        embed = discord.Embed(
            title=f"身份组：{interaction.guild.get_role(view.role_id).name} 的成员列表 ({new_page}/{view.total_pages})", 
            description=f"共有 {len(view.members)} 人 (当前页: {len(chunk)}人)",
            color=discord.Color.blue()
        )
        embed.add_field(name="成员列表", value=f"```\n{member_list}\n```", inline=False)
        
        # 更新view
        new_view = RoleActionView(
            view.role_id,
            view.members,
            member_list,
            view.max_length,
            new_page,
            view.total_pages
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)
