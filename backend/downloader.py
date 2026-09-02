import os
import re
import time
import glob
import shutil
import logging
import tempfile
import contextlib
import yt_dlp
from typing import Dict, Any, Iterator, Optional, Callable, List, Tuple

from .cookies_manager import (
    auto_import_from_browser,
    cookies_status,
    find_cookie_file,
)

logger = logging.getLogger("autoshorts.downloader")

DISK_CACHE_MAX_AGE_HOURS = 48
DISK_CACHE_MAX_SIZE_MB = 1024

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage"))

# Formato preferido: H.264 1080p (decodifica rapido no ffmpeg), com quedas
# progressivas ate qualquer formato disponivel.
VIDEO_FORMAT = (
    "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[ext=m4a]/"
    "bestvideo[ext=mp4][height<=1080]+bestaudio/"
    "best[ext=mp4]/best"
)

# Runtimes de JavaScript que o yt-dlp pode usar para resolver o "n challenge"
# do YouTube. Sem um deles (mais o pacote yt-dlp-ejs) o YouTube devolve o video
# SEM NENHUM FORMATO, e o erro que aparece e o enganoso "Requested format is not
# available". Declarar runtimes ausentes e inofensivo: o yt-dlp ignora.
JS_RUNTIMES = {name: {"path": None} for name in ("deno", "bun", "node", "quickjs")}

# Cliente que devolve 1080p em videos com restricao de idade quando ha uma
# sessao logada. Os clientes padrao respondem "Sorry, this content is
# age-restricted" mesmo com cookies validos.
AUTH_PLAYER_CLIENTS = ["web_safari", "web", "mweb"]

# Clientes que costumam passar pelo age-gate quando o video e incorporavel.
AGE_GATE_PLAYER_CLIENTS = ["web_embedded", "tv_simply", "tv", "mweb"]

# Clientes alternativos usados apenas como ultima tentativa. NAO force esses
# clientes por padrao: sem PO token eles devolvem so o formato 18 (360p).
FALLBACK_PLAYER_CLIENTS = ["tv", "web_safari", "mweb", "android_vr", "ios"]

# Clientes que o yt-dlp descarta quando ha um arquivo de cookies
# ("Skipping client X since it does not support cookies").
NO_COOKIE_CLIENTS = frozenset({"android", "android_vr", "ios", "visionos", "tv_simply"})

_AUTH_MARKERS = (
    "sign in to confirm your age",
    "inappropriate for some users",
    "age-restricted",
    "age restricted",
    "sign in to confirm",
    "not a bot",
    "please sign in",
    "login required",
    "account cookies",
    "use --cookies",
    "cookies-from-browser",
    "http error 403",
    "http error 429",
)

# Erros em que insistir com outra estrategia nao adianta nada.
_TERMINAL_MARKERS = (
    "private video",
    "removed by the uploader",
    "video has been removed",
    "unsupported url",
    "is not a valid url",
    "premieres in",
    "live event will begin",
)

YT_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/)|youtu\.be/)([0-9A-Za-z_-]{11})"
)

COOKIE_UI_HINT = (
    "Abra 'Configuracoes' > 'Acesso ao YouTube (Cookies)' e clique em "
    "'Importar cookies do navegador' (1 clique) ou envie o arquivo cookies.txt exportado "
    "pela extensao 'Get cookies.txt LOCALLY'."
)


def js_runtime_status() -> Dict[str, Any]:
    """O yt-dlp so consegue montar as URLs de video se resolver o 'n challenge'.

    Para isso ele precisa de DUAS coisas: o pacote yt-dlp-ejs e um runtime de
    JavaScript (deno, bun, node ou quickjs). Faltando qualquer uma delas, o
    YouTube devolve o video sem nenhum formato utilizavel.
    """
    try:
        from yt_dlp.dependencies import yt_dlp_ejs
        has_ejs = yt_dlp_ejs is not None
    except Exception:
        has_ejs = False

    found: List[Dict[str, Any]] = []
    try:
        from yt_dlp.utils._jsruntime import (
            BunJsRuntime, DenoJsRuntime, NodeJsRuntime, QuickJsRuntime,
        )
        for cls in (DenoJsRuntime, BunJsRuntime, NodeJsRuntime, QuickJsRuntime):
            try:
                info = cls().info
            except Exception:
                info = None
            if info:
                found.append({"name": info.name, "version": info.version, "supported": info.supported})
    except Exception as e:
        logger.debug("Nao foi possivel inspecionar os runtimes de JS: %s", e)

    usable = [r for r in found if r["supported"]]
    ok = bool(has_ejs and usable)

    if ok:
        message = f"Motor de JavaScript ativo ({usable[0]['name']} {usable[0]['version']})."
    elif not has_ejs and not usable:
        message = ("Faltam o pacote 'yt-dlp-ejs' e um motor de JavaScript. "
                   "Rode: pip install yt-dlp-ejs  e instale o Node.js 22+ (nodejs.org). "
                   "Sem isso, muitos videos baixam so em 360p ou falham com 'formato nao disponivel'.")
    elif not has_ejs:
        message = ("Falta o pacote 'yt-dlp-ejs'. Rode: pip install yt-dlp-ejs")
    else:
        message = ("Falta um motor de JavaScript. Instale o Node.js 22 ou superior (nodejs.org) "
                   "e reinicie o aplicativo.")

    return {"ok": ok, "has_ejs": has_ejs, "runtimes": found, "message": message}


def normalize_url(url: str) -> str:
    """Reduz o link a forma canonica watch?v=ID.

    Evita erros bobos: playlist inteira baixada por causa de '&list=',
    parametros de rastreio e links de compartilhamento com sufixo.
    """
    if not url:
        return url
    match = YT_ID_RE.search(url.strip())
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url.strip()


def _needs_auth(err_str: str) -> bool:
    low = err_str.lower()
    return any(marker in low for marker in _AUTH_MARKERS)


def _is_terminal(err_str: str) -> bool:
    low = err_str.lower()
    return any(marker in low for marker in _TERMINAL_MARKERS)


# Erros genericos que nao dizem nada ao usuario. Quando outra estrategia deu um
# erro mais especifico, e ele que deve chegar na tela.
_VAGUE_MARKERS = (
    "the page needs to be reloaded",
    "requested format is not available",
    "unable to extract",
    "failed to parse json",
    "nonetype",
)


def _error_score(err_str: str) -> int:
    """Quanto maior, mais util e a mensagem para o usuario."""
    low = (err_str or "").lower()
    if not low:
        return -1
    if any(m in low for m in _TERMINAL_MARKERS):
        return 3
    if any(m in low for m in _VAGUE_MARKERS):
        return 0
    if _needs_auth(low):
        return 2
    return 1


def is_cookie_error(err_str: str) -> bool:
    """Usado pela API para sinalizar ao frontend que faltam cookies."""
    low = (err_str or "").lower()
    return ("cookies" in low or "restricao de idade" in low
            or "login" in low or _needs_auth(low))


def _friendly_error(err_str: str, action: str) -> str:
    """Traduz o erro cru do yt-dlp em uma instrucao util em portugues."""
    low = err_str.lower()
    status = cookies_status()

    if not status["configured"]:
        cookie_hint = COOKIE_UI_HINT
    elif status["expired"]:
        cookie_hint = ("Seus cookies expiraram. " + COOKIE_UI_HINT)
    elif not status["has_login"]:
        cookie_hint = ("Os cookies salvos nao tem sessao logada (faltam os cookies de login). " + COOKIE_UI_HINT)
    else:
        cookie_hint = ("Seus cookies podem ter perdido a validade: atualize-os. " + COOKIE_UI_HINT)

    if "sorry, this content is age-restricted" in low and status["configured"] and status["has_login"]:
        return (
            f"O YouTube barrou este video +18 mesmo com a sua conta logada ao {action}. "
            "Confira se a conta exportada tem data de nascimento de maior de 18 anos e se o "
            "'Modo restrito' esta DESLIGADO em youtube.com (menu da sua foto > Modo restrito). "
            "Se estiver tudo certo, aguarde alguns minutos: o YouTube limita acessos repetidos."
        )

    if ("sign in to confirm your age" in low or "inappropriate for some users" in low
            or "age-restricted" in low or "age restricted" in low):
        return f"Este video tem restricao de idade (+18) e o YouTube exige login para {action}. {cookie_hint}"

    if "not a bot" in low or "sign in to confirm" in low:
        return f"O YouTube pediu verificacao anti-bot para {action} este video. {cookie_hint}"

    if "private video" in low or "this video is private" in low:
        return "Este video e privado. Sem uma conta com acesso a ele nao ha como baixa-lo. Tente outro link."

    if "members-only" in low or "members only" in low or "join this channel" in low:
        return f"Video exclusivo para membros do canal. {cookie_hint} (a conta precisa ser membro do canal)."

    if "premium" in low and "youtube" in low:
        return f"Este conteudo exige YouTube Premium. {cookie_hint}"

    if "not available in your country" in low or ("geo" in low and "block" in low):
        return "Este video esta bloqueado na sua regiao (geo-bloqueio). Tente outro link ou use uma VPN."

    if "removed by the uploader" in low or "account associated" in low or "terminated" in low:
        return "Este video foi removido do YouTube (ou o canal foi encerrado). Tente outro link."

    if "live event will begin" in low or "premieres in" in low:
        return "Este video ainda nao foi exibido (estreia/live agendada). Aguarde o fim da transmissao e tente de novo."

    if "video unavailable" in low or "this video is unavailable" in low:
        return (
            "Video indisponivel. Confira se o link foi copiado por inteiro e esta correto "
            "(no ID do YouTube o 'I' maiusculo e o 'l' minusculo sao quase identicos). "
            "Ele tambem pode ter sido removido, estar privado ou bloqueado na sua regiao."
        )

    if "http error 429" in low or "too many requests" in low:
        return f"O YouTube limitou temporariamente os acessos (HTTP 429). Espere alguns minutos e tente de novo. {cookie_hint}"

    if "http error 403" in low or "forbidden" in low:
        return f"O YouTube recusou o acesso a este video (HTTP 403). {cookie_hint}"

    if "the page needs to be reloaded" in low:
        return (
            f"O YouTube recusou a sessao ao {action} este video (resposta 'The page needs to be reloaded'). "
            f"Normalmente isso passa em alguns minutos. Se insistir, atualize os cookies. {cookie_hint}"
        )

    if "requested format is not available" in low or "no video formats found" in low:
        js = js_runtime_status()
        if not js["ok"]:
            return (
                "O YouTube nao liberou nenhum formato de video porque falta o motor de JavaScript "
                f"que resolve o desafio anti-bot. {js['message']}"
            )
        return "Nenhum formato de video compativel foi encontrado para este link. Tente outro video."

    if ("timed out" in low or "timeout" in low) and "unable to" in low:
        return "A conexao com o YouTube expirou. Verifique sua internet e tente novamente."

    if "unsupported url" in low or "is not a valid url" in low:
        return "Link nao suportado. Cole a URL completa de um video do YouTube (youtube.com/watch?v=... ou youtu.be/...)."

    return f"Falha ao {action} o video: {err_str.strip()[:400]}"


# ----------------------------------------------------------------------
# Legendas via yt-dlp (plano B quando a transcript-api e bloqueada)
# ----------------------------------------------------------------------
CAPTION_EXT_PRIORITY = ("json3", "srv3", "srv1", "vtt")


def _pick_caption_track(info: Dict[str, Any], languages: List[str]) -> Optional[Dict[str, str]]:
    """Escolhe a melhor faixa de legenda: manual antes de automatica."""
    for source in ("subtitles", "automatic_captions"):
        tracks = info.get(source) or {}
        if not isinstance(tracks, dict):
            continue
        wanted = list(languages) + [k for k in tracks if k not in languages]
        for lang in wanted:
            options = tracks.get(lang) or []
            for ext in CAPTION_EXT_PRIORITY:
                for opt in options:
                    if opt.get("ext") == ext and opt.get("url"):
                        return {"url": opt["url"], "ext": ext, "lang": lang, "source": source}
    return None


def _parse_json3(body: str) -> List[Dict[str, Any]]:
    import json

    try:
        data = json.loads(body)
    except ValueError:
        return []

    segments = []
    for event in data.get("events") or []:
        segs = event.get("segs") or []
        text = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
        if not text:
            continue
        start = float(event.get("tStartMs", 0)) / 1000.0
        duration = float(event.get("dDurationMs", 0)) / 1000.0
        segments.append({
            "start": round(start, 2),
            "end": round(start + duration, 2),
            "duration": round(duration, 2),
            "text": text,
        })
    return segments


_VTT_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d+):(\d{2}):(\d{2})[.,](\d{3})")


def _parse_vtt(body: str) -> List[Dict[str, Any]]:
    def to_seconds(h, m, s, ms):
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    segments: List[Dict[str, Any]] = []
    lines = body.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        match = _VTT_TIME_RE.search(lines[i])
        if not match:
            i += 1
            continue
        start = to_seconds(*match.groups()[:4])
        end = to_seconds(*match.groups()[4:])

        i += 1
        parts = []
        while i < len(lines) and lines[i].strip() and not _VTT_TIME_RE.search(lines[i]):
            parts.append(re.sub(r"<[^>]+>", "", lines[i]).strip())
            i += 1

        text = " ".join(p for p in parts if p).strip()
        # Legendas automaticas repetem a linha anterior como "rolagem".
        if text and (not segments or segments[-1]["text"] != text):
            segments.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(end - start, 2),
                "text": text,
            })
    return segments


class YouTubeDownloader:
    def __init__(self, download_dir: str):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self._preferred_strategy: Optional[str] = None
        self._browser_import_tried = False
        self._cleanup_old_downloads()

    @contextlib.contextmanager
    def _disposable_cookies(self) -> Iterator[Optional[str]]:
        """Entrega ao yt-dlp uma COPIA descartavel do arquivo de cookies.

        O yt-dlp reescreve o arquivo apontado por 'cookiefile' ao final de cada
        execucao. Como o YouTube manda apagar cookies de sessao em algumas
        respostas, apontar direto para storage/cookies.txt fazia o proprio app
        destruir o login do usuario aos poucos (sumiam SID, SAPISID, HSID,
        LOGIN_INFO...). Com a copia, o arquivo exportado fica intacto.
        """
        source = find_cookie_file()
        if not source:
            yield None
            return

        tmp_dir = tempfile.mkdtemp(prefix="autoshorts_ck_")
        tmp_path = os.path.join(tmp_dir, "cookies.txt")
        try:
            shutil.copy2(source, tmp_path)
        except OSError as e:
            logger.warning("Nao foi possivel copiar os cookies (%s); usando o arquivo original", e)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            yield source
            return

        try:
            yield tmp_path
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def reset_strategy(self):
        """Chamado quando os cookies mudam: recomeca pela estrategia com cookies."""
        self._preferred_strategy = None
        self._browser_import_tried = False

    def _cleanup_old_downloads(self):
        try:
            now = time.time()
            max_age = DISK_CACHE_MAX_AGE_HOURS * 3600
            for fp in glob.glob(os.path.join(self.download_dir, "*.mp4")):
                if now - os.path.getmtime(fp) > max_age:
                    os.remove(fp)
                    logger.info("Cache limpo: %s (mais de %dh)", os.path.basename(fp), DISK_CACHE_MAX_AGE_HOURS)

            total = sum(os.path.getsize(f) for f in glob.glob(os.path.join(self.download_dir, "*.mp4")))
            if total > DISK_CACHE_MAX_SIZE_MB * 1024 * 1024:
                files = sorted(glob.glob(os.path.join(self.download_dir, "*.mp4")), key=os.path.getmtime)
                for f in files[:len(files) // 2]:
                    os.remove(f)
                    logger.info("Cache reduzido: %s", os.path.basename(f))
        except Exception as e:
            logger.warning("Erro na limpeza do cache: %s", e)

    # ------------------------------------------------------------------
    # Estrategias de acesso (cookies / clientes alternativos)
    # ------------------------------------------------------------------
    def _strategies(self, cookie_file: Optional[str] = None) -> List[Tuple[str, Dict[str, Any]]]:
        """Ordem: cookies -> cookies+web_safari -> anonimo -> embed -> alternativos."""
        strategies: List[Tuple[str, Dict[str, Any]]] = []

        def with_clients(clients: List[str], use_cookies: bool = True) -> Dict[str, Any]:
            if use_cookies and cookie_file:
                # O yt-dlp descarta silenciosamente os clientes sem suporte a
                # cookies; filtra-los evita tentativas que nunca rodam.
                clients = [c for c in clients if c not in NO_COOKIE_CLIENTS] or list(clients)
            opts: Dict[str, Any] = {"extractor_args": {"youtube": {"player_client": clients}}}
            if use_cookies and cookie_file:
                opts["cookiefile"] = cookie_file
            return opts

        if cookie_file:
            strategies.append(("cookies", {"cookiefile": cookie_file}))
            # Com sessao logada, o web_safari e o unico cliente que devolve
            # 1080p em video +18; os padrao respondem "content is age-restricted".
            strategies.append(("cookies+web_safari", with_clients(AUTH_PLAYER_CLIENTS)))

        strategies.append(("anonimo", {}))

        # Clientes de embed conseguem abrir boa parte dos videos +18 mesmo sem login.
        strategies.append(("embed-age-gate", with_clients(AGE_GATE_PLAYER_CLIENTS)))
        strategies.append(("clientes-alternativos", with_clients(FALLBACK_PLAYER_CLIENTS)))

        if self._preferred_strategy:
            strategies.sort(key=lambda s: 0 if s[0] == self._preferred_strategy else 1)
        return strategies

    def _try_strategy(self, name: str, base_opts: Dict[str, Any], extra: Dict[str, Any],
                      action: str, runner: Callable[[Dict[str, Any]], Any]):
        opts = dict(base_opts)
        opts.update(extra)
        # Sem isso o yt-dlp nao resolve o "n challenge" e devolve o video sem
        # nenhum formato utilizavel.
        opts.setdefault("js_runtimes", JS_RUNTIMES)
        result = runner(opts)
        if name != "anonimo":
            logger.info("Sucesso ao %s usando a estrategia '%s'", action, name)
        self._preferred_strategy = name
        return result

    def _run_with_fallbacks(self, base_opts: Dict[str, Any], action: str, runner: Callable[[Dict[str, Any]], Any]):
        with self._disposable_cookies() as cookie_file:
            return self._run_all_strategies(base_opts, action, runner, cookie_file)

    def _run_all_strategies(self, base_opts: Dict[str, Any], action: str,
                            runner: Callable[[Dict[str, Any]], Any], cookie_file: Optional[str]):
        best_err = ""
        best_score = -1
        auth_error_seen = False

        def _record(err: str):
            """Guarda o erro mais informativo, nao o ultimo."""
            nonlocal best_err, best_score
            score = _error_score(err)
            if score > best_score:
                best_err, best_score = err, score

        for name, extra in self._strategies(cookie_file):
            try:
                return self._try_strategy(name, base_opts, extra, action, runner)
            except yt_dlp.utils.DownloadError as e:
                err = str(e)
                _record(err)
                auth_error_seen = auth_error_seen or _needs_auth(err)
                logger.warning("Estrategia '%s' falhou ao %s: %s", name, action, err.replace("\n", " ")[:200])
                if _is_terminal(err):
                    break
            except Exception as e:
                _record(str(e))
                logger.warning("Estrategia '%s' indisponivel: %s", name, str(e)[:200])

        last_err = best_err

        # O YouTube pediu login e ainda nao ha cookies salvos: tenta pegar a
        # sessao direto do navegador instalado (Chrome/Edge/Firefox/Brave...).
        if auth_error_seen and not find_cookie_file() and not self._browser_import_tried:
            self._browser_import_tried = True
            logger.info("Tentando importar cookies do navegador automaticamente...")
            imported = auto_import_from_browser()
            if imported:
                logger.info("Cookies importados do navegador: %s", os.path.basename(imported))
                with self._disposable_cookies() as fresh:
                    for name, extra in (
                        ("cookies-auto", {"cookiefile": fresh}),
                        ("cookies-auto+web_safari", {
                            "cookiefile": fresh,
                            "extractor_args": {"youtube": {"player_client": AUTH_PLAYER_CLIENTS}},
                        }),
                    ):
                        try:
                            return self._try_strategy(name, base_opts, extra, action, runner)
                        except Exception as e:
                            _record(str(e))
                            last_err = best_err
                            logger.warning("Estrategia '%s' falhou ao %s: %s", name, action, str(e)[:200])

        # Sem cookies e com o YouTube exigindo login: instrucao direta.
        if not find_cookie_file() and (auth_error_seen or _needs_auth(last_err)):
            raise RuntimeError(
                f"O YouTube exige login para {action} este video (restricao de idade ou anti-bot).\n\n"
                "Como resolver em 10 segundos:\n"
                "1. Clique em 'Configuracoes' (topo da pagina)\n"
                "2. Va ate 'Acesso ao YouTube (Cookies)'\n"
                "3. Clique em 'Importar cookies do navegador'\n\n"
                "Se o navegador bloquear a leitura, use a opcao de enviar o arquivo 'cookies.txt' "
                "exportado pela extensao 'Get cookies.txt LOCALLY'. Tutorial completo em TUTORIAL_COOKIES.md"
            )

        raise RuntimeError(_friendly_error(last_err, action))

    # ------------------------------------------------------------------
    def extract_info(self, url: str) -> Dict[str, Any]:
        url = normalize_url(url)
        base_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "extractor_retries": 3,
        }

        def _runner(opts: Dict[str, Any]) -> Dict[str, Any]:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info.get("_type") == "playlist" and info.get("entries"):
                    info = info["entries"][0]
                return {
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail"),
                    "channel": info.get("uploader") or info.get("channel"),
                    "description": (info.get("description") or "")[:300],
                    "view_count": info.get("view_count", 0),
                    "age_limit": info.get("age_limit", 0),
                    "url": url,
                }

        return self._run_with_fallbacks(base_opts, "analisar", _runner)

    def fetch_captions(self, url: str, languages: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Baixa as legendas pelo yt-dlp (usando os cookies) e devolve segmentos.

        Serve de rede de seguranca quando a youtube-transcript-api e bloqueada,
        o que acontece justamente nos videos com restricao de idade.
        """
        url = normalize_url(url)
        languages = languages or ["pt", "pt-BR", "en", "es"]

        base_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "extractor_retries": 2,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": languages,
        }

        def _runner(opts: Dict[str, Any]) -> Dict[str, Any]:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = self._run_with_fallbacks(base_opts, "obter legendas de", _runner)
        track = _pick_caption_track(info, languages)
        if not track:
            return []

        try:
            import requests
            resp = requests.get(track["url"], timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            body = resp.text
        except Exception as e:
            logger.warning("Falha ao baixar a legenda (%s): %s", track.get("ext"), e)
            return []

        if track.get("ext") == "json3":
            return _parse_json3(body)
        return _parse_vtt(body)

    def download_video(
        self,
        url: str,
        video_id: str,
        ffmpeg_path: Optional[str] = None,
        progress_hook: Optional[Callable[[float], None]] = None,
    ) -> str:
        url = normalize_url(url)
        output_template = os.path.join(self.download_dir, f"{video_id}.%(ext)s")
        target_file = os.path.join(self.download_dir, f"{video_id}.mp4")

        if os.path.exists(target_file) and os.path.getsize(target_file) > 100_000:
            logger.info("Video em cache: %s", target_file)
            return target_file

        def _progress_hook(d: Dict[str, Any]):
            if progress_hook and d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    pct = min(99.0, (downloaded / total) * 100.0)
                    progress_hook(pct)
            elif progress_hook and d.get("status") == "finished":
                progress_hook(100.0)

        base_opts = {
            "format": VIDEO_FORMAT,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 60,
            "retries": 5,
            "fragment_retries": 5,
            "extractor_retries": 3,
            "concurrent_fragment_downloads": 4,
            "nocheckcertificate": True,
            "progress_hooks": [_progress_hook],
        }
        if ffmpeg_path:
            base_opts["ffmpeg_location"] = ffmpeg_path

        def _runner(opts: Dict[str, Any]):
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

        self._run_with_fallbacks(base_opts, "baixar", _runner)

        if os.path.exists(target_file) and os.path.getsize(target_file) > 100_000:
            return target_file

        for f in os.listdir(self.download_dir):
            if f.startswith(video_id) and f.endswith((".mp4", ".mkv", ".webm")):
                fp = os.path.join(self.download_dir, f)
                if os.path.getsize(fp) > 100_000:
                    return fp

        raise FileNotFoundError(f"Nao foi possivel localizar o video baixado para o ID {video_id}")
