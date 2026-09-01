import os
import json
import logging
import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("autoshorts.youtube_publisher")

YT_AUTH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "yt_auth")
os.makedirs(YT_AUTH_DIR, exist_ok=True)
CREDENTIALS_FILE = os.path.join(YT_AUTH_DIR, "client_secrets.json")
TOKEN_FILE = os.path.join(YT_AUTH_DIR, "token.json")


class YouTubePublisher:
    def __init__(self):
        pass

    def generate_shorts_metadata(
        self,
        base_title: str,
        transcript_snippet: str = "",
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gera título viral, descrição persuasiva, hashtags e tags otimizadas para YouTube Shorts usando IA.
        """
        # Se tiver Gemini API Key
        if gemini_api_key:
            try:
                from google import genai
                client = genai.Client(api_key=gemini_api_key)
                prompt = f"""Você é um estrategista de viralização no YouTube Shorts.
Crie metadados perfeitos para este vídeo:

Título Atual/Tema: {base_title}
Fala/Transcrição do Trecho: {transcript_snippet[:1500]}

Retorne APENAS um JSON válido com o formato:
{{
  "title": "TÍTULO VIRAL COM EMOJI (máx 60 caracteres)",
  "description": "Descrição envolvente em 2-3 frases chamando para o canal com chamada para ação.\\n\\n#Shorts #YouTubeShorts #Viral #Trending #Cortes",
  "hashtags": ["#Shorts", "#YouTubeShorts", "#Viral", "#Cortes", "#Engraçado"],
  "tags": ["shorts", "cortes", "viral", "curiosidades", "youtube shorts"]
}}"""
                res = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                text = res.text.strip()
                import re
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if m:
                    return json.loads(m.group(0))
            except Exception as e:
                logger.warning("Falha ao gerar metadados com Gemini: %s", e)

        # Fallback inteligente local
        clean_title = base_title.strip().upper()
        if len(clean_title) > 60:
            clean_title = clean_title[:57] + "..."

        viral_title = f"🔥 {clean_title}"
        desc = (
            f"Confira este momento incrível! Inscreva-se no canal para não perder os melhores cortes diários! 🔔\n\n"
            f"Assista até o final para ver o desfecho!\n\n"
            f"#Shorts #YouTubeShorts #Viral #Trending #Cortes #Humor #Brasil"
        )
        hashtags = ["#Shorts", "#YouTubeShorts", "#Viral", "#Trending", "#Cortes"]
        tags = ["shorts", "youtube shorts", "cortes", "viral", "destaques", "reels"]

        return {
            "title": viral_title,
            "description": desc,
            "hashtags": hashtags,
            "tags": tags,
        }

    def save_client_secrets(self, secrets_dict_or_json: Any) -> str:
        """Salva o arquivo client_secrets.json enviado pelo usuário."""
        if isinstance(secrets_dict_or_json, str):
            secrets_dict = json.loads(secrets_dict_or_json)
        else:
            secrets_dict = secrets_dict_or_json

        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(secrets_dict, f, indent=2)
        return CREDENTIALS_FILE

    def is_configured(self) -> bool:
        """Verifica se há credenciais ou tokens salvos."""
        return os.path.isfile(CREDENTIALS_FILE) or os.path.isfile(TOKEN_FILE)

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: str = "private",  # 'public', 'private', 'unlisted'
        publish_at_iso: Optional[str] = None,  # Ex: '2026-09-02T15:00:00Z' para agendamento
    ) -> Dict[str, Any]:
        """
        Realiza o upload oficial do vídeo para a YouTube Data API v3.
        Se privacy_status == 'private' e publish_at_iso for fornecido, o YouTube agenda a publicação!
        """
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {video_path}")

        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise RuntimeError(
                "Bibliotecas da Google API não instaladas. Execute: pip install google-api-python-client google-auth-oauthlib"
            )

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        creds = None

        if os.path.exists(TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            except Exception as e:
                logger.warning("Token inválido, re-autenticando: %s", e)

        if not creds or not creds.valid:
            if os.path.exists(CREDENTIALS_FILE):
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
            else:
                raise RuntimeError(
                    "Credenciais do YouTube não encontradas. Configure o client_secrets.json nas configurações."
                )

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags or ["shorts", "viral"],
                "categoryId": "22",  # People & Blogs / Entretenimento
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Se houver data de agendamento (o status deve ser 'private' conforme exigência da API do YouTube)
        if publish_at_iso and publish_at_iso.strip():
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = publish_at_iso.strip()

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        logger.info("Iniciando upload para o YouTube Data API: %s", title)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info("Upload YouTube: %d%%", int(status.progress() * 100))

        video_id = response.get("id")
        yt_url = f"https://youtube.com/shorts/{video_id}" if video_id else ""

        return {
            "status": "success",
            "video_id": video_id,
            "youtube_url": yt_url,
            "title": title,
            "privacy": body["status"]["privacyStatus"],
            "scheduled_at": publish_at_iso if publish_at_iso else None,
        }
