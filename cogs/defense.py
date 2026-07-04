import discord
from discord.ext import commands
import re
import asyncio
import os
import logging

logger = logging.getLogger('AegisHound')

class UrlDefenseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.MALICIOUS_KEYWORDS = [
            "free-nitro", "discord-gift", "steam-promo", 
            "crypto-airdrop", "login-verify", "free-coins"
        ]
        self.url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-_~:/?#\[\]@!$&\'()*+,;=]+')

    def _sync_extract_urls(self, text: str):
        return list(set(self.url_pattern.findall(text)))

    async def cog_command_error(self, ctx, error):
        logger.error(f"[指令異常] 指令 {ctx.command} 發生錯誤: {str(error)}")

    @commands.command(name="ping")
    async def ping_test(self, ctx):
        await ctx.send("pong! 獵犬依然在線守護著主人喔！🐾")

    @commands.command(name="stress_test")
    async def stress_test(self, ctx, count: int = 5):
        # 配合真實掃描器，壓力測試數量預設稍微調低，避免真的一瞬間把機器塞爆
        is_owner = await self.bot.is_owner(ctx.author)
        if not is_owner:
            return 

        await ctx.send(f"🚀 **[壓力測試啟動]** 正在模擬送入 {count} 個網址進入深度掃描佇列...")

        for i in range(1, count + 1):
            self.bot.scan_counter += 1
            payload = {
                'url': f"http://example.com/test-path-{i}",
                'channel': ctx.channel,
                'scan_id': self.bot.scan_counter
            }
            await self.bot.threat_queue.put(payload)
        
        await ctx.send(f"📥 成功將 {count} 個測試 Payload 塞入佇列。")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        try:
            unique_urls = await asyncio.to_thread(self._sync_extract_urls, message.content)
            if not unique_urls:
                return

            if len(unique_urls) > 5:
                unique_urls = unique_urls[:5]

            is_malicious = False
            triggered_reason = ""

            for url in unique_urls:
                url_lower = url.lower()
                for keyword in self.MALICIOUS_KEYWORDS:
                    if keyword in url_lower:
                        is_malicious = True
                        triggered_reason = keyword
                        break
                if is_malicious:
                    break

            if is_malicious:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                embed = discord.Embed(
                    title="🐺 AegisHound 威脅攔截觸發",
                    description="偵測到破壞性資安風險，危險訊息已被即刻銷毀！",
                    color=discord.Color.red()
                )
                embed.add_field(name="⚠️ 觸發特徵", value=f"`{triggered_reason}`", inline=True)
                embed.add_field(name="👤 風險來源", value=message.author.mention, inline=True)
                await message.channel.send(embed=embed)
                return 

            # 通過粗篩，送入後台大腦
            for url in unique_urls:
                self.bot.scan_counter += 1
                payload = {
                    'url': url,
                    'channel': message.channel,
                    'scan_id': self.bot.scan_counter
                }
                await self.bot.threat_queue.put(payload)

        except Exception as e:
            logger.error(f"[防線崩潰] on_message 發生未預期錯誤：{str(e)}")

async def setup(bot):
    await bot.add_cog(UrlDefenseCog(bot))