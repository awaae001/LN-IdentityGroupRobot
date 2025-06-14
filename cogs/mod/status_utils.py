import discord
import logging
import psutil
from datetime import datetime
from typing import Tuple, Dict, Union

logger = logging.getLogger(__name__)

async def get_system_status() -> Dict[str, Union[str, int, float]]:
    return {
        'cpu_usage': psutil.cpu_percent(),
        'ram_usage': psutil.virtual_memory().percent
    }


async def build_status_embed(bot_instance) -> discord.Embed:
    # 获取各项状态
    system_status = await get_system_status()
    
    # Discord延迟
    dc_latency = round(bot_instance.latency * 1000) if bot_instance.latency else "N/A"
    
    # 创建Embed
    embed = discord.Embed(
        title="📊 系统与机器人状态",
        color=discord.Color.blue()
    )
    
    # 添加字段
    embed.add_field(name="🖥️ 主机 CPU", value=f"{system_status['cpu_usage']}%", inline=True)
    embed.add_field(name="🧠 主机 RAM", value=f"{system_status['ram_usage']}%", inline=True)
    embed.add_field(name=" ", value=" ", inline=True)
    
    embed.add_field(name="<:logosdiscordicon:1383323627579244664> Discord 延迟", 
                   value=f"{dc_latency} ms" if isinstance(dc_latency, int) else dc_latency, 
                   inline=True)
    
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    embed.set_footer(text=f"枫叶 · 系统状态丨查询时间: {timestamp}")
    
    return embed

async def handle_status_command(interaction: discord.Interaction, bot_instance):
    await interaction.response.defer(ephemeral=False)
    
    try:
        embed = await build_status_embed(bot_instance)
        await interaction.followup.send(embed=embed)
        logger.info(f"用户 {interaction.user} 查询了状态")
    except Exception as e:
        logger.error(f"处理状态命令时出错: {e}")
        await interaction.followup.send("❌ 获取状态信息时出错", ephemeral=True)
