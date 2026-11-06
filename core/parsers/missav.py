import os
import re
import uuid
import asyncio
from typing import Optional, Dict, Any

from astrbot.api import logger
from astrbot.core.message.components import Video
from .base import BaseParser


class MissAVParser(BaseParser):
    name = "MissAV解析器"
    platform = "missav"

    def __init__(self, config=None, downloader=None):
        super().__init__(config, downloader)
        self.download_dir = "./cache"
        os.makedirs(self.download_dir, exist_ok=True)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def is_match(self, url: str) -> bool:
        return bool(re.search(r"missav\.[a-z]+/", url))

    async def get_m3u8(self, page_url: str) -> Optional[str]:
        try:
            # 优先复用父类的 aiohttp session
            session = getattr(self, "session", None)
            if session and not session.closed:
                async with session.get(page_url, headers=self.headers) as resp:
                    if resp.status != 200:
                        return None
                    html = await resp.text()
            else:
                import aiohttp
                async with aiohttp.ClientSession() as new_session:
                    async with new_session.get(page_url, headers=self.headers) as resp:
                        if resp.status != 200:
                            return None
                        html = await resp.text()

            m3u8_matches = re.findall(r"https?://[^\s'\"]+\.m3u8[^\s'\"]*", html)
            return m3u8_matches[0] if m3u8_matches else None
        except Exception as e:
            logger.error(f"[MissAVParser] 获取 M3U8 失败: {e}")
            return None

    async def download_video(self, m3u8_url: str) -> Optional[str]:
        output_file = os.path.join(self.download_dir, f"{uuid.uuid4().hex}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-headers", f"User-Agent: {self.headers['User-Agent']}\r\n",
            "-i", m3u8_url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            output_file
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return output_file
        except Exception as e:
            logger.error(f"[MissAVParser] FFmpeg 下载视频失败: {e}")
        return None

    async def parse(self, url: str) -> Optional[Dict[str, Any]]:
        """实现插件基类要求的统一 parse 接口"""
        m3u8_url = await self.get_m3u8(url)
        if not m3u8_url:
            return None
        
        mp4_path = await self.download_video(m3u8_url)
        if not mp4_path:
            return None
            
        return {
            "type": "video",
            "video": Video.fromFileSystem(mp4_path),
            "file_path": mp4_path
        }
