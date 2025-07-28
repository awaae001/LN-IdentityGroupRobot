import discord
from discord import Interaction
import logging
import re
from config import GUILD_IDS
import config
import json
import os
import random
from datetime import datetime

logger = logging.getLogger('discord_bot.cogs.role_assigner_logic')

DATA_DIR = "data"
ASSIGNMENT_LOG_FILE = os.path.join(DATA_DIR, "role_assignments.json")

def _ensure_data_dir():
    """确保数据目录存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def _load_assignment_log():
    """加载分配日志"""
    _ensure_data_dir()
    try:
        # 使用 'a+' 模式打开文件，如果文件不存在则创建
        with open(ASSIGNMENT_LOG_FILE, 'a+', encoding='utf-8') as f:
            f.seek(0)
            content = f.read()
            if not content:
                return []
            return json.loads(content) 
    except json.JSONDecodeError:
         logger.error(f"无法解析分配日志文件 {ASSIGNMENT_LOG_FILE}，将返回空列表")
         return [] 
    except IOError as e:
        logger.error(f"读取分配日志文件 {ASSIGNMENT_LOG_FILE} 时出错: {e}")
        return []


def _save_assignment_log(log_data):
    """保存分配日志"""
    _ensure_data_dir()
    try:
        with open(ASSIGNMENT_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logger.error(f"无法写入分配日志文件 {ASSIGNMENT_LOG_FILE}: {e}")


async def handle_assign_roles(interaction: Interaction, role_id_str: str = None, user_ids_str: str = None, message_link: str = None, role_id_str_1: str = None, role_id_str_2: str = None, fade: bool = False, time: int = None, operation_id: str = None):
    """
    处理批量分配身份组的核心逻辑
    fade: 处理标记，True 时系统检查时跳过自动褪色操作
    time: 过期时间(天数)，默认为90天
    operation_id: 如果提供，则基于此历史操作补充人员
    """
    user_ids = []
    guild = interaction.guild
    all_guilds = [g for g in interaction.client.guilds if g.id in GUILD_IDS]
    role_status = {}
    operation_timestamp = datetime.now().isoformat()
    
    # 如果提供了 operation_id，则从历史记录加载角色
    if operation_id:
        log_data = _load_assignment_log()
        history_op = next((op for op in log_data if op[0] == operation_id), None)

        if not history_op:
            await interaction.response.send_message(f"错误：未找到操作ID为 `{operation_id}` 的历史记录", ephemeral=True)
            return
        
        # 从历史记录中提取所有涉及的 role_id
        all_role_ids = []
        for entry in history_op[1]['data']:
            all_role_ids.extend(entry.get('role_ids', []))
        
        # 去重并转换为字符串
        role_id_strs_from_history = [str(rid) for rid in set(all_role_ids)]
        
        # 用历史 role_id 覆盖传入的参数
        role_id_str = role_id_strs_from_history[0] if len(role_id_strs_from_history) > 0 else None
        role_id_str_1 = role_id_strs_from_history[1] if len(role_id_strs_from_history) > 1 else None
        role_id_str_2 = role_id_strs_from_history[2] if len(role_id_strs_from_history) > 2 else None
        
        if not any([role_id_str, role_id_str_1, role_id_str_2]):
            await interaction.response.send_message(f"错误：操作ID `{operation_id}` 的历史记录中不包含有效的身份组信息", ephemeral=True)
            return
            
    elif not role_id_str:
        await interaction.response.send_message("错误：必须提供身份组ID或有效的操作ID", ephemeral=True)
        return

    # 如果不是基于历史操作，则生成新的 operation_id
    if not operation_id:
        operation_id = str(random.randint(1000, 9999))

    for g in all_guilds:
        invalid_in_guild = []
        valid_in_guild = []
        for rid_str in [role_id_str, role_id_str_1, role_id_str_2]:
            if not rid_str:
                continue
            try:
                role_id = int(rid_str)
                role = g.get_role(role_id)
                if role:
                    valid_in_guild.append(f"{role.name} ({role.id})")
                else:
                    invalid_in_guild.append(rid_str)
            except ValueError:
                invalid_in_guild.append(rid_str)
        
        role_status[g.id] = {
            "valid": valid_in_guild,
            "invalid": invalid_in_guild,
            "name": g.name
        }

    # 检查所有服务器中的身份组状态
    all_valid = all(not status["invalid"] for status in role_status.values())
    await interaction.response.defer(ephemeral=not all_valid)
    
    # 创建验证结果Embed
    verify_embed = discord.Embed(
        title="身份组验证结果",
        color=discord.Color.blue()
    )
    
    for gid, status in role_status.items():
        # 只显示有有效身份组的服务器
        if status["valid"]:
            field_value = f"✅ 有效身份组: {', '.join(status['valid'])}\n"
            verify_embed.add_field(
                name=f"服务器: {status['name']} ({gid})",
                value=field_value,
                inline=False
            )
    
    # 创建确认Embed
    confirm_embed = discord.Embed(
        title="身份组分配确认",
        description="即将执行以下身份组分配操作",
        color=discord.Color.orange()
    )
    
    # 添加角色信息
    role_info = []
    for g in all_guilds:
        current_roles = []
        for rid_str in [role_id_str, role_id_str_1, role_id_str_2]:
            if rid_str:
                try:
                    role = g.get_role(int(rid_str))
                    if role:
                        current_roles.append(role)
                except ValueError:
                    continue
        
        if current_roles:
            role_info.append(
                f"**{g.name}**: " + 
                ", ".join([f'"{r.name}" ({r.id})' for r in current_roles])
            )
    
    if role_info:
        confirm_embed.add_field(
            name="分配的身份组",
            value="\n".join(role_info),
            inline=False
        )
    
    # 创建确认按钮
    class ConfirmButton(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.confirmed = False
        
        @discord.ui.button(label="确认", style=discord.ButtonStyle.green)
        async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != interaction.user.id:
                await button_interaction.response.send_message(
                    "只有发起命令的用户可以确认操作", 
                    ephemeral=True
                )
                return
            
            await confirm_msg.delete()

            await button_interaction.response.send_message(
                "处理中...", 
                ephemeral=True,
                delete_after=5  
            )
            
            self.confirmed = True
            self.stop()
        
        @discord.ui.button(label="取消", style=discord.ButtonStyle.red)
        async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != interaction.user.id:
                await button_interaction.response.send_message(
                    "只有发起命令的用户可以取消操作", 
                    ephemeral=True
                )
                return
            
            await button_interaction.response.send_message(
                "操作已取消",
                ephemeral=True
            )
            await confirm_msg.delete()

                
            self.stop()

    await interaction.followup.send(embed=verify_embed, ephemeral=not all_valid)

    # 然后发送确认请求
    view = ConfirmButton()
    confirm_msg = await interaction.followup.send(
        embed=confirm_embed,
        view=view,
        wait=True
    )

    await view.wait()

    if not view.confirmed:
        return

    roles = []
    user_ids = []
    invalid_ids = []

    if message_link:
        # 解析消息链接并提取用户 ID
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        match = re.match(r'https://discord\.com/channels/(\d+)/(\d+)/(\d+)', message_link)
        if not match:
            await interaction.followup.send("错误：提供的消息链接格式无效", ephemeral=True)
            return

        link_guild_id, channel_id, message_id = map(int, match.groups())

        if link_guild_id != guild.id:
             await interaction.followup.send("错误：消息链接指向的服务器与当前服务器不符", ephemeral=True)
             return

        try:
            channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
            if not isinstance(channel, discord.TextChannel): 
                 await interaction.followup.send("错误：消息链接指向的不是有效的文本频道", ephemeral=True)
                 return
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.followup.send("错误：无法找到消息链接对应的频道或消息", ephemeral=True)
            return
        except discord.Forbidden:
             await interaction.followup.send("错误：机器人没有权限访问该消息所在的频道", ephemeral=True)
             return
        except Exception as e:
            logger.error(f"获取消息时出错 ({message_link}): {e}", exc_info=True)
            await interaction.followup.send("错误：获取消息时发生未知错误", ephemeral=True)
            return

        # 从消息内容中提取用户提及
        mentioned_user_ids_raw = re.findall(r'<@!?(\d+)>', message.content)
        if not mentioned_user_ids_raw:
             await interaction.followup.send("错误：在指定的消息中未找到任何用户提及", ephemeral=True)
             return

        for uid_str in mentioned_user_ids_raw:
             try:
                 user_ids.append(int(uid_str))
             except ValueError:
                 invalid_ids.append(uid_str)

    elif user_ids_str:
        # 从提供的字符串中解析用户 ID
        user_ids_raw = re.findall(r'\d+', user_ids_str)
        for uid_str in user_ids_raw:
            try:
                user_ids.append(int(uid_str))
            except ValueError:
                invalid_ids.append(uid_str)
    else:
        # 如果两者都未提供
        await interaction.response.send_message("错误：请提供用户 ID 列表或有效的消息链接", ephemeral=True)
        return

    # 去重
    user_ids = list(set(user_ids))
    if not user_ids:
        await interaction.response.send_message("错误：未能提取到任何有效的用户 ID", ephemeral=True)
        return

    all_assigned = []
    all_failed = []
    all_log_entries = []

    # 在所有服务器中分配身份组
    for g in all_guilds:
        # 获取当前服务器的角色
        current_roles = []
        for rid_str in [role_id_str, role_id_str_1, role_id_str_2]:
            if not rid_str:
                continue
            try:
                role_id = int(rid_str)
                role = g.get_role(role_id)
                if role:
                    current_roles.append(role)
            except ValueError:
                continue
        
        # 跳过没有有效身份组的服务器
        if not current_roles:
            continue

        # 检查机器人权限
        bot_member = g.get_member(interaction.client.user.id)
        if not bot_member:
            continue
            
        for role in current_roles:
            if bot_member.top_role <= role:
                all_failed.append(f'{g.name}: 权限不足无法分配 {role.name} ({role.id})')
                continue

        assigned_users = []
        failed_users = []
        successfully_assigned_ids = []

        for user_id in user_ids:
            try:
                member = await g.fetch_member(user_id)
                if member:
                    await member.add_roles(*current_roles)
                    role_names = ", ".join([f'"{r.name}" ({r.id})' for r in current_roles])
                    assigned_users.append(f'{g.name}: {member.name}#{member.discriminator}')
                    successfully_assigned_ids.append(member.id)
                    logger.info(f'在服务器 {g.name} 成功为 {member.name} 分配了 {role_names} 身份组')
            except discord.NotFound:
                failed_users.append(f'{g.name}: {user_id} (未找到)')
                logger.warning(f'在服务器 {g.name} 未找到 ID 为 {user_id} 的用户')
            except discord.Forbidden:
                failed_users.append(f'{g.name}: {user_id} (权限不足)')
                logger.error(f'在服务器 {g.name} 机器人权限不足，无法为 ID 为 {user_id} 的用户分配身份组')
            except Exception as e:
                failed_users.append(f'{g.name}: {user_id} (未知错误: {e})')
                logger.error(f'在服务器 {g.name} 为 ID 为 {user_id} 的用户分配身份组时发生未知错误: {e}', exc_info=True)

        if successfully_assigned_ids:
            all_log_entries.append({
                "guild_id": g.id,
                "guild_name": g.name,
                "role_ids": [r.id for r in current_roles],
                "role_names": [r.name for r in current_roles],
                "timestamp": operation_timestamp,
                "assigned_user_ids": successfully_assigned_ids,
                "operation_id": operation_id
            })
        
        all_assigned.extend(assigned_users)
        all_failed.extend(failed_users)

    # 保存所有分配日志
    # 保存或更新分配日志
    if all_log_entries:
        try:
            log_data = _load_assignment_log()
            if not isinstance(log_data, list):
                log_data = []

            # 检查是否是基于历史操作的补充
            existing_op_index = -1
            for i, op in enumerate(log_data):
                if op[0] == operation_id:
                    existing_op_index = i
                    break
            
            if existing_op_index != -1:
                # 更新现有操作
                logger.info(f"正在为操作ID {operation_id} 补充新的人员分配记录")
                # all_log_entries 包含了本次新分配的用户
                # 我们需要将这些新用户追加到历史记录中
                for new_entry in all_log_entries:
                    guild_id = new_entry['guild_id']
                    new_user_ids = new_entry['assigned_user_ids']
                    
                    # 在旧记录中查找对应服务器的条目
                    history_guild_entry = next((e for e in log_data[existing_op_index][1]['data'] if e['guild_id'] == guild_id), None)
                    
                    if history_guild_entry:
                        # 合并用户ID并去重
                        existing_user_ids = set(history_guild_entry.get('assigned_user_ids', []))
                        existing_user_ids.update(new_user_ids)
                        history_guild_entry['assigned_user_ids'] = list(existing_user_ids)
                        logger.debug(f"已将 {len(new_user_ids)} 名新用户追加到服务器 {guild_id} 的记录中")
                    else:
                        # 如果历史记录中没有这个服务器的条目（理论上不应该发生），则添加
                        log_data[existing_op_index][1]['data'].append(new_entry)
                        logger.warning(f"在操作 {operation_id} 的历史记录中未找到服务器 {guild_id} 的条目，已新建")

            else:
                # 创建新操作
                logger.info(f"正在创建新的操作ID {operation_id} 的分配记录")
                operation_entry = [
                    operation_id,
                    {
                        "operation_id": operation_id,
                        "fade": fade,
                        "outtime": time,
                        "timestamp": int(datetime.now().timestamp()),
                        "data": all_log_entries
                    }
                ]
                log_data.append(operation_entry)

            _save_assignment_log(log_data)
            logger.info(f"已成功将操作ID {operation_id} 的分配记录保存到 {ASSIGNMENT_LOG_FILE}")

        except Exception as e:
            logger.error(f"保存分配日志时出错: {e}", exc_info=True)
    # 构建响应消息
    try:
        # 先检查总embed长度
        if len(all_assigned) > 50 or len(all_failed) > 20:
            summary = discord.Embed(
                title="跨服务器身份组分配完成",
                description=f"成功: {len(all_assigned)}, 失败: {len(all_failed)}\n详情请查看机器人控制台日志",
                color=discord.Color.green()
            )
            await interaction.channel.send(embed=summary)
            # 同时发送到日志频道
            if config.LOG_CHANNEL_ID:
                log_channel = interaction.client.get_channel(int(config.LOG_CHANNEL_ID))
                if log_channel:
                    await log_channel.send(embed=summary)
            return

        # 构建详细embeds
        success_embed = discord.Embed(
            title="跨服务器身份组分配 - 成功情况",
            color=discord.Color.green()
        )
        
        if roles:
            role_value = "\n".join([f'- "{r.name}" ({r.id})' for r in roles])
            if len(role_value) > 1024:
                role_value = role_value[:1000] + "\n... (内容过长，已截断)"
            success_embed.add_field(
                name="分配的身份组",
                value=role_value,
                inline=False
            )
        
        if all_assigned:
            assigned_value = "\n".join([f'- {user}' for user in all_assigned])
            if len(assigned_value) > 1024:
                assigned_value = assigned_value[:1000] + "\n... (内容过长，已截断)"
            success_embed.add_field(
                name=f"成功分配的用户 ({len(all_assigned)})",
                value=assigned_value,
                inline=False
            )
        
        if all_failed:
            fail_embed = discord.Embed(
                title="跨服务器身份组分配 - 失败情况",
                color=discord.Color.red()
            )
            failed_value = "\n".join([f'- {fail}' for fail in all_failed])
            if len(failed_value) > 1024:
                failed_value = failed_value[:1000] + "\n... (内容过长，已截断)"
            fail_embed.add_field(
                name=f"分配失败的情况 ({len(all_failed)})",
                value=failed_value,
                inline=False
            )
            await interaction.channel.send(embed=fail_embed)
            # 同时发送到日志频道
            if config.LOG_CHANNEL_ID:
                log_channel = interaction.client.get_channel(int(config.LOG_CHANNEL_ID))
                if log_channel:
                    await log_channel.send(embed=fail_embed)
        
        await interaction.channel.send(embed=success_embed)
        # 同时发送到日志频道
        if config.LOG_CHANNEL_ID:
            log_channel = interaction.client.get_channel(int(config.LOG_CHANNEL_ID))
            if log_channel:
                await log_channel.send(embed=success_embed)
        
    except discord.HTTPException as e:
        logger.error(f"发送embed时出错: {str(e)}")
        await interaction.followup.send("操作已完成，但发送结果时出错", ephemeral=True)
    except Exception as e:
        logger.error(f"发送结果时发生未知错误: {str(e)}")
        await interaction.followup.send("操作已完成，但发送结果时发生错误", ephemeral=True)
