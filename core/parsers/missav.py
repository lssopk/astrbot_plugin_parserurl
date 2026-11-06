cat << 'EOF' > core/parsers/missav.py
import os
import re
import uuid
import asyncio
import aiohttp
from astrbot.api.message_components import Video
from .base import BaseParser

class MissAVParser(BaseParser):
    name = "MissAV解析器"
    platform = "missav"

    def __init__(self, download_dir="./cache"):
        super().__init__()
        self.download_dir = download_dir
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

    async def get_m3u8(self, page_url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(page_url, headers=self.headers) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

        m3u8_matches = re.findall(r"https?://[^\s'\"]+\.m3u8[^\s'\"]*", html)
        return m3u8_matches[0] if m3u8_matches else None

    async def download_video(self, m3u8_url: str) -> str:
        output_file = os.path.join(self.download_dir, f"{uuid.uuid4().hex}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-headers", f"User-Agent: {self.headers['User-Agent']}\r\n",
            "-i", m3u8_url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            output_file
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            return output_file
        return None

    async def parse(self, url: str):
        m3u8_url = await self.get_m3u8(url)
        if not m3u8_url:
            return None
        
        mp4_path = await self.download_video(m3u8_url)
        if not mp4_path:
            return None
            
        return Video.fromFileSystem(mp4_path)
EOF
