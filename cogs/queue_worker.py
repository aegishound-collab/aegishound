import discord
from discord.ext import commands, tasks
import asyncio
import os
import logging
import re

# 🧠 引入核心大腦
from core.scanner import AegisScanner

logger = logging.getLogger('AegisHound')

class QueueWorkerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        log_channel_str = os.getenv('LOG_CHANNEL_ID', '')
        self.log_channel_id = int(log_channel_str) if log_channel_str.isdigit() else None
        
        # 🛡️ 系統簡化：全局共用一個 Scanner 實體，避免無謂建立 ThreadPool
        self.scanner = AegisScanner(concurrency=10, regex_workers=4)
        
        self.url_scan_processing.start()

    def cog_unload(self):
        self.url_scan_processing.cancel()
        # 🛡️ 數據校閱：確保模組卸載時，正確關閉底層的 Executor 避免記憶體洩漏
        self.scanner.close()

    async def _process_single_target(self, target_info):
        """獨立處理單一網址的微服務協程"""
        url = target_info['url']
        scan_id = target_info['scan_id']
        origin_channel = target_info['channel']
        
        try:
            # 呼叫核心，這裡本身就會受到 Semaphore 與 RateLimiter 的保護
            scan_result = await self.scanner.scan(url)
            return {'scan_id': scan_id, 'url': url, 'channel': origin_channel, 'result': scan_result, 'error': None}
        except Exception as e:
            return {'scan_id': scan_id, 'url': url, 'channel': origin_channel, 'result': None, 'error': str(e)}

    @tasks.loop(seconds=3.0)
    async def url_scan_processing(self):
        queue = getattr(self.bot, 'threat_queue', None)
        if queue is None:
            return

        log_channel = None
        if self.log_channel_id:
            log_channel = self.bot.get_channel(self.log_channel_id)
            if not log_channel:
                try:
                    log_channel = await self.bot.fetch_channel(self.log_channel_id)
                except Exception:
                    log_channel = None

        # 1. 從輸送帶上打包批次任務 (最大 5 筆)
        batch = []
        max_process_per_loop = 5
        while len(batch) < max_process_per_loop:
            try:
                batch.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break 

        if not batch:
            return

        # 2. 🚀 平行展開：讓大腦同時掃描這批網址
        tasks_list = [self._process_single_target(info) for info in batch]
        completed_results = await asyncio.gather(*tasks_list)

        # 3. 整理報告與 UI 呈現
        channel_reports = {}
        for item in completed_results:
            ch_id = item['channel'].id
            if ch_id not in channel_reports:
                channel_reports[ch_id] = {
                    'channel_mention': item['channel'].mention,
                    'reports': [],
                    'has_risk': False
                }
            
            safe_url = re.sub(r'^https?://', 'hxxps://', item['url'], flags=re.IGNORECASE)
            display_url = safe_url if len(safe_url) <= 80 else safe_url[:77] + "..."
            
            if item['error']:
                status_icon = "⚠️"
                detail = f"系統異常: {item['error'][:50]}..."
                channel_reports[ch_id]['has_risk'] = True
            else:
                scan_res = item['result']
                if not scan_res.findings and not scan_res.errors:
                    status_icon = "🟢"
                    detail = f"無風險 (深潛 {scan_res.pages_crawled} 頁)"
                else:
                    status_icon = "🔴"
                    channel_reports[ch_id]['has_risk'] = True
                    if scan_res.findings:
                        first = scan_res.findings[0]
                        detail = f"風險觸發: `{first.pattern_name}` (熵值 {first.entropy:.2f})"
                    else:
                        detail = f"WAF 或連線阻斷: {scan_res.errors[0][:50]}..."
            
            channel_reports[ch_id]['reports'].append(
                f"{status_icon} `[ID: {item['scan_id']}]` {display_url}\n└ {detail}"
            )
            
            # 通知 Queue 任務完成
            queue.task_done()

        # 4. 推播報告
        for ch_id, info in channel_reports.items():
            lines = info['reports']
            if not log_channel:
                for line in lines:
                    logger.info(f"[靜默留存] {line}")
                continue 
            
            embed_color = discord.Color.red() if info['has_risk'] else discord.Color.brand_green()
            embed = discord.Embed(
                title="🐾 獵犬深度掃描報告 (大腦併發解析中)",
                description="\n\n".join(lines),
                color=embed_color
            )
            embed.add_field(name="📍 來源頻道", value=info['channel_mention'], inline=True)
            embed.add_field(name="📊 消化數量", value=f"{len(lines)} 筆", inline=True)

            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"[推播失敗] 無法傳送報告至 Log 頻道: {str(e)}")

    @url_scan_processing.before_loop
    async def before_url_scan(self):
        await self.bot.wait_until_ready()
        logger.info("[系統啟動] 大腦對接完畢，高併發掃描輸送帶就緒。")

async def setup(bot):
    await bot.add_cog(QueueWorkerCog(bot))