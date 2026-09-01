import os
import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("autoshorts.subtitles")


class SubtitleGenerator:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_ass_subtitles(
        self,
        transcript_segments: List[Dict[str, Any]],
        clip_start: float,
        clip_end: float,
        style_preset: str = "yellow_viral",
        output_filename: Optional[str] = None,
        chunk_size: int = 3,
    ) -> str:
        if not output_filename:
            output_filename = f"subs_{int(clip_start)}_{int(clip_end)}.ass"

        target_path = os.path.join(self.output_dir, output_filename)

        if not transcript_segments:
            logger.warning("Nenhum segmento de transcricao para gerar legendas")
            self._write_empty_ass(target_path)
            return target_path

        clip_events = []
        for seg in transcript_segments:
            seg_start = seg["start"]
            seg_end = seg["end"]

            if seg_end <= clip_start or seg_start >= clip_end:
                continue

            rel_start = max(0.0, seg_start - clip_start)
            rel_end = min(clip_end - clip_start, seg_end - clip_start)

            if rel_end <= rel_start:
                continue

            words = seg["text"].strip().split()
            if not words:
                continue

            safe_chunk = max(2, min(chunk_size, len(words)))
            total_chunks = math.ceil(len(words) / safe_chunk)
            chunk_duration = (rel_end - rel_start) / max(1, total_chunks)

            for i in range(total_chunks):
                c_words = words[i * safe_chunk : (i + 1) * safe_chunk]
                c_start = rel_start + (i * chunk_duration)
                c_end = min(rel_end, c_start + chunk_duration)
                c_text = " ".join(c_words).upper()

                if c_text:
                    clip_events.append({
                        "start": c_start,
                        "end": c_end,
                        "text": c_text,
                    })

        style_header = self._get_ass_style_header(style_preset)

        ass_lines = [
            "[Script Info]",
            "Title: AutoShorts AI Viral Subtitles",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: TV.601",
            "PlayResX: 1080",
            "PlayResY: 1920",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            style_header,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        for ev in clip_events:
            start_str = self._format_ass_time(ev["start"])
            end_str = self._format_ass_time(ev["end"])
            formatted_text = self._apply_text_effect(ev["text"], style_preset)
            ass_lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{formatted_text}")

        with open(target_path, "w", encoding="utf-8-sig") as f:
            f.write("\r\n".join(ass_lines) + "\r\n")

        logger.info("Legenda ASS gerada: %s (%d eventos)", target_path, len(clip_events))
        return target_path

    def _write_empty_ass(self, path: str):
        content = (
            "[Script Info]\r\n"
            "Title: AutoShorts AI\r\n"
            "ScriptType: v4.00+\r\n"
            "PlayResX: 1080\r\n"
            "PlayResY: 1920\r\n"
            "\r\n"
            "[V4+ Styles]\r\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\r\n"
            f"{self._get_ass_style_header('yellow_viral')}\r\n"
            "\r\n"
            "[Events]\r\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\r\n"
        )
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(content)

    def _get_ass_style_header(self, preset: str) -> str:
        font = "Arial Black"
        fontsize = "72"
        margin_v = "520"

        styles = {
            "yellow_viral": f"Style: Default,{font},{fontsize},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5.0,2.0,2,80,80,{margin_v},1",
            "neon_cyber": f"Style: Default,{font},74,&H00FFFF00,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,1,0,1,6.0,3.0,2,80,80,{margin_v},1",
            "red_impact": f"Style: Default,{font},74,&H000022FF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,1,0,1,6.0,2.0,2,80,80,{margin_v},1",
            "minimal_white": f"Style: Default,Segoe UI,66,&H00FFFFFF,&H00FFFFFF,&H00111111,&HB0000000,-1,0,0,0,100,100,0,0,1,3.5,1.5,2,80,80,{margin_v},1",
        }

        return styles.get(preset, styles["yellow_viral"])

    def _apply_text_effect(self, text: str, preset: str) -> str:
        words = text.split()
        if not words:
            return text

        # Animação sutil de Pop-in Zoom (115% -> 100% em 90ms) para retenção de atenção estilo MrBeast/Hormozi
        anim_prefix = r"{\fscx115\fscy115\t(0,90,\fscx100\fscy100)}"

        if preset == "yellow_viral":
            if len(words) == 1:
                return f"{anim_prefix}{{\\c&H0000FFFF&}}{words[0]}"
            return f"{anim_prefix}{{\\c&H0000FFFF&}}{words[0]}{{\\c&H00FFFFFF&}} {' '.join(words[1:])}"
        elif preset == "neon_cyber":
            if len(words) == 1:
                return f"{anim_prefix}{{\\c&H00FFFF00&}}{words[0]}"
            return f"{anim_prefix}{{\\c&H00FFFF00&}}{words[0]}{{\\c&H00FFFFFF&}} {' '.join(words[1:])}"
        elif preset == "red_impact":
            if len(words) == 1:
                return f"{anim_prefix}{{\\c&H000022FF&}}{words[0]}"
            return f"{anim_prefix}{{\\c&H000022FF&}}{words[0]}{{\\c&H00FFFFFF&}} {' '.join(words[1:])}"

        return f"{anim_prefix}{text}"

    def _format_ass_time(self, seconds: float) -> str:
        seconds = max(0.0, seconds)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int(round((seconds - int(seconds)) * 100))
        if centis >= 100:
            centis = 99
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"
