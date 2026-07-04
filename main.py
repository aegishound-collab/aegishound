import discord
from discord.ext import commands
import os
import asyncio
import logging
from dotenv import load_dotenv

# ==========================================
# 🛡️ 核心防禦：全域日誌實體隔離
# ==========================================
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('bot_error.log', encoding='utf-8')
file_handler.setFormatter(log_formatter)

logger = logging.getLogger('AegisHound')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING) 
discord_logger.addHandler(file_handler)

load_dotenv()

class AegisHound(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        # 任務輸送帶
        self.threat_queue = None
        self.scan_counter = 0

    async def setup_hook(self):
        logger.info("[系統啟動] 總指揮官正在部署防禦齒輪...")
        
        self.threat_queue = asyncio.Queue()
        
        allowed_cogs_str = os.getenv('ALLOWED_COGS', 'defense,queue_worker')
        allowed_cogs = [cog.strip() for cog in allowed_cogs_str.split(',') if cog.strip()]

        for cog_name in allowed_cogs:
            try:
                await self.load_extension(f'cogs.{cog_name}')
                logger.info(f"[模組載入] 已成功掛載資安齒輪：{cog_name}")
            except Exception as e:
                logger.error(f"[掛載失敗] 載入 {cog_name} 失敗！異常摘要: {str(e)}")

    async def on_ready(self):
        print(f"🐺 [核心連線] AegisHound 成功對接 Discord Gateway！")
        logger.info(f"獵犬代號：{self.user} (ID: {self.user.id}) 成功上線。")

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ [系統終止] 找不到 DISCORD_TOKEN！")
    else:
        bot = AegisHound()
        bot.run(token, log_handler=None)