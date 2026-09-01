import os
import re
import shutil
import subprocess
import threading
import logging
from typing import Optional, Callable
import imageio_ffmpeg

logger = logging.getLogger("autoshorts.video")


class VideoProcessor:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.ffmpeg_path = self._detect_ffmpeg()

    def _detect_ffmpeg(self) -> str:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            logger.info("FFmpeg do sistema: %s", system_ffmpeg)
            return system_ffmpeg
        try:
            path = imageio_ffmpeg.get_ffmpeg_exe()
            logger.info("FFmpeg do imageio: %s", path)
            return path
        except Exception:
            logger.warning("FFmpeg nao encontrado, usando 'ffmpeg' do PATH")
            return "ffmpeg"

    def _sanitize_path_for_ffmpeg(self, path: str) -> str:
        clean = os.path.abspath(path).replace("\\", "/")
        if len(clean) > 1 and clean[1] == ":":
            clean = clean[0] + "\\:" + clean[2:]
        return clean.replace("'", "\\'")

    def process_short(
        self,
        input_video_path: str,
        output_filename: str,
        start_time: float,
        end_time: float,
        layout_mode: str = "blur_bg",
        ass_subtitles_path: Optional[str] = None,
        watermark_text: Optional[str] = None,
        watermark_position: str = "top_right",
        watermark_image_path: Optional[str] = None,
        watermark_scale: int = 250,
        watermark_opacity: float = 0.9,
        react_cam_pos: str = "bottom_right",
        react_cam_order: str = "cam_top_content_bottom",
        react_ratio: str = "50_50",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> str:
        output_path = os.path.join(self.output_dir, output_filename)
        duration = max(1.0, end_time - start_time)

        if not os.path.isfile(input_video_path):
            raise FileNotFoundError(f"Video de entrada nao encontrado: {input_video_path}")

        if progress_callback:
            progress_callback(5, "Iniciando renderizacao de video...")

        filter_chains = []
        last_v = "0:v"

        if layout_mode == "react_split":
            # Configuração das alturas com base no ratio
            if react_ratio == "40_60":
                h_top, h_bottom = 768, 1152
            elif react_ratio == "60_40":
                h_top, h_bottom = 1152, 768
            else: # 50_50
                h_top, h_bottom = 960, 960

            # Crop da webcam a partir do vídeo 16:9 original
            cam_crops = {
                "bottom_right": "crop=iw*0.38:ih*0.50:iw*0.62:ih*0.50",
                "bottom_left": "crop=iw*0.38:ih*0.50:0:ih*0.50",
                "top_right": "crop=iw*0.38:ih*0.50:iw*0.62:0",
                "top_left": "crop=iw*0.38:ih*0.50:0:0",
                "center_top": "crop=iw*0.42:ih*0.50:iw*0.29:0",
                "center_bottom": "crop=iw*0.42:ih*0.50:iw*0.29:ih*0.50",
                "left_side": "crop=iw*0.50:ih:0:0",
                "right_side": "crop=iw*0.50:ih:iw*0.50:0"
            }
            cam_crop_expr = cam_crops.get(react_cam_pos, "crop=iw*0.38:ih*0.50:iw*0.62:ih*0.50")

            if react_cam_order == "cam_top_content_bottom":
                h_cam = h_top
                h_content = h_bottom
                filter_chains.append(
                    f"[{last_v}]split=2[v_raw_cam][v_raw_content];"
                    f"[v_raw_cam]{cam_crop_expr},scale=1080:{h_cam}:force_original_aspect_ratio=increase,crop=1080:{h_cam}[v_cam];"
                    f"[v_raw_content]split=2[c_bg][c_fg];"
                    f"[c_bg]scale=1080:{h_content}:force_original_aspect_ratio=increase,crop=1080:{h_content},boxblur=15:4,eq=brightness=-0.18[c_bg_out];"
                    f"[c_fg]scale=1080:-2:flags=lanczos[c_fg_out];"
                    f"[c_bg_out][c_fg_out]overlay=(W-w)/2:(H-h)/2[v_content];"
                    f"[v_cam][v_content]vstack=inputs=2[v_stack_raw];"
                    f"[v_stack_raw]drawbox=x=0:y={h_cam}-2:w=1080:h=4:color=white@0.4:t=fill[v_layout]"
                )
            else: # content_top_cam_bottom
                h_content = h_top
                h_cam = h_bottom
                filter_chains.append(
                    f"[{last_v}]split=2[v_raw_cam][v_raw_content];"
                    f"[v_raw_content]split=2[c_bg][c_fg];"
                    f"[c_bg]scale=1080:{h_content}:force_original_aspect_ratio=increase,crop=1080:{h_content},boxblur=15:4,eq=brightness=-0.18[c_bg_out];"
                    f"[c_fg]scale=1080:-2:flags=lanczos[c_fg_out];"
                    f"[c_bg_out][c_fg_out]overlay=(W-w)/2:(H-h)/2[v_content];"
                    f"[v_raw_cam]{cam_crop_expr},scale=1080:{h_cam}:force_original_aspect_ratio=increase,crop=1080:{h_cam}[v_cam];"
                    f"[v_content][v_cam]vstack=inputs=2[v_stack_raw];"
                    f"[v_stack_raw]drawbox=x=0:y={h_content}-2:w=1080:h=4:color=white@0.4:t=fill[v_layout]"
                )
        elif layout_mode == "center_crop":
            filter_chains.append(
                f"[{last_v}]crop=ih*(9/16):ih:(iw-ow)/2:0,scale=1080:1920:flags=lanczos[v_layout]"
            )
        elif layout_mode == "fit_letterbox":
            filter_chains.append(
                f"[{last_v}]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black[v_layout]"
            )
        else: # blur_bg default
            filter_chains.append(
                f"[{last_v}]split=2[v_bg_in][v_fg_in];"
                f"[v_bg_in]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.15[bg];"
                f"[v_fg_in]scale=1080:-2:flags=lanczos[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v_layout]"
            )
        last_v = "v_layout"

        if watermark_image_path and os.path.isfile(watermark_image_path):
            clean_img = self._sanitize_path_for_ffmpeg(watermark_image_path)
            
            if watermark_position == "full_916":
                pos_expr = "0:0"
                scale_filter = "scale=1080:1920"
            else:
                pos_expr = {
                    "top_right": "W-w-50:80",
                    "top_left": "50:80",
                    "bottom_right": "W-w-50:H-h-200",
                    "bottom_left": "50:H-h-200",
                    "top_center": "(W-w)/2:80",
                    "bottom_center": "(W-w)/2:H-h-250",
                    "center": "(W-w)/2:(H-h)/2",
                }.get(watermark_position, "W-w-50:80")
                wm_w = max(50, min(1080, int(watermark_scale)))
                scale_filter = f"scale={wm_w}:-1"

            alpha_val = max(0.05, min(1.0, float(watermark_opacity)))

            filter_chains.append(
                f"movie='{clean_img}',{scale_filter},format=rgba,colorchannelmixer=aa={alpha_val}[wm_img];"
                f"[{last_v}][wm_img]overlay={pos_expr}[v_wm]"
            )
            last_v = "v_wm"

        elif watermark_text and watermark_text.strip():
            clean_text = watermark_text.strip()
            for char in ("\\", "'", ":"):
                clean_text = clean_text.replace(char, f"\\{char}")

            pos_x, pos_y = {
                "top_right": ("w-tw-50", "80"),
                "top_left": ("50", "80"),
                "bottom_right": ("w-tw-50", "h-th-200"),
                "bottom_left": ("50", "h-th-200"),
                "top_center": ("(w-tw)/2", "80"),
                "bottom_center": ("(w-tw)/2", "h-th-250"),
                "center": ("(w-tw)/2", "(h-th)/2"),
            }.get(watermark_position, ("w-tw-50", "80"))

            alpha_val = max(0.05, min(1.0, float(watermark_opacity)))
            font_sz = max(18, min(90, int(watermark_scale / 6))) if watermark_scale else 36

            filter_chains.append(
                f"[{last_v}]drawtext=text='{clean_text}':font='Segoe UI,Arial':fontsize={font_sz}:"
                f"fontcolor=white@{alpha_val}:box=1:boxcolor=black@{alpha_val*0.65}:boxborderw=16:"
                f"x={pos_x}:y={pos_y}[v_wm]"
            )
            last_v = "v_wm"

        if ass_subtitles_path and os.path.isfile(ass_subtitles_path):
            clean_ass = self._sanitize_path_for_ffmpeg(ass_subtitles_path)
            filter_chains.append(f"[{last_v}]ass='{clean_ass}'[v_out]")
        else:
            filter_chains.append(f"[{last_v}]null[v_out]")
        last_v = "v_out"

        full_filter = ";".join(filter_chains)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", input_video_path,
            "-filter_complex", full_filter,
            "-map", f"[{last_v}]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "21",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info("FFmpeg cmd: %s", " ".join(cmd))

        stderr_lines: list = []

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
            )

            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

            def _read_stderr():
                for line in process.stderr:
                    stderr_lines.append(line)
                    match = time_pattern.search(line)
                    if match:
                        h, m, s = match.groups()
                        current = int(h) * 3600 + int(m) * 60 + float(s)
                        pct = min(98, max(5, int((current / duration) * 100)))
                        if progress_callback:
                            progress_callback(pct, f"Renderizando corte ({pct}%)...")

            reader = threading.Thread(target=_read_stderr, daemon=True)
            reader.start()
            reader.join(timeout=300)

            returncode = process.wait(timeout=60)

            if returncode != 0:
                err_text = "".join(stderr_lines[-50:])
                raise RuntimeError(f"FFmpeg falhou (codigo {returncode}): {err_text}")

        except subprocess.TimeoutExpired:
            process.kill()
            raise RuntimeError("FFmpeg excedeu o tempo limite (5 minutos)")

        if progress_callback:
            progress_callback(100, "Short gerado com sucesso!")

        if not os.path.isfile(output_path) or os.path.getsize(output_path) < 1000:
            raise RuntimeError(f"Arquivo de saida invalido ou muito pequeno: {output_path}")

        return output_path
