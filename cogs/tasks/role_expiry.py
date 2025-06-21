import discord
from discord.ext import commands, tasks
import logging
import time
from datetime import timedelta, datetime
import os
import asyncio
import json

# 导入共享的日志加载/保存函数和配置
try:
    from ..mod.role_assigner_logic import _load_assignment_log, _save_assignment_log
    import config # 导入根目录的 config
except ImportError:
   
    from cogs.mod.role_assigner_logic import _load_assignment_log, _save_assignment_log
    import config

logger = logging.getLogger('discord_bot.cogs.tasks.role_expiry')
logger.setLevel(logging.DEBUG)  # 确保日志级别为DEBUG

# 定义过期时间（15天）
EXPIRY_DURATION_SECONDS = 30 * 24 * 60 * 60
# EXPIRY_DURATION_SECONDS = 60 # 测试用：设置为 1 分钟

class RoleExpiryTask(commands.Cog):
    """
    处理身份组自动过期和替换的后台任务 Cog。
    """
    def __init__(self, bot):
        self.bot = bot
        self.check_expired_roles.start()

    def cog_unload(self):
        self.check_expired_roles.cancel()

    @tasks.loop(hours=1.0) 
    # @tasks.loop(minutes=1.0) # 测试用：每分钟检查一次
    # @tasks.loop(seconds=10)
    async def check_expired_roles(self):
        """定期检查并处理过期的身份组分配记录"""
        logger.debug("开始检查过期的身份组分配...")
        try:
            exited_user_ids = set()
            removed_dir = "data/removed"
            if os.path.exists(removed_dir):
                for fname in os.listdir(removed_dir):
                    if fname.endswith(".json"):
                        fpath = os.path.join(removed_dir, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                exited_data = json.load(f)
                                exited_user_ids.update(exited_data.get("data", []))
                        except Exception as e:
                            logger.error(f"读取排除名单文件 {fpath} 失败: {e}")

            log_data = _load_assignment_log()
            if not isinstance(log_data, list):
                logger.error("分配日志格式不正确，应为列表。跳过本次检查。")
                return

            current_time = time.time()
            logs_to_keep = []
            processed_operations = 0

            for operation_entry in log_data:
                if not isinstance(operation_entry, list) or len(operation_entry) != 2:
                    logs_to_keep.append(operation_entry)
                    continue

                operation_id, details = operation_entry
                # 检查 fade 标记，若为 True 则跳过自动褪色
                if isinstance(details, dict) and details.get("fade") is True:
                    logs_to_keep.append(operation_entry)
                    continue

                if not isinstance(details, dict) or 'timestamp' not in details or 'data' not in details:
                    logs_to_keep.append(operation_entry)
                    continue

                operation_timestamp = details.get('timestamp')
                assignment_details_list = details.get('data')

                if not isinstance(operation_timestamp, (int, float)):
                     logs_to_keep.append(operation_entry)
                     continue

                if not isinstance(assignment_details_list, list):
                    logs_to_keep.append(operation_entry)
                    continue

                # 检查是否过期
                if current_time - operation_timestamp > EXPIRY_DURATION_SECONDS:
                    logger.info(f"处理过期操作 ID {operation_id}")
                    processed_operations += 1
                    operation_fully_processed = True # 假设此操作能完全处理

                    for assignment in assignment_details_list:
                        if not isinstance(assignment, dict):
                            logger.debug(f"操作 {operation_id} 包含无效分配条目")
                            operation_fully_processed = False # 标记此操作未完全处理
                            continue # 跳过这个损坏的分配条目

                        guild_id = assignment.get('guild_id')
                        old_role_ids = assignment.get('role_ids', [])
                        assigned_user_ids = assignment.get('assigned_user_ids', [])

                        if not all([guild_id, isinstance(old_role_ids, list), isinstance(assigned_user_ids, list)]):
                            logger.debug(f"操作 {operation_id} 服务器 {guild_id} 数据不完整")
                            operation_fully_processed = False
                            continue

                        # 获取替换身份组 ID
                        replacement_role_id = config.REPLACEMENT_ROLES.get(guild_id)
                        if not replacement_role_id:
                            logger.warning(f"服务器 {guild_id} 未配置替换身份组")
                            operation_fully_processed = False # 标记此操作未完全处理
                            continue # 跳到下一个分配条目

                        # 获取 Discord 对象
                        guild = self.bot.get_guild(guild_id)
                        if not guild:
                            logger.warning(f"机器人未加入服务器 {guild_id}")
                            operation_fully_processed = False
                            continue

                        replacement_role = guild.get_role(replacement_role_id)
                        if not replacement_role:
                            logger.warning(f"服务器 {guild_id} 未找到替换身份组 {replacement_role_id}")
                            operation_fully_processed = False
                            continue

                        old_roles = []
                        valid_old_role_ids = []
                        for r_id in old_role_ids:
                            role = guild.get_role(r_id)
                            if role:
                                old_roles.append(role)
                                valid_old_role_ids.append(r_id)
                            else:
                                logger.error(f"服务器 {guild_id} 未找到旧身份组 {r_id}")

                        if not old_roles:
                            logger.error(f"服务器 {guild_id} 无有效旧身份组")

                        # 检查机器人权限
                        bot_member = guild.get_member(self.bot.user.id)
                        if not bot_member:
                            logger.error(f"无法获取机器人在 {guild_id} 的成员对象")
                            operation_fully_processed = False
                            continue

                        can_manage_roles = bot_member.guild_permissions.manage_roles
                        if not can_manage_roles:
                            logger.warning(f"服务器 {guild_id} 缺少管理身份组权限")
                            operation_fully_processed = False
                            continue

                        for user_id in assigned_user_ids:
                            # 跳过自动退出名单中的用户
                            if str(user_id) in exited_user_ids:
                                logger.debug(f"用户 {user_id} 在自动退出名单，跳过补偿身份组")
                                continue

                            member = None
                            try:
                                member = await guild.fetch_member(user_id)
                            except discord.NotFound:
                                logger.debug(f"用户 {user_id} 已离开服务器 {guild_id}")
                                continue # 跳到下一个用户
                            except discord.Forbidden:
                                logger.error(f"无法获取用户 {user_id} 在服务器 {guild_id} 的信息")
                                operation_fully_processed = False # 标记未完全处理
                                continue # 跳到下一个用户
                            except Exception as e:
                                logger.error(f"获取用户 {user_id} 错误: {e}", exc_info=True)
                                operation_fully_processed = False
                                continue

                            if member:
                                # 移除旧身份组
                                roles_to_remove = [role for role in old_roles if role in member.roles]
                                if roles_to_remove:
                                    try:
                                        await member.remove_roles(*roles_to_remove, reason=f"自动过期替换 (操作ID: {operation_id})")
                                        logger.debug(f"已移除用户 {user_id} 的旧身份组")
                                    except discord.Forbidden:
                                        logger.error(f"无法移除用户 {user_id} 的身份组")
                                        operation_fully_processed = False
                                    except discord.HTTPException as e:
                                        logger.error(f"移除用户 {user_id} 身份组 HTTP 错误: {e}")
                                        operation_fully_processed = False
                                    except Exception as e:
                                        logger.error(f"移除用户 {user_id} 身份组错误: {e}", exc_info=True)
                                        operation_fully_processed = False

                                # 添加新身份组 (仅当不在用户身上时)
                                if replacement_role not in member.roles:
                                    try:
                                        await member.add_roles(replacement_role, reason=f"自动过期替换 (操作ID: {operation_id})")
                                        logger.debug(f"已为用户 {user_id} 添加替换身份组")
                                    except discord.Forbidden:
                                        logger.error(f"无法为用户 {user_id} 添加替换身份组")
                                        operation_fully_processed = False
                                    except discord.HTTPException as e:
                                        logger.error(f"为用户 {user_id} 添加身份组 HTTP 错误: {e}")
                                        operation_fully_processed = False
                                    except Exception as e:
                                        logger.error(f"为用户 {user_id} 添加身份组错误: {e}", exc_info=True)
                                        operation_fully_processed = False
                                else:
                                    logger.debug(f"用户 {user_id} 已有替换身份组")


                    if not operation_fully_processed:
                        logger.warning(f"操作 {operation_id} 未完全处理")
                        logs_to_keep.append(operation_entry)
                    else:
                        logger.debug(f"操作 {operation_id} 处理完成")

                else:
                    # 未过期，保留日志
                    logs_to_keep.append(operation_entry)

            # 保存更新后的日志 (仅当日志内容有变动时)
            if len(logs_to_keep) != len(log_data):
                logger.debug(f"保存日志变更，处理了 {processed_operations} 个操作")
                _save_assignment_log(logs_to_keep)

            # 发送处理结果到日志频道
            # logger.debug(f"准备发送处理结果到日志频道，LOG_CHANNEL_ID: {config.LOG_CHANNEL_ID}")
            if config.LOG_CHANNEL_ID and processed_operations > 0:
                try:
                    log_channel = self.bot.get_channel(int(config.LOG_CHANNEL_ID))
                    logger.debug(f"获取到的日志频道: {log_channel}")
                    if log_channel:
                        success_users = []
                        for operation_entry in log_data:
                            if not isinstance(operation_entry, list) or len(operation_entry) != 2:
                                continue
                            operation_id, details = operation_entry
                            if not isinstance(details, dict) or 'data' not in details:
                                continue
                            assignment_details_list = details.get('data')
                            if not isinstance(assignment_details_list, list):
                                continue
                            for assignment in assignment_details_list:
                                if isinstance(assignment, dict):
                                    assigned_user_ids = assignment.get('assigned_user_ids', [])
                                    success_users.extend(str(uid) for uid in assigned_user_ids)
                        
                        message = f"已处理 {processed_operations} 个过期操作\n成功处理的用户ID:\n" + "\n".join(success_users)
                        await log_channel.send(message)
                except Exception as e:
                    logger.error(f"发送过期处理结果到日志频道失败: {e}")

        except FileNotFoundError:
             logger.debug("分配日志文件不存在")
        except json.JSONDecodeError:
             logger.error("无法解析分配日志文件")
        except Exception as e:
            logger.error(f"检查过期身份组错误: {e}", exc_info=True)

    @check_expired_roles.before_loop
    async def before_check_expired_roles(self):
        """在任务循环开始前等待机器人准备就绪"""
        await self.bot.wait_until_ready()

    @check_expired_roles.error
    async def check_expired_roles_error(self, error):
        """处理任务循环中的错误"""
        logger.error(f"任务错误: {error}", exc_info=True)
        await asyncio.sleep(60)
        if not self.check_expired_roles.is_running():
             self.check_expired_roles.restart()


async def setup(bot):
    # 确保数据目录存在
    data_dir = "data"
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
        except OSError as e:
            logger.error(f"无法创建数据目录 {data_dir}: {e}")
            # 如果无法创建目录，Cog 可能无法正常工作，可以选择不加载
            # return

    # 确保日志文件存在（如果不存在则创建空列表文件）
    assignment_log_file = os.path.join(data_dir, "role_assignments.json")
    if not os.path.exists(assignment_log_file):
        try:
            with open(assignment_log_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        except IOError as e:
             logger.error(f"无法创建空的分配日志文件 {assignment_log_file}: {e}")
             # 如果无法创建文件，Cog 可能无法正常工作
             # return

    # 检查替换身份组配置是否加载
    if not config.REPLACEMENT_ROLES:
         logger.warning("未配置替换身份组 (REPLACEMENT_ROLES 为空)")
         # 即使没有配置，也加载 Cog，以便将来添加配置后能工作

    await bot.add_cog(RoleExpiryTask(bot))
