import os
import re
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("autoshorts.transcriber")

_transcript_cache: Dict[str, tuple] = {}
CACHE_TTL = 1800


class YouTubeTranscriber:
    def __init__(self):
        pass

    def extract_video_id(self, url_or_id: str) -> str:
        if len(url_or_id) == 11 and not ("/" in url_or_id or "." in url_or_id):
            return url_or_id

        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11})",
            r"(?:embed\/)([0-9A-Za-z_-]{11})",
            r"(?:shorts\/)([0-9A-Za-z_-]{11})",
            r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
            r"(?:live\/)([0-9A-Za-z_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        return url_or_id

    def get_transcript(
        self,
        url_or_id: str,
        preferred_languages: Optional[List[str]] = None,
        video_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        video_id = self.extract_video_id(url_or_id)

        now = time.time()
        if video_id in _transcript_cache:
            cached_time, cached_data = _transcript_cache[video_id]
            if now - cached_time < CACHE_TTL:
                logger.info("Transcricao em cache: %s", video_id)
                return cached_data

        if not preferred_languages:
            preferred_languages = ["pt", "pt-BR", "en", "es"]

        # 1. Tenta obter transcrição via youtube-transcript-api
        try:
            result = self._fetch_transcript(video_id, preferred_languages)
            if result and len(result) > 0:
                _transcript_cache[video_id] = (time.time(), result)
                return result
        except Exception as e:
            logger.warning("Falha ao obter legendas oficiais do YouTube para %s: %s", video_id, e)

        # 2. Fallback: Cria segmentação inteligente por timeline quando o vídeo não possui legendas (ex: clipes musicais, gameplays)
        logger.info("Gerando segmentação temporal inteligente para %s", video_id)
        fallback_segments = self._generate_fallback_segments(video_metadata)
        _transcript_cache[video_id] = (time.time(), fallback_segments)
        return fallback_segments

    def _fetch_transcript(
        self, video_id: str, preferred_languages: List[str]
    ) -> List[Dict[str, Any]]:
        from youtube_transcript_api import YouTubeTranscriptApi

        # Suporte a youtube-transcript-api v1.2.4+ (instanciável) e versões legadas
        try:
            ytt = YouTubeTranscriptApi()
        except Exception:
            ytt = YouTubeTranscriptApi

        # 1. Tenta listar transcrições disponíveis
        try:
            if hasattr(ytt, "list"):
                transcript_list = ytt.list(video_id)
            elif hasattr(YouTubeTranscriptApi, "list_transcripts"):
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            else:
                transcript_list = None

            if transcript_list:
                # 1.1 Manual
                try:
                    if hasattr(transcript_list, "find_manually_created_transcript"):
                        t = transcript_list.find_manually_created_transcript(preferred_languages)
                        return self._clean_segments(t.fetch())
                except Exception:
                    pass

                # 1.2 Gerada automaticamente
                try:
                    if hasattr(transcript_list, "find_generated_transcript"):
                        t = transcript_list.find_generated_transcript(preferred_languages)
                        return self._clean_segments(t.fetch())
                except Exception:
                    pass

                # 1.3 Qualquer uma disponível
                for t in transcript_list:
                    try:
                        return self._clean_segments(t.fetch())
                    except Exception:
                        continue
        except Exception as e:
            logger.debug("list_transcripts falhou: %s", e)

        # 2. Tenta fetch direto
        try:
            if hasattr(ytt, "fetch"):
                data = ytt.fetch(video_id, languages=preferred_languages)
                return self._clean_segments(data)
            elif hasattr(YouTubeTranscriptApi, "get_transcript"):
                data = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_languages)
                return self._clean_segments(data)
        except Exception as e:
            logger.debug("fetch direto falhou: %s", e)

        raise RuntimeError(f"Nenhuma legenda encontrada no YouTube para {video_id}")

    def _generate_fallback_segments(
        self, video_metadata: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Gera segmentos baseados na linha do tempo quando o vídeo não tem legendas no YouTube
        (como clipes musicais, gameplays sem fala ou vídeos onde o YouTube bloqueia extração).
        """
        total_duration = 300.0
        title = "Destaque do Vídeo"
        if video_metadata:
            total_duration = float(video_metadata.get("duration", 300.0) or 300.0)
            title = video_metadata.get("title", title)

        if total_duration <= 0:
            total_duration = 180.0

        segments = []
        step = 25.0
        current = 0.0
        idx = 1

        while current < total_duration:
            seg_end = min(total_duration, current + step)
            if seg_end - current >= 5.0:
                segments.append({
                    "start": round(current, 2),
                    "end": round(seg_end, 2),
                    "duration": round(seg_end - current, 2),
                    "text": f"[{title} - Momento #{idx}]",
                })
                idx += 1
            current += step

        return segments

    def _clean_segments(self, raw_segments: Any) -> List[Dict[str, Any]]:
        cleaned = []

        # Padrões de ruídos e artefatos de legenda automática do YouTube a serem limpos
        noise_patterns = re.compile(
            r"\[(música|musica|risos|aplausos|gritos|vinheta|ruído|ruido|music|laughter|applause|cheering|noise)\]",
            re.IGNORECASE,
        )

        for item in raw_segments:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                start = float(item.get("start", 0.0))
                duration = float(item.get("duration", 0.0))
            else:
                text = str(getattr(item, "text", "")).strip()
                start = float(getattr(item, "start", 0.0))
                duration = float(getattr(item, "duration", 0.0))

            text = text.replace("\n", " ")
            text = noise_patterns.sub("", text).strip()
            text = re.sub(r"\s+", " ", text)

            if not text or len(text) < 1:
                continue

            end = start + duration

            # Mescla micro-segmentos consecutivos muito curtos (< 0.4s) com a frase anterior para leitura fluída
            if cleaned and (start - cleaned[-1]["end"]) < 0.3 and (cleaned[-1]["end"] - cleaned[-1]["start"]) < 1.2:
                cleaned[-1]["end"] = round(end, 2)
                cleaned[-1]["duration"] = round(cleaned[-1]["end"] - cleaned[-1]["start"], 2)
                cleaned[-1]["text"] = f"{cleaned[-1]['text']} {text}"
            else:
                cleaned.append({
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(duration, 2),
                    "text": text,
                })
        return cleaned

    def format_as_text_with_timestamps(self, segments: List[Dict[str, Any]]) -> str:
        lines = []
        for seg in segments:
            start_min = int(seg["start"] // 60)
            start_sec = int(seg["start"] % 60)
            lines.append(f"[{start_min:02d}:{start_sec:02d}] {seg['text']}")
        return "\n".join(lines)
