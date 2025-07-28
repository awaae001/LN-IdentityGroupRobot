import discord
from discord.ext import commands
import json
import logging
import os
from cogs.ui.role_distributor_view import RoleDistributorView

logger = logging.getLogger('discord_bot.cogs.role_distributor_logic')

class RoleDistributorLogic(commands.Cog):
    """处理身份组分发器核心逻辑的 Cog"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.distributors_file = 'data/role_distributors.json'
        self.distributors = self.load_distributors()

    def load_distributors(self):
        """从 JSON 文件加载分发器配置"""
        try:
            with open(self.distributors_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_distributors(self):
        """将分发器配置保存到 JSON 文件"""
        with open(self.distributors_file, 'w', encoding='utf-8') as f:
            json.dump(self.distributors, f, indent=4)

    async def handle_role_acquisition(self, interaction: discord.Interaction):
        """处理用户获取身份组的请求"""
        await interaction.response.defer(ephemeral=True)
        channel_id_str = str(interaction.channel_id)

        if channel_id_str not in self.distributors:
            await interaction.followup.send("此频道没有配置身份组分发器", ephemeral=True)
            return

        config = self.distributors[channel_id_str]
        role_id = config.get('role_id')
        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.followup.send("配置的身份组无效，请联系管理员", ephemeral=True)
            return

        member = interaction.user
        if role in member.roles:
            await interaction.followup.send(f"您已经拥有 **{role.name}** 身份组", ephemeral=True)
        else:
            try:
                await member.add_roles(role, reason="通过身份组分发器获取")
                await interaction.followup.send(f"成功获取 **{role.name}** 身份组！", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("机器人权限不足，无法为您添加身份组", ephemeral=True)

    async def handle_role_release(self, interaction: discord.Interaction):
        """处理用户退出身份组的请求"""
        await interaction.response.defer(ephemeral=True)
        channel_id_str = str(interaction.channel_id)

        if channel_id_str not in self.distributors:
            await interaction.followup.send("此频道没有配置身份组分发器", ephemeral=True)
            return

        config = self.distributors[channel_id_str]
        role_id = config.get('role_id')
        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.followup.send("配置的身份组无效，请联系管理员", ephemeral=True)
            return

        member = interaction.user
        if role not in member.roles:
            await interaction.followup.send(f"您不拥有 **{role.name}** 身份组", ephemeral=True)
        else:
            try:
                await member.remove_roles(role, reason="通过身份组分发器退出")
                await interaction.followup.send(f"已成功退出 **{role.name}** 身份组", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("机器人权限不足，无法为您移除身份组", ephemeral=True)

    async def delete_distributor(self, channel: discord.TextChannel):
        """安全地删除一个频道的分发器配置并删除其消息"""
        channel_id_str = str(channel.id)
        if channel_id_str in self.distributors:
            config = self.distributors.pop(channel_id_str)
            self.save_distributors()
            
            try:
                message = await channel.fetch_message(config["message_id"])
                await message.delete()
                logger.info(f"成功删除了频道 {channel.id} 的身份组分发器消息")
            except discord.NotFound:
                logger.warning(f"试图删除时，在频道 {channel.id} 中找不到分发器消息 (ID: {config['message_id']})")
            except discord.Forbidden:
                logger.error(f"机器人没有权限删除频道 {channel.id} 中的消息")
            
            return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """监听消息事件，以保持分发器消息在频道底部"""
        if message.author.bot:
            return

        channel_id_str = str(message.channel.id)
        if channel_id_str in self.distributors:
            config = self.distributors[channel_id_str]
            
            # 删除旧消息
            try:
                old_message = await message.channel.fetch_message(config["message_id"])
                await old_message.delete()
            except discord.NotFound:
                logger.warning(f"在频道 {channel_id_str} 中找不到旧的分发消息 (ID: {config['message_id']})，可能已被手动删除")
            except discord.Forbidden:
                logger.error(f"机器人没有权限删除频道 {channel_id_str} 中的消息")
                return # 如果无法删除，则不继续以避免垃圾信息

            # 发送新消息
            try:
                embed = discord.Embed(title=config["title"], description=config["content"], color=discord.Color.blue())
                if message.guild.icon:
                    embed.set_author(name=config["name"], icon_url=message.guild.icon.url)
                else:
                    embed.set_author(name=config["name"])
                
                view = RoleDistributorView()
                new_message = await message.channel.send(embed=embed, view=view)
                
                # 更新配置中的消息ID
                self.distributors[channel_id_str]["message_id"] = new_message.id
                self.save_distributors()
                
            except discord.Forbidden:
                logger.error(f"机器人没有权限在频道 {channel_id_str} 中发送新的分发消息")
            except Exception as e:
                logger.error(f"重新发送分发消息时出错: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    """异步 setup 函数，用于加载 Cog"""
    await bot.add_cog(RoleDistributorLogic(bot))
    logger.info("RoleDistributorLogic Cog 已成功加载")