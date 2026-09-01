import os
import time
import glob
import logging
import yt_dlp
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("autoshorts.downloader")

DISK_CACHE_MAX_AGE_HOURS = 48
DISK_CACHE_MAX_SIZE_MB = 1024


class YouTubeDownloader:
    def __init__(self, download_dir: str):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self._cleanup_old_downloads()

    def _cleanup_old_downloads(self):
        try:
            now = time.time()
            max_age = DISK_CACHE_MAX_AGE_HOURS * 3600
            for fp in glob.glob(os.path.join(self.download_dir, "*.mp4")):
                if now - os.path.getmtime(fp) > max_age:
                    os.remove(fp)
                    logger.info("Cache limpo: %s (mais de %dh)", os.path.basename(fp), DISK_CACHE_MAX_AGE_HOURS)

            total = sum(os.path.getsize(f) for f in glob.glob(os.path.join(self.download_dir, "*.mp4")))
            if total > DISK_CACHE_MAX_SIZE_MB * 1024 * 1024:
                files = sorted(glob.glob(os.path.join(self.download_dir, "*.mp4")), key=os.path.getmtime)
                for f in files[:len(files) // 2]:
                    os.remove(f)
                    logger.info("Cache reduzido: %s", os.path.basename(f))
        except Exception as e:
            logger.warning("Erro na limpeza do cache: %s", e)

    def extract_info(self, url: str) -> Dict[str, Any]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "socket_timeout": 30,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail"),
                    "channel": info.get("uploader") or info.get("channel"),
                    "description": (info.get("description") or "")[:300],
                    "view_count": info.get("view_count", 0),
                    "url": url,
                }
        except yt_dlp.utils.DownloadError as e:
            raise RuntimeError(f"Falha ao extrair info do video: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Erro inesperado ao acessar o video: {e}") from e

    def download_video(
        self,
        url: str,
        video_id: str,
        ffmpeg_path: Optional[str] = None,
        progress_hook: Optional[Callable[[float], None]] = None,
    ) -> str:
        output_template = os.path.join(self.download_dir, f"{video_id}.%(ext)s")
        target_file = os.path.join(self.download_dir, f"{video_id}.mp4")

        if os.path.exists(target_file) and os.path.getsize(target_file) > 100_000:
            logger.info("Video em cache: %s", target_file)
            return target_file

        def _progress_hook(d: Dict[str, Any]):
            if progress_hook and d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    progress_hook(min(99, int(downloaded / total * 100)))
            elif progress_hook and d.get("status") == "finished":
                progress_hook(100)

        ydl_opts = {
            "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 60,
            "retries": 3,
            "fragment_retries": 3,
            "progress_hooks": [_progress_hook],
        }

        if ffmpeg_path:
            ydl_opts["ffmpeg_location"] = ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            raise RuntimeError(f"Falha no download do video: {e}") from e

        if os.path.exists(target_file) and os.path.getsize(target_file) > 100_000:
            return target_file

        for f in os.listdir(self.download_dir):
            if f.startswith(video_id) and f.endswith((".mp4", ".mkv", ".webm")):
                fp = os.path.join(self.download_dir, f)
                if os.path.getsize(fp) > 100_000:
                    return fp

        raise FileNotFoundError(f"Nao foi possivel localizar o video baixado para o ID {video_id}")
