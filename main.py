import discord
from discord.ext import commands
import logging
import config # 导入配置模块
import asyncio # 用于加载扩展
import os # 用于处理路径
from cogs.mod.remove_role_logic import RemoveRoleButton  

logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger('discord_bot')


TOKEN = config.TOKEN
GUILD_IDS = config.GUILD_IDS

intents = discord.Intents.default()
intents.members = True
intents.message_content = True 

# 创建 Bot 实例
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    """当机器人准备就绪时记录消息并同步命令"""
    if not GUILD_IDS: 
        logger.error("没有配置有效的服务器ID，无法继续。")
        await bot.close()
        return

    logger.info(f'{bot.user.name} 已连接到 Discord！')
    
    # 为每个服务器同步命令
    for guild_id in GUILD_IDS:
        logger.info(f'正在尝试为服务器 ID {guild_id} 同步命令...')
        try:
            guild_object = discord.Object(id=guild_id)
            synced = await bot.tree.sync(guild=guild_object)
            logger.info(f'已尝试同步 {len(synced)} 条命令到服务器 ID {guild_id}')
            # 获取服务器名称用于日志
            guild = bot.get_guild(guild_id)
            if guild:
                logger.info(f'目标服务器名称: {guild.name}')
        except discord.errors.Forbidden:
            logger.error(f"机器人缺少同步服务器 {guild_id} 命令所需的 '应用程序命令' 权限。请在服务器设置 -> 集成 -> 机器人和应用 中检查权限。")
        except discord.errors.HTTPException as e:
            logger.error(f"同步命令时发生 HTTP 错误: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"同步命令时发生未知错误: {e}", exc_info=True)


# 使用 setup_hook 来异步加载扩展
async def setup_hook():
    """在机器人登录前递归加载所有 cogs"""
    cogs_root_dir = os.path.join(os.path.dirname(__file__), 'cogs')
    logger.info(f"开始从 {cogs_root_dir} 加载 Cogs...")

    for root, dirs, files in os.walk(cogs_root_dir):
        dirs[:] = [d for d in dirs if not d.startswith('__')]

        for filename in files:
            if filename.endswith('.py') and not filename.startswith('_'):
                relative_path = os.path.relpath(os.path.join(root, filename), cogs_root_dir)
                module_name_parts = relative_path[:-3].split(os.sep)
                cog_name = 'cogs.' + '.'.join(module_name_parts)

                try:
                    await bot.load_extension(cog_name)
                    logger.info(f'成功加载 Cog: {cog_name}')
                except commands.ExtensionNotFound:
                    logger.error(f'Cog 未找到: {cog_name}')
                except commands.ExtensionAlreadyLoaded:
                    logger.warning(f'Cog 已加载: {cog_name}') # 可能在热重载时发生
                except commands.NoEntryPointError:
                    logger.error(f'Cog "{cog_name}" 没有 setup 函数。')
                except commands.ExtensionFailed as e:
                    logger.error(f'加载 Cog "{cog_name}" 失败: {e.__cause__ or e}', exc_info=True)
                except Exception as e:
                    logger.error(f'加载 Cog "{cog_name}" 时发生未知错误: {e}', exc_info=True)

    bot.setup_hook = setup_hook

    # 注册持久化视图
    bot.add_view(RemoveRoleButton(None))  


# 运行机器人
if __name__ == "__main__":
    if TOKEN is None or not GUILD_IDS:
         logger.critical("机器人无法启动，因为 DISCORD_TOKEN 或 GUILD_IDS 未能从配置中加载。请检查 .env 文件和 config.py 中的日志。")
    else:
        try:
            logger.info("正在启动机器人...")
            bot.run(TOKEN)
        except discord.LoginFailure:
            logger.critical("无效的 Discord Token。请检查 .env 文件中的 DISCORD_TOKEN。")
        except Exception as e:
            # 捕获其他可能的启动时异常
            logger.critical(f"启动机器人时发生严重错误: {e}", exc_info=True)
