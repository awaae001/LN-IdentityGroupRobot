import discord
from discord.ext import commands
import logging
import config # 导入配置模块
import asyncio # 用于加载扩展
import os # 用于处理路径

# 配置日志 (基础配置可以在这里，或者移到 config.py 如果需要更复杂的设置)
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger('discord_bot') # 主机器人的 logger


TOKEN = config.TOKEN
GUILD_IDS = config.GUILD_IDS  # 改为支持多个服务器ID

# 设置 intents，需要 members intent 来获取用户信息
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
    """在机器人登录前加载所有 cogs"""
    # 构建 cogs 目录的路径
    cogs_dir = os.path.join(os.path.dirname(__file__), 'cogs')
    # 查找 cogs 目录下的所有 Python 文件
    for filename in os.listdir(cogs_dir):
        if filename.endswith('.py') and not filename.startswith('_'):
            cog_name = f'cogs.{filename[:-3]}' # 构建模块路径
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
                logger.error(f'加载 Cog "{cog_name}" 失败: {e}', exc_info=True) # 包含原始异常信息
            except Exception as e:
                 logger.error(f'加载 Cog "{cog_name}" 时发生未知错误: {e}', exc_info=True)

# 将 setup_hook 附加到 bot
bot.setup_hook = setup_hook


# 运行机器人
if __name__ == "__main__":
    # 启动前的检查现在主要在 config.py 中完成
    # 这里只检查关键配置是否成功导入
    if TOKEN is None or not GUILD_IDS:
         logger.critical("机器人无法启动，因为 DISCORD_TOKEN 或 GUILD_IDS 未能从配置中加载。请检查 .env 文件和 config.py 中的日志。")
    else:
        try:
            logger.info("正在启动机器人...")
            bot.run(TOKEN)
        except discord.LoginFailure:
            # 这个错误仍然特定于 bot.run，所以保留在这里
            logger.critical("无效的 Discord Token。请检查 .env 文件中的 DISCORD_TOKEN。")
        except Exception as e:
            # 捕获其他可能的启动时异常
            logger.critical(f"启动机器人时发生严重错误: {e}", exc_info=True)
