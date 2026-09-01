import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from backend.downloader import YouTubeDownloader
from backend.transcriber import YouTubeTranscriber
from backend.ai_clipper import AIClipper

def test_user_video():
    print("=== Testando Correção com o Vídeo do Usuário (Mf36ifZ3pjM) ===")
    
    url = "https://www.youtube.com/watch?v=Mf36ifZ3pjM"
    downloader = YouTubeDownloader("storage/downloads")
    
    # 1. Extrai metadados
    meta = downloader.extract_info(url)
    print(f"[OK] Metadados extraídos:")
    print(f"  - Título: {meta['title']}")
    print(f"  - Canal: {meta['channel']}")
    print(f"  - Duração: {meta['duration']}s")
    
    # 2. Obtém transcrição / segmentação
    transcriber = YouTubeTranscriber()
    segments = transcriber.get_transcript(url, video_metadata=meta)
    print(f"[OK] Segmentos obtidos: {len(segments)} segmentos")
    print(f"  - Primeiro segmento: {segments[0]}")
    print(f"  - Último segmento: {segments[-1]}")
    assert len(segments) > 0, "Lista de segmentos vazia!"
    
    # 3. Analisa cortes virais
    clipper = AIClipper()
    genre_info = clipper.detect_video_genre(meta, segments)
    print(f"[OK] Gênero detectado: {genre_info['badge']}")
    
    clips = clipper.find_viral_clips(segments, meta, min_duration=25, max_duration=55, max_clips=5, preferred_provider="heuristics")
    print(f"[OK] Cortes virais gerados com sucesso: {len(clips)} cortes")
    for c in clips:
        print(f"  - {c['title']} ({c['start']}s - {c['end']}s, {c['duration']}s) | Score: {c['score']}")
    
    assert len(clips) > 0, "Nenhum corte foi gerado!"
    print("\n🎉 Correção validada com 100% de sucesso!")

if __name__ == "__main__":
    test_user_video()
