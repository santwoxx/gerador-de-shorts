"""Ajustes pos-render nos Shorts ja gerados.

Reprocessa um arquivo da pasta outputs/ aplicando velocidade, tom, volume,
espelhamento, zoom e correcao de cor, gerando SEMPRE uma nova versao (o
arquivo original e preservado).
"""

import os
import re
import math
import logging
import threading
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("autoshorts.editor")

DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d+\.?\d*)")
TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

# Faixas aceitas por cada ajuste: (minimo, maximo, padrao)
LIMITS: Dict[str, Tuple[float, float, float]] = {
    "speed": (0.5, 2.0, 1.0),
    "pitch_semitones": (-6.0, 6.0, 0.0),
    "volume": (0.2, 3.0, 1.0),
    "zoom": (1.0, 1.4, 1.0),
    "brightness": (-0.3, 0.3, 0.0),
    "contrast": (0.5, 1.8, 1.0),
    "saturation": (0.0, 2.0, 1.0),
    "grain": (0.0, 25.0, 0.0),
    "trim_start": (0.0, 60.0, 0.0),
    "trim_end": (0.0, 60.0, 0.0),
}


def clamp(name: str, value: Any) -> float:
    low, high, default = LIMITS[name]
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(num) or math.isinf(num):
        return default
    return max(low, min(high, num))


def _atempo_chain(factor: float) -> List[str]:
    """atempo so aceita 0.5-2.0 por instancia; encadeia quando precisa."""
    if abs(factor - 1.0) < 0.001:
        return []
    steps = []
    remaining = factor
    while remaining > 2.0:
        steps.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        steps.append("atempo=0.5")
        remaining /= 0.5
    steps.append(f"atempo={remaining:.6f}")
    return steps


def next_version_name(output_dir: str, filename: str) -> str:
    """short.mp4 -> short_v2.mp4 -> short_v3.mp4 ..."""
    stem, ext = os.path.splitext(filename)
    ext = ext or ".mp4"

    match = re.match(r"^(.*)_v(\d+)$", stem)
    base, version = (match.group(1), int(match.group(2))) if match else (stem, 1)

    for n in range(version + 1, version + 200):
        candidate = f"{base}_v{n}{ext}"
        if not os.path.exists(os.path.join(output_dir, candidate)):
            return candidate
    raise RuntimeError("Limite de versoes atingido para este Short.")


class VideoEditor:
    def __init__(self, output_dir: str, ffmpeg_path: str):
        self.output_dir = output_dir
        self.ffmpeg_path = ffmpeg_path
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    def probe_duration(self, path: str) -> float:
        """Le a duracao pelo proprio ffmpeg (evita depender do ffprobe)."""
        try:
            proc = subprocess.run(
                [self.ffmpeg_path, "-hide_banner", "-i", path],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            match = DURATION_RE.search(proc.stderr or "")
            if match:
                h, m, s = match.groups()
                return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception as e:
            logger.warning("Nao foi possivel ler a duracao de %s: %s", os.path.basename(path), e)
        return 0.0

    # ------------------------------------------------------------------
    def build_filters(self, opts: Dict[str, Any]) -> Tuple[str, str]:
        """Monta as cadeias de filtro de video e de audio."""
        speed = clamp("speed", opts.get("speed", 1.0))
        preserve_pitch = bool(opts.get("preserve_pitch", True))
        pitch = clamp("pitch_semitones", opts.get("pitch_semitones", 0.0))
        volume = clamp("volume", opts.get("volume", 1.0))
        zoom = clamp("zoom", opts.get("zoom", 1.0))
        brightness = clamp("brightness", opts.get("brightness", 0.0))
        contrast = clamp("contrast", opts.get("contrast", 1.0))
        saturation = clamp("saturation", opts.get("saturation", 1.0))
        grain = clamp("grain", opts.get("grain", 0.0))

        vf: List[str] = []
        if opts.get("mirror"):
            vf.append("hflip")

        if zoom > 1.001:
            # Corta o centro e reamplia: zoom real, sem alterar o 1080x1920.
            vf.append(f"crop=iw/{zoom:.4f}:ih/{zoom:.4f}:(iw-ow)/2:(ih-oh)/2")
            vf.append("scale=1080:1920:flags=lanczos")

        if abs(brightness) > 0.001 or abs(contrast - 1.0) > 0.001 or abs(saturation - 1.0) > 0.001:
            vf.append(
                f"eq=brightness={brightness:.4f}:contrast={contrast:.4f}:saturation={saturation:.4f}"
            )

        if grain > 0.1:
            vf.append(f"noise=alls={int(grain)}:allf=t")

        if abs(speed - 1.0) > 0.001:
            vf.append(f"setpts={1.0 / speed:.6f}*PTS")

        vf.append("format=yuv420p")

        # Normaliza para 48kHz: permite usar asetrate com valor fixo.
        af: List[str] = ["aresample=48000"]

        if abs(speed - 1.0) > 0.001:
            if preserve_pitch:
                af.extend(_atempo_chain(speed))
            else:
                # Efeito "fita acelerada": a voz sobe junto com a velocidade.
                af.append(f"asetrate=48000*{speed:.6f}")
                af.append("aresample=48000")

        if abs(pitch) > 0.01:
            ratio = 2.0 ** (pitch / 12.0)
            af.append(f"asetrate=48000*{ratio:.6f}")
            af.append("aresample=48000")
            af.extend(_atempo_chain(1.0 / ratio))

        if abs(volume - 1.0) > 0.001:
            af.append(f"volume={volume:.4f}")

        return ",".join(vf), ",".join(af)

    # ------------------------------------------------------------------
    def edit(
        self,
        input_filename: str,
        opts: Dict[str, Any],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        input_path = os.path.join(self.output_dir, input_filename)
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"Short nao encontrado: {input_filename}")

        source_duration = self.probe_duration(input_path)
        trim_start = clamp("trim_start", opts.get("trim_start", 0.0))
        trim_end = clamp("trim_end", opts.get("trim_end", 0.0))
        speed = clamp("speed", opts.get("speed", 1.0))

        kept = source_duration - trim_start - trim_end if source_duration else 0.0
        if source_duration and kept < 1.0:
            raise ValueError(
                f"Os cortes de inicio/fim nao deixam video suficiente "
                f"(o Short tem {source_duration:.1f}s)."
            )

        output_filename = next_version_name(self.output_dir, input_filename)
        output_path = os.path.join(self.output_dir, output_filename)
        expected_duration = (kept / speed) if kept else 0.0

        vf, af = self.build_filters(opts)

        # -ss e -t precisam vir ANTES do -i: como opcoes de entrada elas contam
        # o tempo do arquivo original. Depois do -i, o -t passaria a limitar a
        # duracao de saida e o corte do fim sairia errado sempre que a
        # velocidade fosse alterada.
        cmd = [self.ffmpeg_path, "-y", "-hide_banner"]
        if trim_start > 0.01:
            cmd += ["-ss", f"{trim_start:.3f}"]
        if kept > 0 and trim_end > 0.01:
            cmd += ["-t", f"{kept:.3f}"]
        cmd += ["-i", input_path]
        cmd += [
            "-vf", vf,
            "-af", af,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "21",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info("FFmpeg (ajustes): %s", " ".join(cmd))
        if progress_callback:
            progress_callback(5, "Aplicando ajustes no Short...")

        stderr_lines: List[str] = []
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, encoding="utf-8", errors="replace",
        )

        def _read_stderr():
            for line in process.stderr:
                stderr_lines.append(line)
                match = TIME_RE.search(line)
                if match and expected_duration > 0 and progress_callback:
                    h, m, s = match.groups()
                    current = int(h) * 3600 + int(m) * 60 + float(s)
                    pct = min(98, max(5, int((current / expected_duration) * 100)))
                    progress_callback(pct, f"Aplicando ajustes ({pct}%)...")

        reader = threading.Thread(target=_read_stderr, daemon=True)
        reader.start()

        try:
            returncode = process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            process.kill()
            raise RuntimeError("O FFmpeg excedeu o tempo limite ao aplicar os ajustes.")
        reader.join(timeout=10)

        if returncode != 0:
            err_text = "".join(stderr_lines[-40:])
            if os.path.exists(output_path):
                os.remove(output_path)
            raise RuntimeError(f"FFmpeg falhou ao aplicar os ajustes (codigo {returncode}): {err_text[-600:]}")

        if not os.path.isfile(output_path) or os.path.getsize(output_path) < 1000:
            raise RuntimeError("A nova versao saiu vazia ou corrompida.")

        if progress_callback:
            progress_callback(100, "Nova versao gerada com sucesso!")

        final_duration = self.probe_duration(output_path) or expected_duration
        return {
            "filename": output_filename,
            "source_filename": input_filename,
            "duration": round(final_duration, 1),
            "source_duration": round(source_duration, 1),
            "size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 2),
        }
