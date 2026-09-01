import os
import sys
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import imageio_ffmpeg
from backend.ai_clipper import AIClipper
from backend.video_processor import VideoProcessor
from backend.subtitle_generator import SubtitleGenerator

def test_react_pipeline():
    print("=== Testando Otimização de React / Split-Screen ===")
    
    # 1. Testa Detecção de React
    clipper = AIClipper()
    meta_react = {
        "title": "CASIMIRO REAGE AOS PIORES RESTAURANTES DO BRASIL",
        "channel": "Cortes do Casimito",
        "description": "Casimiro reage e comenta vídeo hilário no react ao vivo na twitch."
    }
    segments = [{"start": 0.0, "end": 10.0, "text": "Olha essa comida mano, que absurdo kkkk"}]
    
    genre_info = clipper.detect_video_genre(meta_react, segments)
    print(f"[OK] Detecção de gênero: {genre_info['badge']}")
    assert genre_info['is_react'] is True, "Falha na detecção de React!"
    assert genre_info['suggested_layout'] == "react_split", "Layout sugerido deve ser react_split!"

    # 2. Testa Renderização FFmpeg do modo react_split
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs("storage/downloads", exist_ok=True)
    os.makedirs("storage/outputs", exist_ok=True)
    test_input = "storage/downloads/test_video.mp4"

    if not os.path.exists(test_input):
        gen_cmd = [
            ffmpeg_exe, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-c:v", "libx264", "-c:a", "aac",
            test_input
        ]
        subprocess.run(gen_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    sub_gen = SubtitleGenerator("storage/subtitles")
    ass_path = sub_gen.generate_ass_subtitles(segments, 0.0, 5.0, style_preset="yellow_viral")

    proc = VideoProcessor("storage/outputs")
    output_react_path = proc.process_short(
        input_video_path=test_input,
        output_filename="test_react_short.mp4",
        start_time=0.0,
        end_time=5.0,
        layout_mode="react_split",
        ass_subtitles_path=ass_path,
        watermark_text="@CanalReact",
        watermark_position="top_right",
        react_cam_pos="bottom_right",
        react_cam_order="cam_top_content_bottom",
        react_ratio="50_50"
    )

    assert os.path.exists(output_react_path), "Vídeo react_split não foi gerado!"
    size = os.path.getsize(output_react_path)
    print(f"[OK] Short React Split-Screen renderizado com sucesso: {output_react_path} ({size} bytes)")
    print("\n🎉 Teste do Modo React 100% aprovado!")

if __name__ == "__main__":
    test_react_pipeline()
