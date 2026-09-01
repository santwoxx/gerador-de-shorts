import os
import json
import re
import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("autoshorts.aiclipper")


class AIClipper:
    def __init__(self, gemini_api_key: Optional[str] = None, groq_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")

    def detect_video_genre(self, metadata: Dict[str, Any], transcript_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detecta se o vídeo é um React, Gameplay, Podcast ou vídeo padrão para sugerir o melhor layout."""
        title = (metadata.get("title") or "").lower()
        desc = (metadata.get("description") or "").lower()
        channel = (metadata.get("channel") or "").lower()

        sample_text = " ".join(s["text"] for s in transcript_segments[:25]).lower() if transcript_segments else ""
        combined = f"{title} {desc} {channel} {sample_text}"

        react_keywords = [
            "react", "reagindo", "reação", "reaction", "reagi", "reagiu", 
            "assistindo", "analisando", "opinando", "comentando o", "vendo o",
            "streamer", "twitch", "gameplay", "casimiro", "cazé", "gaules", 
            "alanzoka", "cellbit", "coringa", "loud", "felca", "orochinho"
        ]

        podcast_keywords = [
            "podcast", "podpah", "flow", "inteligencia ltda", "venus", "entrevista",
            "conversa com", "bate papo", "cortes do flow", "cortes podpah"
        ]

        if any(kw in combined for kw in react_keywords):
            return {
                "genre": "react",
                "is_react": True,
                "suggested_layout": "react_split",
                "suggested_cam_pos": "bottom_right",
                "badge": "🎬 React / Streamer Detectado",
                "tip": "Recomendamos o layout Split-Screen 9:16 (Câmera do Streamer + Conteúdo)."
            }
        elif any(kw in combined for kw in podcast_keywords):
            return {
                "genre": "podcast",
                "is_react": False,
                "suggested_layout": "blur_bg",
                "suggested_cam_pos": "bottom_right",
                "badge": "🎙️ Podcast / Conversa",
                "tip": "Formato Fundo Desfocado ou Recorte Central recomendado."
            }
        else:
            return {
                "genre": "general",
                "is_react": False,
                "suggested_layout": "blur_bg",
                "suggested_cam_pos": "bottom_right",
                "badge": "✨ Vídeo Geral",
                "tip": "Formato Fundo Desfocado padrão aplicado."
            }

    def find_viral_clips(
        self,
        transcript_segments: List[Dict[str, Any]],
        video_metadata: Dict[str, Any],
        min_duration: int = 30,
        max_duration: int = 60,
        max_clips: int = 5,
        preferred_provider: str = "auto",
        clip_mode: str = "viral_highlights",
        start_clip_offset: int = 1,
    ) -> List[Dict[str, Any]]:
        if not transcript_segments:
            return []

        total_video_duration = float(video_metadata.get("duration", 0) or 0)
        if not total_video_duration and transcript_segments:
            total_video_duration = transcript_segments[-1]["end"]

        # Se o usuário escolheu o modo Sequencial / Fatiamento Completo por Lotes
        if clip_mode == "sequential":
            logger.info("Modo de fatiamento sequencial por lotes ativado (Shorts %d em diante, max %d)", start_clip_offset, max_clips)
            return self._slice_sequential(transcript_segments, video_metadata, min_duration, max_duration, max_clips, total_video_duration, start_clip_offset)

        if preferred_provider in ("auto", "gemini") and self.gemini_api_key:
            try:
                clips = self._analyze_with_gemini(transcript_segments, video_metadata, min_duration, max_duration, max_clips)
                if clips:
                    return self._enrich_and_validate_clips(clips, transcript_segments, total_video_duration)
            except Exception as e:
                logger.warning("Gemini falhou: %s", e)

        if preferred_provider in ("auto", "groq") and self.groq_api_key:
            try:
                clips = self._analyze_with_groq(transcript_segments, video_metadata, min_duration, max_duration, max_clips)
                if clips:
                    return self._enrich_and_validate_clips(clips, transcript_segments, total_video_duration)
            except Exception as e:
                logger.warning("Groq falhou: %s", e)

        logger.info("Usando Motor Heuristico Local")
        return self._analyze_with_heuristics(transcript_segments, video_metadata, min_duration, max_duration, max_clips)

    def _slice_sequential(
        self,
        transcript_segments: List[Dict[str, Any]],
        video_metadata: Dict[str, Any],
        min_duration: int,
        max_duration: int,
        max_clips: int,
        total_duration: float,
        start_clip_offset: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Fatia o vídeo sequencialmente por lotes com suporte a offset inicial (ex: partes 1-5, depois 6-10).
        """
        if total_duration <= 0:
            total_duration = transcript_segments[-1]["end"] if transcript_segments else 600.0

        target_step = float(max_duration)
        if target_step <= 0:
            target_step = 60.0

        total_parts = max(1, math.ceil(total_duration / target_step))
        start_idx = max(0, start_clip_offset - 1)
        end_idx = min(total_parts, start_idx + (max_clips if max_clips > 0 else total_parts))

        clips = []
        for i in range(start_idx, end_idx):
            start = round(i * target_step, 2)
            end = round(min(total_duration, (i + 1) * target_step), 2)
            dur = round(end - start, 2)

            if dur < 5.0 and len(clips) > 0:
                break

            snippet_parts = []
            first_sentence = ""
            for seg in transcript_segments:
                if seg["end"] >= start and seg["start"] <= end:
                    snippet_parts.append(seg["text"])
                    if not first_sentence:
                        first_sentence = seg["text"]

            snippet = " ".join(snippet_parts)
            context_title = self._generate_fallback_title(snippet, first_sentence, i + 1)
            clean_title = f"PARTE {i+1}/{total_parts} • {context_title}"

            clips.append({
                "id": f"clip_seq_{i+1}",
                "title": clean_title,
                "start": start,
                "end": end,
                "duration": dur,
                "score": 90 - (i % 8),
                "hook": first_sentence[:80] + ("..." if len(first_sentence) > 80 else "") or f"Parte {i+1} do vídeo",
                "explanation": f"Fatia sequencial contínua cobrindo {start}s até {end}s ({dur}s).",
                "transcript_snippet": snippet[:200] + "..." if len(snippet) > 200 else snippet,
                "virality_score": 85,
                "reasoning": f"Parte {i+1} de {total_parts} no fatiamento por lotes ({int(start//60)}m{int(start%60)}s ao {int(end//60)}m{int(end%60)}s)",
            })

        return clips

    def _build_prompt(
        self,
        transcript_segments: List[Dict[str, Any]],
        video_metadata: Dict[str, Any],
        min_duration: int,
        max_duration: int,
        max_clips: int,
    ) -> str:
        formatted = "\n".join(
            f"[{s['start']:.1f}s - {s['end']:.1f}s] {s['text']}" for s in transcript_segments
        )
        if len(formatted) > 40000:
            formatted = formatted[:40000] + "\n... (transcricao truncada)"

        return f"""Voce e um especialista em crescimento no YouTube Shorts, TikTok e Instagram Reels.
Analise a transcricao e selecione os {max_clips} MELHORES CORTES VIRAIS para Shorts verticais.

DADOS DO VIDEO:
- Titulo: {video_metadata.get('title', 'Video do YouTube')}
- Canal: {video_metadata.get('channel', 'Canal')}
- Duracao Total: {video_metadata.get('duration', 0)} segundos

REGRAS:
1. Duracao: Entre {min_duration} e {max_duration} segundos.
2. Estrutura: GANCHO (0-4s) + DESENVOLVIMENTO + CLIMAX.
3. Nao cortar no meio de frases.
4. Titulos apelativos, pontuacao de viralidade 0-100.
5. Responda APENAS com JSON valido, sem texto antes ou depois.

Formato:
[
  {{
    "title": "TITULO VIRAL",
    "start": 12.5,
    "end": 58.0,
    "score": 96,
    "hook": "Frase de impacto inicial",
    "explanation": "Por que e bom"
  }}
]

TRANSCRICAO:
{formatted}"""

    def _analyze_with_gemini(
        self,
        transcript_segments: List[Dict[str, Any]],
        video_metadata: Dict[str, Any],
        min_duration: int,
        max_duration: int,
        max_clips: int,
    ) -> List[Dict[str, Any]]:
        from google import genai

        client = genai.Client(api_key=self.gemini_api_key)
        prompt = self._build_prompt(transcript_segments, video_metadata, min_duration, max_duration, max_clips)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return self._extract_json_from_response(response.text)

    def _analyze_with_groq(
        self,
        transcript_segments: List[Dict[str, Any]],
        video_metadata: Dict[str, Any],
        min_duration: int,
        max_duration: int,
        max_clips: int,
    ) -> List[Dict[str, Any]]:
        import requests

        prompt = self._build_prompt(transcript_segments, video_metadata, min_duration, max_duration, max_clips)
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "Responda APENAS em JSON valido."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.5,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        return self._extract_json_from_response(content)

    def _analyze_with_heuristics(
        self,
        transcript_segments: List[Dict[str, Any]],
        video_metadata: Dict[str, Any],
        min_duration: int,
        max_duration: int,
        max_clips: int,
    ) -> List[Dict[str, Any]]:
        hook_keywords = {
            "como": 3, "por que": 4, "porque": 3, "qual": 3, "segredo": 6,
            "nunca": 5, "sempre": 3, "verdade": 5, "mentira": 5, "descobri": 6,
            "olha so": 5, "veja": 4, "dica": 5, "erro": 6, "atencao": 5,
            "cuidado": 6, "incrivel": 5, "ninguem": 5, "melhor": 4, "pior": 4,
            "dinheiro": 4, "resultado": 4, "funciona": 4, "importante": 4,
            "estrategia": 4, "nao faca": 6, "aconteceu": 5,
        }

        n = len(transcript_segments)
        scored_windows: List[Dict[str, Any]] = []

        for i in range(n):
            start_seg = transcript_segments[i]
            start_time = start_seg["start"]
            collected_text = []

            for j in range(i, n):
                seg = transcript_segments[j]
                collected_text.append(seg["text"])
                duration = seg["end"] - start_time

                if duration < min_duration:
                    continue

                if duration > max_duration:
                    break

                full_text = " ".join(collected_text)
                score = self._calculate_heuristic_score(full_text, collected_text[0], duration, hook_keywords)

                scored_windows.append({
                    "start": round(start_time, 2),
                    "end": round(seg["end"], 2),
                    "duration": round(duration, 2),
                    "score": score,
                    "text": full_text,
                    "first_sentence": collected_text[0],
                })

        scored_windows.sort(key=lambda x: x["score"], reverse=True)
        selected: List[Dict[str, Any]] = []

        for w in scored_windows:
            if len(selected) >= max_clips:
                break

            overlaps = False
            for sc in selected:
                if not (w["end"] < sc["start"] + 15 or w["start"] > sc["end"] - 15):
                    overlaps = True
                    break

            if not overlaps:
                title = self._generate_fallback_title(w["text"], w["first_sentence"], len(selected) + 1)
                hook = w["first_sentence"][:80]
                if len(w["first_sentence"]) > 80:
                    hook += "..."

                selected.append({
                    "title": title,
                    "start": w["start"],
                    "end": w["end"],
                    "duration": w["duration"],
                    "score": min(99, max(65, int(w["score"]))),
                    "hook": hook,
                    "explanation": "Momento com alto ritmo de fala, palavras-chave de retencao e estrutura narrativa coesa.",
                    "transcript_snippet": w["text"],
                })

        if not selected and transcript_segments:
            total_dur = transcript_segments[-1]["end"]
            step = max(30.0, min(55.0, total_dur / max(1, max_clips)))
            current = 0.0
            idx = 1
            while current < total_dur and len(selected) < max_clips:
                c_end = min(total_dur, current + step)
                if c_end - current >= 15:
                    selected.append({
                        "title": f"MOMENTO EPICO #{idx}",
                        "start": round(current, 2),
                        "end": round(c_end, 2),
                        "duration": round(c_end - current, 2),
                        "score": 85 + (idx % 10),
                        "hook": "Destaque selecionado do video",
                        "explanation": "Trecho selecionado para formato vertical.",
                        "transcript_snippet": "",
                    })
                    idx += 1
                current += step

        return self._enrich_and_validate_clips(selected, transcript_segments, video_metadata.get("duration", 0))

    def _calculate_heuristic_score(self, text: str, first_sentence: str, duration: float, keywords: Dict[str, int]) -> float:
        text_lower = text.lower()
        first_lower = first_sentence.lower()
        score = 50.0

        for kw, weight in keywords.items():
            if kw in text_lower:
                score += weight * 1.5
            if kw in first_lower:
                score += weight * 3.0

        score += min(15, text.count("?") * 4)
        score += min(10, text.count("!") * 2)

        words = text.split()
        wps = len(words) / max(1.0, duration)
        if 2.2 <= wps <= 3.8:
            score += 15
        elif wps < 1.5:
            score -= 10

        return min(98.0, score)

    def _generate_fallback_title(self, full_text: str, first_sentence: str, index: int) -> str:
        clean = re.sub(r"[^\w\s]", "", first_sentence).strip()
        words = clean.split()
        if len(words) >= 3:
            return " ".join(words[:6]).upper()
        return f"MOMENTO IMPERDIVEL #{index}"

    def _extract_json_from_response(self, text: str) -> List[Dict[str, Any]]:
        try:
            m = re.search(r"```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```", text, re.DOTALL)
            if m:
                return json.loads(m.group(1))

            m2 = re.search(r"(\[\s*\{.*\}\s*\])", text, re.DOTALL)
            if m2:
                return json.loads(m2.group(1))

            return json.loads(text.strip())
        except Exception:
            logger.warning("Falha ao extrair JSON da resposta da IA")
            return []

    def _enrich_and_validate_clips(
        self,
        clips: List[Dict[str, Any]],
        transcript_segments: List[Dict[str, Any]],
        total_duration: float,
    ) -> List[Dict[str, Any]]:
        valid = []
        for idx, clip in enumerate(clips):
            start = max(0.0, float(clip.get("start", 0.0)))
            end = float(clip.get("end", start + 45.0))
            if total_duration > 0 and end > total_duration:
                end = total_duration
            if end <= start:
                end = start + 30.0

            duration = round(end - start, 2)

            snippet_parts = [
                seg["text"]
                for seg in transcript_segments
                if seg["end"] >= start and seg["start"] <= end
            ]

            valid.append({
                "id": f"clip_{idx + 1}",
                "title": str(clip.get("title", f"CORTE VIRAL #{idx + 1}")).strip(),
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": duration,
                "score": int(clip.get("score", 88)),
                "hook": str(clip.get("hook", "Gancho do corte")).strip(),
                "explanation": str(clip.get("explanation", "Corte de alta retencao")).strip(),
                "transcript_snippet": " ".join(snippet_parts),
            })
        return valid
