import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import imageio_ffmpeg

from backend.transcriber import YouTubeTranscriber
from backend.ai_clipper import AIClipper
from backend.subtitle_generator import SubtitleGenerator
from backend.video_processor import VideoProcessor

def test_pipeline():
    print("=== Testando Pipeline do AutoShorts AI ===")
    
    # 1. Verifica FFmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"[OK] FFmpeg detectado em: {ffmpeg_exe}")
    
    # 2. Testa Transcriber com ID de vídeo conhecido (ex: TED Talk ou vídeo comum)
    transcriber = YouTubeTranscriber()
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id = transcriber.extract_video_id(test_url)
    assert video_id == "dQw4w9WgXcQ", f"Erro no extrator de ID: {video_id}"
    print(f"[OK] Extrator de ID YouTube: {video_id}")
    
    # 3. Testa Motor Heurístico Local com transcrição simulada
    sample_segments = [
        {"start": 0.0, "end": 4.5, "duration": 4.5, "text": "Você já se perguntou qual é o maior segredo para ter sucesso na internet?"},
        {"start": 4.5, "end": 9.0, "duration": 4.5, "text": "Muitas pessoas cometem um erro gravíssimo todos os dias e nunca percebem."},
        {"start": 9.0, "end": 15.0, "duration": 6.0, "text": "O primeiro passo é focar em retenção de atenção nos primeiros três segundos."},
        {"start": 15.0, "end": 22.0, "duration": 7.0, "text": "Quando você cria um gancho irresistível, o algoritmo entrega seu vídeo para milhares de pessoas."},
        {"start": 22.0, "end": 32.0, "duration": 10.0, "text": "E a verdade é que isso funciona tanto no Shorts quanto no TikTok e Instagram Reels!"},
        {"start": 32.0, "end": 42.0, "duration": 10.0, "text": "Portanto, aplique essa dica hoje mesmo e veja seus resultados explodirem!"}
    ]
    
    clipper = AIClipper()
    meta = {"title": "O Segredo do Sucesso", "channel": "Canal Teste", "duration": 42.0}
    clips = clipper.find_viral_clips(sample_segments, meta, min_duration=20, max_duration=45, max_clips=2, preferred_provider="heuristics")
    
    print(f"[OK] Motor Heurístico retornou {len(clips)} cortes:")
    for c in clips:
        print(f"  - Título: {c['title']} | Score: {c['score']} | Tempo: {c['start']}s a {c['end']}s ({c['duration']}s)")
        print(f"    Gancho: {c['hook']}")
    
    assert len(clips) > 0, "Motor heurístico não retornou cortes!"

    # 4. Testa Geração de Legenda ASS
    sub_gen = SubtitleGenerator("storage/subtitles")
    ass_file = sub_gen.generate_ass_subtitles(sample_segments, clip_start=0.0, clip_end=42.0, style_preset="yellow_viral")
    assert os.path.exists(ass_file), "Arquivo de legendas ASS não foi gerado!"
    print(f"[OK] Legenda ASS gerada com sucesso em: {ass_file}")

    print("\n✅ Todos os testes de unidade passaram com sucesso!")

if __name__ == "__main__":
    test_pipeline()
