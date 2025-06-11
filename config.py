import os
import logging
from dotenv import load_dotenv

# 配置日志记录器 (config 模块也可能需要记录信息)
logger = logging.getLogger(__name__) # 使用模块名作为记录器名称

# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量获取配置
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_IDS_STR = os.getenv('GUILD_IDS') or os.getenv('GUILD_ID')  # 支持新旧环境变量名
GUILD_ID_STR = GUILD_IDS_STR  # 保持向后兼容

# 授权用户与管理员
ADMIN_USER_IDS_STR = os.getenv('ADMIN_USER_IDS', '')
ADMIN_USER_IDS = [uid.strip() for uid in ADMIN_USER_IDS_STR.split(',') if uid.strip()]
if not ADMIN_USER_IDS:
    logger.warning("环境变量 'ADMIN_USER_IDS' 未设置或为空，将使用空列表。")
    
AUTHORIZED_ROLE_IDS_STR = os.getenv('AUTHORIZED_ROLE_IDS', '')
AUTHORIZED_ROLE_IDS = [rid.strip() for rid in AUTHORIZED_ROLE_IDS_STR.split(',') if rid.strip()]
if not AUTHORIZED_ROLE_IDS:
    logger.warning("环境变量 'AUTHORIZED_ROLE_IDS' 未设置或为空，将使用空列表。")

# 处理服务器ID
GUILD_IDS = []
GUILD_ID = None  # 保持向后兼容

if GUILD_IDS_STR:
    try:
        # 支持逗号分隔的多个服务器ID
        GUILD_IDS = [int(gid.strip()) for gid in GUILD_IDS_STR.split(',') if gid.strip()]
        if GUILD_IDS:
            GUILD_ID = GUILD_IDS[0]  # 第一个ID作为默认值保持兼容
        else:
            logger.error("GUILD_IDS 格式无效，请检查 .env 文件")
    except ValueError as e:
        logger.error(f"服务器ID格式错误: {e}")
else:
    logger.error("GUILD_IDS 未在 .env 文件中设置")
