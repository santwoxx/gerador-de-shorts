import os
import re
import json
import uuid
import time
import asyncio
import logging
import threading
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from .downloader import YouTubeDownloader, is_cookie_error, js_runtime_status
from . import cookies_manager
from .transcriber import YouTubeTranscriber
from .ai_clipper import AIClipper
from .subtitle_generator import SubtitleGenerator
from .video_processor import VideoProcessor
from .video_editor import VideoEditor, LIMITS as EDIT_LIMITS
from .youtube_publisher import YouTubePublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("autoshorts")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
DOWNLOADS_DIR = os.path.join(STORAGE_DIR, "downloads")
SUBTITLES_DIR = os.path.join(STORAGE_DIR, "subtitles")
WATERMARKS_DIR = os.path.join(STORAGE_DIR, "watermarks")
OUTPUTS_DIR = os.path.join(STORAGE_DIR, "outputs")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

for d in [DOWNLOADS_DIR, SUBTITLES_DIR, WATERMARKS_DIR, OUTPUTS_DIR]:
    os.makedirs(d, exist_ok=True)

app = FastAPI(title="AutoShorts AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Needs-Cookies"],
)

downloader = YouTubeDownloader(DOWNLOADS_DIR)
transcriber = YouTubeTranscriber()
subtitle_gen = SubtitleGenerator(SUBTITLES_DIR)
video_proc = VideoProcessor(OUTPUTS_DIR)
video_editor = VideoEditor(OUTPUTS_DIR, video_proc.ffmpeg_path)

# Legendas de videos com restricao de idade so saem pelo yt-dlp (com cookies).
transcriber.set_caption_provider(downloader.fetch_captions)

tasks: Dict[str, Dict[str, Any]] = {}
tasks_lock = threading.Lock()

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="short_gen")

YT_URL_RE = re.compile(
    r'(?:https?://)?(?:www\.)?'
    r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/|youtube\.com/live/)'
    r'([0-9A-Za-z_-]{11})'
)

TASK_MAX_AGE = 3600
TASK_CLEANUP_INTERVAL = 300
_last_cleanup = time.time()


def _cleanup_old_tasks():
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < TASK_CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    with tasks_lock:
        expired = [tid for tid, t in tasks.items() if now - t.get("created_at", now) > TASK_MAX_AGE]
        for tid in expired:
            del tasks[tid]
        if expired:
            logger.info("Limpeza: %d tarefas antigas removidas", len(expired))


class AnalyzeRequest(BaseModel):
    url: str
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    min_duration: float = 30.0
    max_duration: float = 60.0
    max_clips: int = 5
    provider: str = "auto"
    clip_mode: str = "viral_highlights"
    start_clip_offset: int = 1

    @field_validator("url")
    @classmethod
    def validate_yt_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL nao pode ser vazia")
        if not YT_URL_RE.search(v):
            raise ValueError("URL invalida: insira um link valido do YouTube")
        return v

    @field_validator("min_duration", "max_duration")
    @classmethod
    def validate_durations(cls, v: float) -> float:
        if v < 0 or v > 7200:
            raise ValueError("O tempo deve estar entre 0 e 7200 segundos")
        return v

    @field_validator("max_clips")
    @classmethod
    def validate_max_clips(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("max_clips deve estar entre 1 e 100")
        return v

    @field_validator("clip_mode")
    @classmethod
    def validate_clip_mode(cls, v: str) -> str:
        if v not in ("viral_highlights", "sequential", "custom_manual"):
            raise ValueError("clip_mode deve ser 'viral_highlights', 'sequential' ou 'custom_manual'")
        return v


class GenerateShortRequest(BaseModel):
    url: str
    clip_id: str
    start: float
    end: float
    title: Optional[str] = "Corte Viral"
    layout: str = "blur_bg"
    subtitle_style: str = "yellow_viral"
    watermark_type: str = "text"
    watermark_text: Optional[str] = ""
    watermark_position: str = "top_right"
    watermark_image_name: Optional[str] = None
    watermark_scale: int = 250
    watermark_opacity: float = 0.9
    react_cam_pos: str = "bottom_right"
    react_cam_order: str = "cam_top_content_bottom"
    react_ratio: str = "50_50"
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_yt_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL nao pode ser vazia")
        if not YT_URL_RE.search(v):
            raise ValueError("URL invalida: insira um link valido do YouTube")
        return v


@app.on_event("startup")
async def startup_event():
    logger.info("AutoShorts AI iniciado com sucesso")
    js = js_runtime_status()
    if js["ok"]:
        logger.info("%s", js["message"])
    else:
        logger.warning("ATENCAO: %s", js["message"])


@app.post("/api/analyze")
async def analyze_video(req: AnalyzeRequest):
    _cleanup_old_tasks()

    task_id = str(uuid.uuid4())
    with tasks_lock:
        tasks[task_id] = {
            "status": "processing",
            "progress": 10,
            "message": "Extraindo metadados do video...",
            "result": None,
            "error": None,
            "created_at": time.time(),
        }

    try:
        meta = downloader.extract_info(req.url)
        with tasks_lock:
            tasks[task_id]["progress"] = 30
            tasks[task_id]["message"] = "Buscando transcricao gratuita com timestamps..."

        segments = transcriber.get_transcript(req.url, video_metadata=meta)
        if not segments:
            raise ValueError("Nao foi possivel processar segmentos para este video.")

        with tasks_lock:
            tasks[task_id]["progress"] = 60
            tasks[task_id]["message"] = "Identificando momentos de alta retencao com IA..."

        clipper = AIClipper(gemini_api_key=req.gemini_api_key, groq_api_key=req.groq_api_key)
        genre_info = clipper.detect_video_genre(meta, segments)

        clips = clipper.find_viral_clips(
            transcript_segments=segments,
            video_metadata=meta,
            min_duration=req.min_duration,
            max_duration=req.max_duration,
            max_clips=req.max_clips,
            preferred_provider=req.provider,
            clip_mode=req.clip_mode,
            start_clip_offset=req.start_clip_offset,
        )

        with tasks_lock:
            tasks[task_id]["progress"] = 100
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["message"] = f"{len(clips)} cortes virais identificados com sucesso!"
            tasks[task_id]["result"] = {
                "metadata": meta,
                "genre_info": genre_info,
                "clips": clips,
                "total_segments": len(segments),
            }

        return tasks[task_id]["result"]

    except Exception as e:
        logger.exception("Erro na analise do video")
        with tasks_lock:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = str(e)
        # Sinaliza ao frontend que o caso se resolve configurando os cookies.
        headers = {"X-Needs-Cookies": "1"} if is_cookie_error(str(e)) else None
        raise HTTPException(status_code=400, detail=str(e), headers=headers)


def _run_short_generation_task(task_id: str, req: GenerateShortRequest):
    try:
        with tasks_lock:
            tasks[task_id]["status"] = "processing"
            tasks[task_id]["progress"] = 10
            tasks[task_id]["message"] = "Obtendo metadados e transcricao..."

        try:
            meta = downloader.extract_info(req.url)
        except Exception:
            meta = {"duration": max(60.0, req.end), "title": req.title}

        segments = transcriber.get_transcript(req.url, video_metadata=meta)

        ass_path = None
        if req.subtitle_style and req.subtitle_style != "none":
            with tasks_lock:
                tasks[task_id]["progress"] = 25
                tasks[task_id]["message"] = f"Gerando estilo de legenda '{req.subtitle_style}'..."

            ass_filename = f"sub_{task_id}.ass"
            ass_path = subtitle_gen.generate_ass_subtitles(
                transcript_segments=segments,
                clip_start=req.start,
                clip_end=req.end,
                style_preset=req.subtitle_style,
                output_filename=ass_filename,
            )
        else:
            with tasks_lock:
                tasks[task_id]["progress"] = 25
                tasks[task_id]["message"] = "Modo 'Sem Legenda' selecionado, gerando vídeo limpo..."

        def dl_progress(pct: float):
            mapped = 40 + int((pct / 100.0) * 15)
            with tasks_lock:
                tasks[task_id]["progress"] = min(54, mapped)
                tasks[task_id]["message"] = f"Baixando video fonte ({int(pct)}%)..."

        video_id = transcriber.extract_video_id(req.url)
        raw_video_path = downloader.download_video(
            req.url,
            video_id,
            ffmpeg_path=video_proc.ffmpeg_path,
            progress_hook=dl_progress,
        )

        wm_img_path = None
        if req.watermark_type in ("image", "full_overlay") and req.watermark_image_name:
            candidate = os.path.join(WATERMARKS_DIR, req.watermark_image_name)
            if os.path.isfile(candidate):
                wm_img_path = candidate

        with tasks_lock:
            tasks[task_id]["progress"] = 55
            tasks[task_id]["message"] = "Processando video vertical 9:16 e aplicando efeitos..."

        output_filename = f"short_{task_id[:8]}_{int(req.start)}_{int(req.end)}.mp4"

        def ffmpeg_progress(pct: int, msg: str):
            mapped = 55 + int(pct * 0.43)
            with tasks_lock:
                tasks[task_id]["progress"] = min(98, mapped)
                tasks[task_id]["message"] = msg

        final_path = video_proc.process_short(
            input_video_path=raw_video_path,
            output_filename=output_filename,
            start_time=req.start,
            end_time=req.end,
            layout_mode=req.layout,
            ass_subtitles_path=ass_path,
            watermark_text=req.watermark_text if req.watermark_type == "text" else None,
            watermark_position=req.watermark_position,
            watermark_image_path=wm_img_path,
            watermark_scale=req.watermark_scale,
            watermark_opacity=req.watermark_opacity,
            react_cam_pos=req.react_cam_pos,
            react_cam_order=req.react_cam_order,
            react_ratio=req.react_ratio,
            progress_callback=ffmpeg_progress,
        )

        with tasks_lock:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["message"] = "Short renderizado com sucesso!"
            tasks[task_id]["result"] = {
                "filename": output_filename,
                "title": req.title,
                "duration": round(req.end - req.start, 2),
                "video_url": f"/api/stream/{output_filename}",
                "download_url": f"/api/download/{output_filename}",
            }

        logger.info("Short gerado com sucesso: %s", output_filename)

    except Exception as e:
        logger.exception("Erro na geracao do short %s", task_id)
        with tasks_lock:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["progress"] = 0
            tasks[task_id]["error"] = str(e)
            tasks[task_id]["needs_cookies"] = is_cookie_error(str(e))
            tasks[task_id]["message"] = f"Erro na renderizacao: {str(e)}"


@app.post("/api/generate-short")
async def generate_short(req: GenerateShortRequest, background_tasks: BackgroundTasks):
    _cleanup_old_tasks()

    task_id = str(uuid.uuid4())
    with tasks_lock:
        tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "progress": 0,
            "message": "Enfileirando geracao do Short...",
            "result": None,
            "error": None,
            "created_at": time.time(),
        }
    background_tasks.add_task(_run_short_generation_task, task_id, req)
    return {"task_id": task_id, "status": "queued"}


class BatchGenerateRequest(BaseModel):
    url: str
    clips: list  # Lista de {clip_id, start, end, title}
    layout: str = "blur_bg"
    subtitle_style: str = "yellow_viral"
    watermark_type: str = "text"
    watermark_text: Optional[str] = ""
    watermark_position: str = "top_right"
    watermark_image_name: Optional[str] = None
    watermark_scale: int = 250
    watermark_opacity: float = 0.9
    react_cam_pos: str = "bottom_right"
    react_cam_order: str = "cam_top_content_bottom"
    react_ratio: str = "50_50"
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_yt_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL nao pode ser vazia")
        if not YT_URL_RE.search(v):
            raise ValueError("URL invalida: insira um link valido do YouTube")
        return v


def _run_batch_generation_task(batch_task_id: str, req: BatchGenerateRequest):
    total_clips = len(req.clips)
    completed = []
    errors = []

    with tasks_lock:
        tasks[batch_task_id]["status"] = "processing"
        tasks[batch_task_id]["progress"] = 2
        tasks[batch_task_id]["message"] = f"Iniciando lote: 0/{total_clips} shorts..."
        tasks[batch_task_id]["batch_total"] = total_clips
        tasks[batch_task_id]["batch_completed"] = 0
        tasks[batch_task_id]["batch_results"] = []

    for idx, clip_info in enumerate(req.clips):
        clip_num = idx + 1
        with tasks_lock:
            tasks[batch_task_id]["message"] = f"Gerando Short {clip_num}/{total_clips}: {clip_info.get('title', 'Corte')}..."
            tasks[batch_task_id]["batch_current"] = clip_num
            base_progress = int((idx / total_clips) * 100)
            tasks[batch_task_id]["progress"] = max(2, base_progress)

        single_req = GenerateShortRequest(
            url=req.url,
            clip_id=clip_info.get("clip_id", f"batch_{idx}"),
            start=float(clip_info["start"]),
            end=float(clip_info["end"]),
            title=clip_info.get("title", f"Parte {clip_num}"),
            layout=req.layout,
            subtitle_style=req.subtitle_style,
            watermark_type=req.watermark_type,
            watermark_text=req.watermark_text,
            watermark_position=req.watermark_position,
            watermark_image_name=req.watermark_image_name,
            watermark_scale=req.watermark_scale,
            watermark_opacity=req.watermark_opacity,
            react_cam_pos=req.react_cam_pos,
            react_cam_order=req.react_cam_order,
            react_ratio=req.react_ratio,
            gemini_api_key=req.gemini_api_key,
            groq_api_key=req.groq_api_key,
        )

        inner_task_id = str(uuid.uuid4())
        with tasks_lock:
            tasks[inner_task_id] = {
                "task_id": inner_task_id,
                "status": "processing",
                "progress": 0,
                "message": "Processando...",
                "result": None,
                "error": None,
                "created_at": time.time(),
            }

        try:
            _run_short_generation_task(inner_task_id, single_req)

            with tasks_lock:
                inner = tasks.get(inner_task_id, {})
                if inner.get("status") == "completed" and inner.get("result"):
                    completed.append(inner["result"])
                    tasks[batch_task_id]["batch_results"].append(inner["result"])
                else:
                    errors.append(inner.get("error", "Erro desconhecido"))
        except Exception as e:
            logger.exception("Erro no batch clip %d", clip_num)
            errors.append(str(e))

        with tasks_lock:
            tasks[batch_task_id]["batch_completed"] = clip_num
            progress = int((clip_num / total_clips) * 100)
            tasks[batch_task_id]["progress"] = min(99, progress)

    with tasks_lock:
        tasks[batch_task_id]["progress"] = 100
        if completed:
            tasks[batch_task_id]["status"] = "completed"
            tasks[batch_task_id]["message"] = f"{len(completed)}/{total_clips} shorts gerados com sucesso!"
            tasks[batch_task_id]["result"] = {
                "completed": completed,
                "errors": errors,
                "total": total_clips,
                "success_count": len(completed),
            }
        else:
            tasks[batch_task_id]["status"] = "error"
            first_error = str(errors[0]) if errors else ""
            tasks[batch_task_id]["error"] = (
                f"Todos os {total_clips} shorts falharam." + (f" Motivo: {first_error}" if first_error else "")
            )
            tasks[batch_task_id]["needs_cookies"] = is_cookie_error(first_error)
            tasks[batch_task_id]["message"] = "Falha na geracao em lote."

    logger.info("Batch %s finalizado: %d/%d sucesso", batch_task_id, len(completed), total_clips)


@app.post("/api/generate-batch")
async def generate_batch(req: BatchGenerateRequest, background_tasks: BackgroundTasks):
    _cleanup_old_tasks()

    if not req.clips or len(req.clips) == 0:
        raise HTTPException(status_code=400, detail="Lista de clips vazia.")
    if len(req.clips) > 20:
        raise HTTPException(status_code=400, detail="Maximo de 20 clips por lote.")

    batch_task_id = str(uuid.uuid4())
    with tasks_lock:
        tasks[batch_task_id] = {
            "task_id": batch_task_id,
            "status": "queued",
            "progress": 0,
            "message": f"Lote com {len(req.clips)} shorts enfileirado...",
            "result": None,
            "error": None,
            "created_at": time.time(),
            "batch_total": len(req.clips),
            "batch_completed": 0,
            "batch_current": 0,
            "batch_results": [],
        }

    background_tasks.add_task(_run_batch_generation_task, batch_task_id, req)
    return {"task_id": batch_task_id, "status": "queued", "total_clips": len(req.clips)}


@app.get("/api/progress/{task_id}")
async def get_task_progress(task_id: str):
    with tasks_lock:
        task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa nao encontrada.")
    return task


@app.post("/api/upload-watermark")
async def upload_watermark(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="Formato invalido. Use PNG, JPG ou WebP.")

    unique_name = f"wm_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = os.path.join(WATERMARKS_DIR, unique_name)

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo excede 5MB.")
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="Arquivo muito pequeno ou vazio.")

    with open(dest_path, "wb") as f:
        f.write(content)

    return {"filename": unique_name, "url": f"/storage/watermarks/{unique_name}"}


PRESETS_FILE = os.path.join(WATERMARKS_DIR, "presets.json")

DEFAULT_PRESETS = [
    {
        "id": "gato_galudo_916",
        "name": "🎬 Gato Galudo 9:16 Overlay",
        "type": "full_overlay",
        "text": "@GatoGaludoClips",
        "position": "full_916",
        "scale": 1080,
        "opacity": 1.0,
        "image_name": "gato_galudo_overlay.png",
        "badge": "Overlay 9:16"
    },
    {
        "id": "canal_top_right",
        "name": "🔥 Canal Topo Direito",
        "type": "text",
        "text": "@meucanal",
        "position": "top_right",
        "scale": 250,
        "opacity": 0.9,
        "image_name": None,
        "badge": "Texto"
    },
    {
        "id": "selo_bottom_center",
        "name": "⚡ Selo Rodapé Centro",
        "type": "text",
        "text": "CORTES VIRIS",
        "position": "bottom_center",
        "scale": 220,
        "opacity": 0.85,
        "image_name": None,
        "badge": "Texto"
    }
]


def _load_watermark_presets() -> list:
    if os.path.isfile(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PRESETS


def _save_watermark_presets(presets: list):
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Erro ao salvar presets de watermark: %s", e)


@app.get("/api/watermark-presets")
async def get_watermark_presets():
    return _load_watermark_presets()


class WatermarkPresetModel(BaseModel):
    id: Optional[str] = None
    name: str
    type: str  # 'text', 'image', 'full_overlay'
    text: Optional[str] = ""
    position: str = "top_right"
    scale: int = 250
    opacity: float = 0.9
    image_name: Optional[str] = None
    badge: Optional[str] = "Personalizado"


@app.post("/api/watermark-presets")
async def save_watermark_preset(preset: WatermarkPresetModel):
    presets = _load_watermark_presets()
    preset_dict = preset.dict()
    if not preset_dict.get("id"):
        preset_dict["id"] = f"preset_{uuid.uuid4().hex[:8]}"

    # Subtitui se ja existir com o mesmo ID ou adiciona
    existing_idx = next((i for i, p in enumerate(presets) if p.get("id") == preset_dict["id"]), None)
    if existing_idx is not None:
        presets[existing_idx] = preset_dict
    else:
        presets.append(preset_dict)

    _save_watermark_presets(presets)
    return {"status": "success", "preset": preset_dict}


@app.delete("/api/watermark-presets/{preset_id}")
async def delete_watermark_preset(preset_id: str):
    presets = _load_watermark_presets()
    new_presets = [p for p in presets if p.get("id") != preset_id]
    _save_watermark_presets(new_presets)
    return {"status": "success", "preset_id": preset_id}


@app.get("/api/watermarks")
async def list_watermark_images():
    files = []
    if os.path.isdir(WATERMARKS_DIR):
        for fname in os.listdir(WATERMARKS_DIR):
            if fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                full_p = os.path.join(WATERMARKS_DIR, fname)
                try:
                    stat = os.stat(full_p)
                    files.append({
                        "filename": fname,
                        "url": f"/storage/watermarks/{fname}",
                        "size_kb": round(stat.st_size / 1024, 1),
                    })
                except OSError:
                    continue
    return files


def _get_dir_size_mb(directory: str) -> float:
    total = 0
    if os.path.isdir(directory):
        for dirpath, dirnames, filenames in os.walk(directory):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp) and not f.endswith(".gitkeep"):
                    total += os.path.getsize(fp)
    return round(total / (1024 * 1024), 2)


@app.get("/api/storage-stats")
async def get_storage_stats():
    downloads_mb = _get_dir_size_mb(DOWNLOADS_DIR)
    outputs_mb = _get_dir_size_mb(OUTPUTS_DIR)
    subtitles_mb = _get_dir_size_mb(SUBTITLES_DIR)
    return {
        "downloads_mb": downloads_mb,
        "outputs_mb": outputs_mb,
        "subtitles_mb": subtitles_mb,
        "total_mb": round(downloads_mb + outputs_mb + subtitles_mb, 2)
    }


@app.post("/api/clear-cache")
async def clear_cache():
    cleared_files = 0
    cleared_bytes = 0

    if os.path.isdir(DOWNLOADS_DIR):
        for f in os.listdir(DOWNLOADS_DIR):
            if f.endswith(".gitkeep"):
                continue
            fp = os.path.join(DOWNLOADS_DIR, f)
            if os.path.isfile(fp):
                sz = os.path.getsize(fp)
                os.remove(fp)
                cleared_files += 1
                cleared_bytes += sz

    if os.path.isdir(SUBTITLES_DIR):
        for f in os.listdir(SUBTITLES_DIR):
            if f.endswith(".gitkeep"):
                continue
            fp = os.path.join(SUBTITLES_DIR, f)
            if os.path.isfile(fp):
                sz = os.path.getsize(fp)
                os.remove(fp)
                cleared_files += 1
                cleared_bytes += sz

    return {
        "status": "success",
        "cleared_files": cleared_files,
        "freed_mb": round(cleared_bytes / (1024 * 1024), 2)
    }


@app.get("/api/outputs")
async def list_outputs():
    files = []
    if os.path.isdir(OUTPUTS_DIR):
        for fname in os.listdir(OUTPUTS_DIR):
            if not fname.endswith(".mp4"):
                continue
            full_p = os.path.join(OUTPUTS_DIR, fname)
            try:
                stat = os.stat(full_p)
                files.append({
                    "filename": fname,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": int(stat.st_mtime),
                    "stream_url": f"/api/stream/{fname}",
                    "download_url": f"/api/download/{fname}",
                })
            except OSError:
                continue
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files


@app.delete("/api/outputs/{filename}")
async def delete_output(filename: str):
    if not filename.endswith(".mp4") or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo invalido.")
    target = os.path.join(OUTPUTS_DIR, filename)
    if os.path.isfile(target):
        os.remove(target)
        return {"status": "success", "message": f"{filename} removido."}
    raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")


def _get_file_response(file_path: str, filename: str, as_attachment: bool = False):
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Video nao encontrado.")

    disposition = f'attachment; filename="{filename}"' if as_attachment else f'inline; filename="{filename}"'

    async def file_iterator(chunk_size: int = 1024 * 64):
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    file_size = os.path.getsize(file_path)
    headers = {
        "Content-Disposition": disposition,
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
    }
    return StreamingResponse(file_iterator(), media_type="video/mp4", headers=headers)


@app.get("/api/stream/{filename}")
async def stream_video(filename: str):
    file_path = os.path.join(OUTPUTS_DIR, filename)
    return _get_file_response(file_path, filename, as_attachment=False)


@app.get("/api/download/{filename}")
async def download_video_file(filename: str):
    file_path = os.path.join(OUTPUTS_DIR, filename)
    return _get_file_response(file_path, filename, as_attachment=True)


yt_publisher = YouTubePublisher()


class YTMetadataRequest(BaseModel):
    base_title: str
    transcript_snippet: Optional[str] = ""
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None


class YTUploadRequest(BaseModel):
    filename: str
    title: str
    description: str
    tags: Optional[list] = None
    privacy_status: str = "private"  # 'public', 'private', 'unlisted'
    publish_at_iso: Optional[str] = None  # Agendamento ISO string


@app.post("/api/youtube/generate-metadata")
async def generate_youtube_metadata(req: YTMetadataRequest):
    return yt_publisher.generate_shorts_metadata(
        base_title=req.base_title,
        transcript_snippet=req.transcript_snippet or "",
        gemini_api_key=req.gemini_api_key,
        groq_api_key=req.groq_api_key,
    )


@app.post("/api/youtube/upload")
async def upload_to_youtube(req: YTUploadRequest):
    if not req.filename or "/" in req.filename or "\\" in req.filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    video_path = os.path.join(OUTPUTS_DIR, req.filename)
    if not os.path.isfile(video_path):
        raise HTTPException(status_code=404, detail="Vídeo MP4 não encontrado para upload.")

    try:
        res = yt_publisher.upload_video(
            video_path=video_path,
            title=req.title,
            description=req.description,
            tags=req.tags,
            privacy_status=req.privacy_status,
            publish_at_iso=req.publish_at_iso,
        )
        return res
    except Exception as e:
        logger.exception("Erro no upload do YouTube")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/youtube/status")
async def get_youtube_status():
    return {"is_configured": yt_publisher.is_configured()}


@app.post("/api/youtube/credentials")
async def save_youtube_credentials(file: UploadFile = File(...)):
    content = await file.read()
    try:
        secrets_dict = json.loads(content.decode("utf-8"))
        yt_publisher.save_client_secrets(secrets_dict)
        return {"status": "success", "message": "Credenciais salvas com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Arquivo JSON de credenciais inválido: {e}")


class EditShortRequest(BaseModel):
    filename: str
    speed: float = 1.0
    preserve_pitch: bool = True
    pitch_semitones: float = 0.0
    volume: float = 1.0
    mirror: bool = False
    zoom: float = 1.0
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    grain: float = 0.0
    trim_start: float = 0.0
    trim_end: float = 0.0

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.endswith(".mp4") or "/" in v or "\\" in v or ".." in v:
            raise ValueError("Nome de arquivo invalido")
        return v


def _run_edit_task(task_id: str, req: EditShortRequest):
    def _progress(pct: int, message: str):
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["progress"] = pct
                tasks[task_id]["message"] = message

    try:
        result = video_editor.edit(
            req.filename,
            req.model_dump(exclude={"filename"}),
            progress_callback=_progress,
        )

        with tasks_lock:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["message"] = "Nova versao gerada com sucesso!"
            tasks[task_id]["result"] = {
                "title": result["filename"],
                "filename": result["filename"],
                "duration": result["duration"],
                "size_mb": result["size_mb"],
                "source_filename": result["source_filename"],
                "source_duration": result["source_duration"],
                "video_url": f"/api/stream/{result['filename']}",
                "download_url": f"/api/download/{result['filename']}",
            }

        logger.info(
            "Ajustes aplicados: %s -> %s (%.1fs -> %.1fs)",
            result["source_filename"], result["filename"],
            result["source_duration"], result["duration"],
        )

    except Exception as e:
        logger.exception("Erro ao aplicar ajustes no short %s", task_id)
        with tasks_lock:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["progress"] = 0
            tasks[task_id]["error"] = str(e)
            tasks[task_id]["message"] = f"Erro ao aplicar os ajustes: {str(e)}"


@app.get("/api/short-info/{filename}")
async def short_info(filename: str):
    """Duracao e tamanho de um Short da biblioteca (usado pelo painel de ajustes)."""
    if not filename.endswith(".mp4") or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo invalido.")

    path = os.path.join(OUTPUTS_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Short nao encontrado.")

    duration = await asyncio.get_running_loop().run_in_executor(
        None, video_editor.probe_duration, path
    )
    return {
        "filename": filename,
        "duration": round(duration, 2),
        "size_mb": round(os.path.getsize(path) / (1024 * 1024), 2),
    }


@app.post("/api/edit-short")
async def edit_short(req: EditShortRequest):
    _cleanup_old_tasks()

    source_path = os.path.join(OUTPUTS_DIR, req.filename)
    if not os.path.isfile(source_path):
        raise HTTPException(status_code=404, detail="Short nao encontrado na biblioteca.")

    task_id = str(uuid.uuid4())
    with tasks_lock:
        tasks[task_id] = {
            "status": "processing",
            "progress": 3,
            "message": "Preparando os ajustes...",
            "result": None,
            "error": None,
            "created_at": time.time(),
        }

    _executor.submit(_run_edit_task, task_id, req)
    return {"task_id": task_id, "status": "processing"}


@app.get("/api/edit-limits")
async def edit_limits():
    """Faixas aceitas por cada ajuste, para o frontend montar os controles."""
    return {
        name: {"min": low, "max": high, "default": default}
        for name, (low, high, default) in EDIT_LIMITS.items()
    }


@app.get("/api/cookies/status")
async def cookies_status_endpoint():
    """Estado dos cookies + navegadores disponiveis para importacao."""
    status = cookies_manager.cookies_status()
    status["browsers"] = cookies_manager.available_browsers()
    status["js_runtime"] = js_runtime_status()
    return status


@app.post("/api/cookies/upload")
async def cookies_upload(file: UploadFile = File(...)):
    """Recebe o cookies.txt (ou JSON) exportado pela extensao do navegador."""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo de cookies excede 5MB.")
    if len(content) < 20:
        raise HTTPException(status_code=400, detail="Arquivo de cookies vazio ou muito pequeno.")

    try:
        text = content.decode("utf-8", errors="ignore")
        status = cookies_manager.save_cookies_from_text(text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Falha ao salvar cookies enviados")
        raise HTTPException(status_code=400, detail=f"Falha ao salvar os cookies: {e}")

    downloader.reset_strategy()
    status["browsers"] = cookies_manager.available_browsers()
    return status


class CookiesTextRequest(BaseModel):
    content: str


@app.post("/api/cookies/text")
async def cookies_paste(req: CookiesTextRequest):
    """Aceita o conteudo do cookies.txt colado direto na interface."""
    try:
        status = cookies_manager.save_cookies_from_text(req.content, source="conteudo colado")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Falha ao salvar cookies colados")
        raise HTTPException(status_code=400, detail=f"Falha ao salvar os cookies: {e}")

    downloader.reset_strategy()
    status["browsers"] = cookies_manager.available_browsers()
    return status


class CookiesBrowserRequest(BaseModel):
    browser: Optional[str] = None


@app.post("/api/cookies/browser")
async def cookies_from_browser(req: CookiesBrowserRequest):
    """Importa a sessao logada direto do navegador instalado (sem extensao)."""
    browser = (req.browser or "").strip().lower() or None
    valid = {b["id"] for b in cookies_manager.available_browsers()}
    if browser and browser not in valid:
        raise HTTPException(status_code=400, detail=f"Navegador nao suportado: {browser}")

    try:
        # Executor padrao (nao o _executor): ler o navegador pode demorar e nao
        # deve competir com as renderizacoes em andamento.
        status = await asyncio.get_running_loop().run_in_executor(
            None, cookies_manager.import_from_browser, browser
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Falha ao importar cookies do navegador")
        raise HTTPException(status_code=400, detail=f"Falha ao importar cookies do navegador: {e}")

    downloader.reset_strategy()
    status["browsers"] = cookies_manager.available_browsers()
    return status


@app.delete("/api/cookies")
async def cookies_delete():
    status = cookies_manager.delete_cookies()
    downloader.reset_strategy()
    status["browsers"] = cookies_manager.available_browsers()
    return status


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": "2.0.0",
        "tasks_active": len(tasks),
        "js_runtime": js_runtime_status(),
        "cookies": cookies_manager.cookies_status()["configured"],
    }


app.mount("/storage/watermarks", StaticFiles(directory=WATERMARKS_DIR), name="watermarks")

if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
