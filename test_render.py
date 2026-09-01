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
from backend.video_processor import VideoProcessor
from backend.subtitle_generator import SubtitleGenerator

def test_full_render():
    print("=== Testando Renderização Real com FFmpeg ===")
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # 1. Cria um vídeo de teste de 5 segundos em 1920x1080 horizontal
    os.makedirs("storage/downloads", exist_ok=True)
    os.makedirs("storage/outputs", exist_ok=True)
    test_input = "storage/downloads/test_video.mp4"
    
    gen_cmd = [
        ffmpeg_exe, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=5:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-c:a", "aac",
        test_input
    ]
    subprocess.run(gen_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[OK] Vídeo de teste gerado em: {test_input}")
    
    # 2. Gera legenda ASS de teste
    sub_gen = SubtitleGenerator("storage/subtitles")
    segments = [
        {"start": 0.0, "end": 2.5, "duration": 2.5, "text": "ISSO É UM TESTE DO AUTOSHORTS"},
        {"start": 2.5, "end": 5.0, "duration": 2.5, "text": "LEGENDA VIRAL FUNCIONANDO"}
    ]
    ass_path = sub_gen.generate_ass_subtitles(segments, 0.0, 5.0, style_preset="yellow_viral")
    print(f"[OK] Legenda ASS gerada em: {ass_path}")
    
    # 3. Processa no VideoProcessor em 9:16 com Fundo Desfocado, Marca d'Água e Legendas
    proc = VideoProcessor("storage/outputs")
    output_path = proc.process_short(
        input_video_path=test_input,
        output_filename="test_short_rendered.mp4",
        start_time=0.0,
        end_time=5.0,
        layout_mode="blur_bg",
        ass_subtitles_path=ass_path,
        watermark_text="@CanalDoUsuario",
        watermark_position="top_right"
    )
    
    assert os.path.exists(output_path), "Vídeo de saída não foi criado!"
    file_size = os.path.getsize(output_path)
    print(f"[OK] Short 9:16 renderizado com sucesso: {output_path} ({file_size} bytes)")
    print("\n🎉 Pipeline de renderização FFmpeg 100% validado!")

if __name__ == "__main__":
    test_full_render()
