"""Gerenciamento dos cookies do YouTube (restricao de idade / anti-bot).

O YouTube exige uma sessao logada para videos com restricao de idade (+18),
exclusivos para membros e sempre que dispara a verificacao anti-bot
("confirm you are not a bot"). Este modulo cuida de tudo que envolve esses
cookies:

* localizar um arquivo de cookies valido em storage/;
* aceitar o arquivo exportado por qualquer extensao (Netscape .txt ou JSON)
  e normalizar para o formato que o yt-dlp entende;
* importar os cookies direto do navegador instalado, sem extensao nenhuma;
* dizer, em portugues, o que esta faltando.
"""

import os
import glob
import json
import time
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("autoshorts.cookies")

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage"))
PRIMARY_COOKIE_FILE = os.path.join(STORAGE_DIR, "cookies.txt")

# Nomes aceitos dentro de storage/ (o usuario pode largar ali o arquivo
# exportado pela extensao, sem precisar renomear).
COOKIE_FILE_NAMES = (
    "cookies.txt",
    "youtube_cookies.txt",
    "www.youtube.com_cookies.txt",
    "youtube.com_cookies.txt",
)

NETSCAPE_HEADER = (
    "# Netscape HTTP Cookie File\n"
    "# Gerado pelo AutoShorts AI - nao edite manualmente.\n\n"
)

# Presenca de qualquer um desses cookies indica sessao realmente logada.
# Sem eles o YouTube continua barrando video com restricao de idade.
LOGIN_COOKIE_NAMES = (
    "__Secure-3PSID",
    "__Secure-1PSID",
    "SID",
    "SAPISID",
    "__Secure-3PAPISID",
    "LOGIN_INFO",
)

RELEVANT_DOMAINS = ("youtube.com", "youtube-nocookie.com", "google.com", "googlevideo.com")

# Ordem de tentativa ao importar cookies do navegador instalado.
BROWSER_ORDER = ("chrome", "edge", "brave", "firefox", "opera", "vivaldi", "chromium")

BROWSER_LABELS = {
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "brave": "Brave",
    "firefox": "Mozilla Firefox",
    "opera": "Opera",
    "vivaldi": "Vivaldi",
    "chromium": "Chromium",
    "safari": "Safari",
    "whale": "Whale",
}

# Linha: dominio, incluir subdominios, path, secure, expiracao, nome, valor
CookieRow = Tuple[str, str, str, str, int, str, str]


# ----------------------------------------------------------------------
# Localizacao / estado
# ----------------------------------------------------------------------
def find_cookie_file() -> Optional[str]:
    """Retorna o primeiro arquivo de cookies valido encontrado em storage/."""
    for name in COOKIE_FILE_NAMES:
        path = os.path.join(STORAGE_DIR, name)
        if os.path.isfile(path) and os.path.getsize(path) > 50:
            return os.path.abspath(path)

    # Qualquer *cookies*.txt solto na pasta storage tambem serve.
    for path in sorted(glob.glob(os.path.join(STORAGE_DIR, "*cookies*.txt"))):
        if os.path.isfile(path) and os.path.getsize(path) > 50:
            return os.path.abspath(path)
    return None


def cookies_status() -> Dict[str, Any]:
    """Estado detalhado do arquivo de cookies, para exibir no frontend."""
    path = find_cookie_file()
    if not path:
        return {
            "configured": False,
            "path": None,
            "filename": None,
            "has_youtube": False,
            "has_login": False,
            "total": 0,
            "youtube_cookies": 0,
            "expired": False,
            "age_days": None,
            "message": "Nenhum cookie configurado. Videos com restricao de idade vao falhar.",
        }

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            rows = _rows_from_text(f.read(), drop_expired=False)
    except OSError as e:
        return {
            "configured": False,
            "path": path,
            "filename": os.path.basename(path),
            "has_youtube": False,
            "has_login": False,
            "total": 0,
            "youtube_cookies": 0,
            "expired": False,
            "age_days": None,
            "message": f"Nao foi possivel ler o arquivo de cookies: {e}",
        }

    info = _summarize(rows)
    age_days = round((time.time() - os.path.getmtime(path)) / 86400, 1)

    if not info["has_youtube"]:
        message = "O arquivo enviado nao tem cookies do youtube.com. Exporte de novo com o YouTube aberto."
    elif info["expired"]:
        message = "Os cookies expiraram. Importe do navegador ou exporte o arquivo novamente."
    elif not info["has_login"]:
        message = ("Cookies do YouTube encontrados, mas sem sessao logada. Videos com restricao "
                   "de idade continuam bloqueados: exporte com a conta logada.")
    elif age_days > 25:
        message = f"Cookies com {age_days:.0f} dias. Se falhar, atualize em 'Importar do navegador'."
    else:
        message = "Cookies ativos. Videos com restricao de idade e anti-bot liberados."

    return {
        "configured": True,
        "path": path,
        "filename": os.path.basename(path),
        "has_youtube": info["has_youtube"],
        "has_login": info["has_login"],
        "total": info["total"],
        "youtube_cookies": info["youtube"],
        "expired": info["expired"],
        "age_days": age_days,
        "message": message,
    }


def available_browsers() -> List[Dict[str, str]]:
    """Navegadores que o yt-dlp consegue ler nesta maquina."""
    try:
        from yt_dlp.cookies import SUPPORTED_BROWSERS
    except Exception:
        SUPPORTED_BROWSERS = set(BROWSER_ORDER)

    ordered = [b for b in BROWSER_ORDER if b in SUPPORTED_BROWSERS]
    if os.name != "nt" and "safari" in SUPPORTED_BROWSERS:
        ordered.append("safari")
    return [{"id": b, "label": BROWSER_LABELS.get(b, b.title())} for b in ordered]


# ----------------------------------------------------------------------
# Parsing / normalizacao
# ----------------------------------------------------------------------
def _norm_bool(value: Any, default: str = "FALSE") -> str:
    text = str(value).strip().upper()
    if text in ("TRUE", "FALSE"):
        return text
    if text in ("1", "YES", "Y"):
        return "TRUE"
    if text in ("0", "NO", "N", ""):
        return "FALSE"
    return default


def _norm_expires(value: Any) -> int:
    try:
        return max(0, int(float(str(value).strip() or 0)))
    except (TypeError, ValueError):
        return 0


def _is_relevant(domain: str) -> bool:
    low = (domain or "").lower().lstrip(".")
    return any(low == d or low.endswith("." + d) for d in RELEVANT_DOMAINS)


def _rows_from_json(text: str) -> List[CookieRow]:
    """Extensoes tipo Cookie-Editor / EditThisCookie exportam JSON."""
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("cookies") or data.get("Cookies") or data.get("data") or []
    if not isinstance(data, list):
        return []

    rows: List[CookieRow] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("Name")
        domain = item.get("domain") or item.get("Domain")
        if not name or not domain:
            continue

        host_only = bool(item.get("hostOnly"))
        domain = str(domain)
        if not host_only and not domain.startswith("."):
            domain = "." + domain

        rows.append((
            domain,
            "FALSE" if host_only else "TRUE",
            str(item.get("path") or "/"),
            "TRUE" if item.get("secure") else "FALSE",
            _norm_expires(item.get("expirationDate") or item.get("expires") or 0),
            str(name),
            str(item.get("value") or ""),
        ))
    return rows


def _rows_from_netscape(text: str) -> List[CookieRow]:
    rows: List[CookieRow] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        elif line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 7:
            # Alguns exports trocam TAB por espacos; o valor pode ter espacos.
            parts = line.split()
            if len(parts) > 7:
                parts = parts[:6] + [" ".join(parts[6:])]
        if len(parts) == 6:
            parts.append("")  # cookie com valor vazio
        if len(parts) < 7:
            continue

        domain, include_sub, path, secure, expires, name, value = [p.strip() for p in parts[:7]]
        if not domain or not name:
            continue

        rows.append((
            domain,
            _norm_bool(include_sub, "TRUE" if domain.startswith(".") else "FALSE"),
            path or "/",
            _norm_bool(secure),
            _norm_expires(expires),
            name,
            value,
        ))
    return rows


def _rows_from_text(text: str, drop_expired: bool = True) -> List[CookieRow]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    stripped = text.lstrip()

    rows: List[CookieRow] = []
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            rows = _rows_from_json(stripped)
        except (ValueError, TypeError):
            rows = []
    if not rows:
        rows = _rows_from_netscape(text)

    if drop_expired:
        now = time.time()
        rows = [r for r in rows if r[4] == 0 or r[4] > now]
    return _dedupe(rows)


def _dedupe(rows: Iterable[CookieRow]) -> List[CookieRow]:
    seen: Dict[Tuple[str, str, str], CookieRow] = {}
    for row in rows:
        seen[(row[0].lower(), row[2], row[5])] = row
    return list(seen.values())


def _rows_from_jar(jar) -> List[CookieRow]:
    rows: List[CookieRow] = []
    for c in jar:
        if not c.name or not _is_relevant(c.domain):
            continue
        rows.append((
            c.domain,
            "TRUE" if (c.domain or "").startswith(".") else "FALSE",
            c.path or "/",
            "TRUE" if c.secure else "FALSE",
            _norm_expires(c.expires or 0),
            c.name,
            c.value or "",
        ))
    return _dedupe(rows)


def _summarize(rows: List[CookieRow]) -> Dict[str, Any]:
    now = time.time()
    youtube = [r for r in rows if "youtube.com" in r[0].lower()]
    login = [r for r in rows if r[5] in LOGIN_COOKIE_NAMES and r[6].strip()]
    live_youtube = [r for r in youtube if r[4] == 0 or r[4] > now]
    return {
        "total": len(rows),
        "youtube": len(youtube),
        "has_youtube": bool(youtube),
        "has_login": bool(login),
        "expired": bool(youtube) and not live_youtube,
    }


def _write_rows(rows: List[CookieRow], path: str = PRIMARY_COOKIE_FILE) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(NETSCAPE_HEADER)
        for domain, include_sub, cpath, secure, expires, name, value in rows:
            f.write(f"{domain}\t{include_sub}\t{cpath}\t{secure}\t{expires}\t{name}\t{value}\n")
    os.replace(tmp, path)

    # Confere que o yt-dlp consegue mesmo carregar o arquivo gerado.
    try:
        from yt_dlp.utils import YoutubeDLCookieJar
        YoutubeDLCookieJar(path).load(ignore_discard=True, ignore_expires=True)
    except Exception as e:
        try:
            os.remove(path)
        except OSError:
            pass
        raise ValueError(f"O arquivo de cookies gerado ficou invalido ({e}). Exporte novamente.")
    return path


def _cleanup_duplicate_files(keep: str) -> None:
    """Evita que um arquivo antigo em storage/ continue sendo escolhido."""
    keep_abs = os.path.abspath(keep)
    for path in glob.glob(os.path.join(STORAGE_DIR, "*cookies*.txt")):
        if os.path.abspath(path) != keep_abs:
            try:
                os.replace(path, path + ".bak")
            except OSError:
                pass


# ----------------------------------------------------------------------
# Entradas do usuario
# ----------------------------------------------------------------------
def save_cookies_from_text(text: str, source: str = "arquivo enviado") -> Dict[str, Any]:
    """Salva cookies colados/enviados pelo usuario em storage/cookies.txt."""
    if not text or not text.strip():
        raise ValueError("O conteudo enviado esta vazio.")

    rows = _rows_from_text(text)
    if not rows:
        raise ValueError(
            "Nao encontrei nenhum cookie valido nesse arquivo. Use a extensao "
            "'Get cookies.txt LOCALLY' e envie o .txt exportado (formato Netscape) "
            "ou o JSON do Cookie-Editor."
        )

    info = _summarize(rows)
    if not info["has_youtube"]:
        raise ValueError(
            "Esse arquivo nao contem cookies do youtube.com. Abra o YouTube logado, "
            "exporte os cookies com a aba do YouTube em primeiro plano e envie de novo."
        )

    path = _write_rows(rows)
    _cleanup_duplicate_files(path)
    logger.info("Cookies salvos em %s (%d cookies, login=%s)", path, len(rows), info["has_login"])

    status = cookies_status()
    status["imported"] = len(rows)
    status["source"] = source
    return status


def delete_cookies() -> Dict[str, Any]:
    """Remove todos os arquivos de cookies de storage/."""
    removed = []
    for path in glob.glob(os.path.join(STORAGE_DIR, "*cookies*.txt")):
        try:
            os.remove(path)
            removed.append(os.path.basename(path))
        except OSError as e:
            logger.warning("Nao foi possivel remover %s: %s", path, e)
    status = cookies_status()
    status["removed"] = removed
    return status


def _browser_error_pt(browser: str, err: str) -> str:
    label = BROWSER_LABELS.get(browser, browser)
    low = err.lower()
    if "could not find" in low and "cookies database" in low:
        return f"{label}: nao esta instalado (ou nao tem perfil) nesta maquina."
    if ("could not copy" in low or "permission" in low or "being used by another process" in low
            or "locked" in low or "in use" in low):
        return (f"{label}: o banco de cookies esta travado porque o navegador esta aberto. "
                f"Feche o {label} por completo (inclusive o icone ao lado do relogio) e tente de novo, "
                f"ou use o envio do arquivo cookies.txt, que funciona com o navegador aberto.")
    if "decrypt" in low or "dpapi" in low or "app-bound" in low:
        return (f"{label}: os cookies estao protegidos pela criptografia do Windows "
                f"(App-Bound Encryption). Use o envio do arquivo cookies.txt.")
    if "unsupported" in low:
        return f"{label}: nao e suportado nesta plataforma."
    return f"{label}: {err[:160]}"


def import_from_browser(browser: Optional[str] = None) -> Dict[str, Any]:
    """Le os cookies do navegador instalado e salva em storage/cookies.txt.

    Retorna o status dos cookies com a lista de tentativas por navegador.
    Levanta ValueError quando nenhum navegador entregou uma sessao logada.
    """
    from yt_dlp.cookies import extract_cookies_from_browser

    candidates = [browser] if browser else list(BROWSER_ORDER)
    attempts: List[Dict[str, Any]] = []

    for name in candidates:
        try:
            jar = extract_cookies_from_browser(name)
        except Exception as e:  # navegador ausente, banco travado, sem permissao
            attempts.append({"browser": name, "ok": False, "error": _browser_error_pt(name, str(e))})
            continue

        rows = _rows_from_jar(jar)
        info = _summarize(rows)
        label = BROWSER_LABELS.get(name, name)

        if not info["has_youtube"]:
            attempts.append({"browser": name, "ok": False,
                             "error": f"{label}: nenhum cookie do YouTube encontrado."})
            continue

        if not info["has_login"]:
            # Cookies existem mas sem sessao (ou o Windows nao deixou descriptografar).
            attempts.append({
                "browser": name, "ok": False,
                "error": (f"{label}: achei cookies do YouTube, mas sem sessao logada. "
                          f"Faca login no YouTube nesse navegador ou envie o arquivo cookies.txt."),
            })
            continue

        path = _write_rows(rows)
        _cleanup_duplicate_files(path)
        attempts.append({"browser": name, "ok": True, "cookies": len(rows)})
        logger.info("Cookies importados do %s (%d cookies)", name, len(rows))

        status = cookies_status()
        status["imported"] = len(rows)
        status["source"] = label
        status["browser"] = name
        status["attempts"] = attempts
        return status

    detail = " ".join(a["error"] for a in attempts if not a.get("ok"))[:600]
    raise ValueError(
        "Nao consegui importar uma sessao logada de nenhum navegador. "
        + (detail or "Nenhum navegador compativel foi encontrado.")
        + " Alternativa garantida: exporte o arquivo cookies.txt com a extensao "
          "'Get cookies.txt LOCALLY' e envie aqui."
    )


def auto_import_from_browser() -> Optional[str]:
    """Tentativa silenciosa usada pelo downloader quando o YouTube pede login."""
    try:
        import_from_browser()
    except Exception as e:
        logger.info("Auto-import de cookies do navegador nao funcionou: %s", str(e)[:200])
        return None
    return find_cookie_file()
