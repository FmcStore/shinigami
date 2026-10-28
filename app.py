"""Shinigami REST API — FastAPI proxy/normalizer for api.shngm.io (11.shinigami.asia)."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Pretty-print all JSON: custom default_response_class (indent=2, sorted off,
# ensure_ascii=False so unicode titles render as-is).
class PrettyJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        import json
        return (json.dumps(content, ensure_ascii=False, indent=2, default=str)
                + "\n").encode("utf-8")

API_BASE = "https://api.shngm.io"
SLIDER_BASE = "https://slider.shinigami.io"
EXPLORE_BASE = "https://explore.shngm.io"
MIRRORS = ["https://storage.shngm.id", "https://delivery.shngm.id",
           "https://mirror1.shngm.id", "https://mirror2.shngm.id"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CACHE_TTL = 60
CACHE_MAX_ENTRIES = 512
PAGE_SIZE_DEFAULT = 10
PAGE_SIZE_MAX = 24

app = FastAPI(title="Shinigami API", version="1.0.1",
              description="REST API proxy for 11.shinigami.asia (upstream api.shngm.io)",
              default_response_class=PrettyJSONResponse)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_cache: dict[str, tuple[float, Any]] = {}


class UpstreamError(Exception):
    def __init__(self, status: int, message: str, source: str = ""):
        self.status = status
        self.message = message
        self.source = source


async def fetch_json(url: str, params: Optional[dict] = None) -> Any:
    """GET an upstream JSON API with in-memory cache keyed by full URL+querystring."""
    key = url + ("?" + urlencode(params, doseq=True) if params else "")
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    # Evict expired/stale entries first; hard-cap total keys (oldest first).
    for k in [k for k, (t, _) in _cache.items() if now - t >= CACHE_TTL]:
        del _cache[k]
    while len(_cache) >= CACHE_MAX_ENTRIES:
        _cache.pop(next(iter(_cache)))
    try:
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": UA}) as client:
            r = await client.get(url, params=params)
    except (httpx.HTTPError, OSError) as e:
        detail = type(e).__name__ + (f": {e}" if isinstance(e, httpx.HTTPError) else "")
        raise UpstreamError(502, f"upstream network error ({detail})", key) from e
    if r.status_code >= 500:
        raise UpstreamError(502, f"upstream server error {r.status_code}", key)
    if r.status_code >= 400:
        raise UpstreamError(404, f"upstream not found ({r.status_code})", key)
    try:
        payload = r.json()
    except ValueError as e:
        raise UpstreamError(502, "upstream returned non-JSON response", key) from e
    _cache[key] = (now, payload)
    return payload


async def upstream(base: str, path: str, params: Optional[dict] = None) -> tuple[Any, Optional[dict], str]:
    """Fetch envelope API; returns (data, meta, source_url)."""
    url = base + path
    source = url + ("?" + urlencode(params, doseq=True) if params else "")
    payload = await fetch_json(url, params)
    if not isinstance(payload, dict) or "data" not in payload:
        # slider.shinigami.io returns a bare list without envelope
        if isinstance(payload, list):
            return payload, None, source
        raise UpstreamError(502, f"unexpected upstream envelope for {source}", source)
    if payload.get("retcode") not in (0, None):
        raise UpstreamError(502, f"upstream retcode={payload.get('retcode')}: {payload.get('message')}", source)
    return payload.get("data"), payload.get("meta"), source


def err_response(status: int, message: str, source: str = "") -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": True, "status": status,
                                                     "message": message, "source": source})


@app.exception_handler(UpstreamError)
async def upstream_error_handler(_req: Request, exc: UpstreamError) -> JSONResponse:
    return err_response(exc.status, exc.message, exc.source)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_req: Request, exc: RequestValidationError) -> JSONResponse:
    return err_response(400, f"invalid parameter: {exc.errors()[0].get('msg', 'validation failed')}")


def clamp_page(page: int, page_size: int) -> tuple[int, int, bool]:
    ps = max(1, min(page_size, PAGE_SIZE_MAX))
    return max(1, page), ps, ps != page_size


def images_for(chapter_data: dict) -> list[dict]:
    base = chapter_data.get("base_url", "")
    base_low = chapter_data.get("base_url_low") or base
    path = (chapter_data.get("chapter") or {}).get("path", "")
    files = (chapter_data.get("chapter") or {}).get("data") or []
    images = []
    for i, f in enumerate(files):
        entry = {"index": i, "file": f,
                 "url": f"{base}{path}{f}",
                 "url_low": f"{base_low}{path}{f}",
                 "mirrors": [f"{m}{path}{f}" for m in MIRRORS]}
        images.append(entry)
    return images


LIST_PARAMS = {"page", "page_size", "q", "type", "format", "category", "genre_include",
               "is_recommended", "is_update", "sort", "sort_order"}


def list_params(request: Request, page: int, page_size: int) -> tuple[dict, dict]:
    page, ps, clamped = clamp_page(page, page_size)
    out: dict[str, Any] = {"page": page, "page_size": ps}
    for k in request.query_params.keys():
        if k in ("page", "page_size"):
            continue
        if k not in LIST_PARAMS:
            raise UpstreamError(400, f"unknown parameter: {k}")
        if k == "genre_include":
            out.setdefault("genre_include", []).extend(request.query_params.getlist(k))
        else:
            out[k] = request.query_params.get(k)
    extra = {"_page_size_clamped": ps != page_size} if clamped else {}
    return out, extra


# ---------------------------------------------------------------- root / catalog

@app.get("/")
async def catalog() -> dict:
    return {
        "name": "Shinigami API",
        "upstream": [API_BASE, SLIDER_BASE, EXPLORE_BASE],
        "cache_ttl_seconds": CACHE_TTL,
        "endpoints": [
            "GET /api/home",
            "GET /api/manga/list?page=&page_size=&q=&format=&type=&category=&genre_include=&is_recommended=&is_update=&sort=&sort_order=",
            "GET /api/manga/top?filter=daily|weekly|all_time&page=&page_size=",
            "GET /api/manga/{manga_id}",
            "GET /api/manga/{manga_id}/chapters (latest only — upstream has no full chapter list)",
            "GET /api/chapter/{chapter_id}",
            "GET /api/genres | /api/types | /api/formats",
            "GET /api/authors?q= | /api/artists?q=",
            "GET /api/announcements?page=&page_size=",
            "GET /api/slider",
            "GET /api/search?q=",
            "GET /api/explore",
            "GET /api/random",
            "GET /api/health",
        ],
        "notes": "Auth-only upstream endpoints (user/profile, bookmark, readlist, history, auth/supabase, check-premium) are out of scope.",
    }


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "ts": int(time.time())}


@app.get("/api/home")
async def home():
    async def safe(coro_name: str, fn, *a, **kw):
        try:
            return await fn(*a, **kw)
        except UpstreamError as e:
            return {"error": e.message, "status": e.status}

    slider, _, slider_src = await upstream(SLIDER_BASE, "/v1/slider/web")
    ann, _, ann_src = await upstream(API_BASE, "/v1/announcement/list", {"page": 1, "page_size": 5})

    async def top_fetch(f: str):
        try:
            d, _, _ = await upstream(API_BASE, "/v1/manga/top", {"filter": f, "page": 1, "page_size": 10})
            return f, d
        except UpstreamError as e:
            return f, {"error": e.message, "status": e.status}

    latest, latest_meta, latest_src = await upstream(API_BASE, "/v1/manga/list",
                                                     {"page": 1, "page_size": PAGE_SIZE_MAX,
                                                      "sort": "latest", "sort_order": "desc", "is_update": "true"})
    tops = {}
    for f, d in await asyncio.gather(*(top_fetch(f) for f in ("daily", "weekly", "all_time"))):
        tops[f] = d
    return {
        "slider": slider,
        "announcements": ann,
        "top": tops,
        "latest_update": latest,
        "sources": {"slider": slider_src, "announcements": ann_src, "latest_update": latest_src},
    }


# ---------------------------------------------------------------- manga

@app.get("/api/manga/list")
async def manga_list(request: Request, page: int = Query(1, ge=1), page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1)):
    params, extra = list_params(request, page, page_size)
    data, meta, source = await upstream(API_BASE, "/v1/manga/list", params)
    out = {"data": data, "meta": meta, "source": source}
    out.update(extra)
    return out


@app.get("/api/manga/top")
async def manga_top(request: Request, filter: str = "daily", page: int = 1, page_size: int = PAGE_SIZE_DEFAULT):
    if filter not in ("daily", "weekly", "all_time"):
        raise UpstreamError(400, "filter must be daily|weekly|all_time")
    page, ps, clamped = clamp_page(page, page_size)
    params: dict[str, Any] = {"filter": filter, "page": page, "page_size": ps}
    data, meta, source = await upstream(API_BASE, "/v1/manga/top", params)
    out = {"data": data, "meta": meta, "source": source}
    if clamped:
        out["_page_size_clamped"] = True
    return out


@app.get("/api/manga/{manga_id}")
async def manga_detail(manga_id: str):
    data, meta, source = await upstream(API_BASE, f"/v1/manga/detail/{manga_id}")
    if not isinstance(data, dict) or not data:
        raise UpstreamError(404, f"manga {manga_id} not found", source)
    chapters_meta = {
        "latest_chapter_id": data.get("latest_chapter_id"),
        "latest_chapter_number": data.get("latest_chapter_number"),
        "latest_chapter_time": data.get("latest_chapter_time"),
        "note": "Upstream provides no full chapter-list endpoint; use latest_chapter_id with /api/chapter/{id} and traverse prev_chapter_id for older chapters.",
    }
    return {"data": data, "chapters": chapters_meta, "meta": meta, "source": source}


@app.get("/api/manga/{manga_id}/chapters")
async def manga_chapters(manga_id: str):
    data, _, source = await upstream(API_BASE, f"/v1/manga/detail/{manga_id}")
    if not isinstance(data, dict) or not data:
        raise UpstreamError(404, f"manga {manga_id} not found", source)
    latest_id = data.get("latest_chapter_id")
    latest = None
    if latest_id:
        cd, _, csrc = await upstream(API_BASE, f"/v1/chapter/detail/{latest_id}")
        latest = {
            "chapter_id": cd.get("chapter_id"),
            "chapter_number": cd.get("chapter_number"),
            "chapter_title": cd.get("chapter_title"),
            "release_date": cd.get("release_date"),
            "prev_chapter_id": cd.get("prev_chapter_id"),
            "source": csrc,
        }
    return {
        "manga_id": manga_id,
        "latest": latest,
        "chapters": [],
        "explanation": "Upstream has no chapter-list endpoint. Start from 'latest' and walk prev_chapter_id via /api/chapter/{chapter_id} to enumerate older chapters.",
    }


# ---------------------------------------------------------------- chapter

@app.get("/api/chapter/{chapter_id}")
async def chapter_detail(chapter_id: str):
    data, meta, source = await upstream(API_BASE, f"/v1/chapter/detail/{chapter_id}")
    if not isinstance(data, dict) or not data:
        raise UpstreamError(404, f"chapter {chapter_id} not found", source)
    return {
        "chapter_id": data.get("chapter_id"),
        "manga_id": data.get("manga_id"),
        "chapter_number": data.get("chapter_number"),
        "chapter_title": data.get("chapter_title"),
        "release_date": data.get("release_date"),
        "images": images_for(data),
        "pagination": {
            "prev_chapter_id": data.get("prev_chapter_id"),
            "prev_chapter_number": data.get("prev_chapter_number"),
            "next_chapter_id": data.get("next_chapter_id"),
            "next_chapter_number": data.get("next_chapter_number"),
        },
        "meta": meta,
        "source": source,
    }


# ---------------------------------------------------------------- taxonomies & people

async def taxonomy_list(path: str, q: str | None, page: int, page_size: int):
    page, ps, clamped = clamp_page(page, page_size)
    params: dict[str, Any] = {"page": page, "page_size": ps}
    if q:
        params["q"] = q
    data, meta, source = await upstream(API_BASE, path, params)
    out = {"data": data, "meta": meta, "source": source}
    if clamped:
        out["_page_size_clamped"] = True
    return out


@app.get("/api/genres")
async def genres(page: int = 1, page_size: int = PAGE_SIZE_DEFAULT):
    return await taxonomy_list("/v1/genre/list", None, page, page_size)


@app.get("/api/types")
async def types(page: int = 1, page_size: int = PAGE_SIZE_DEFAULT):
    return await taxonomy_list("/v1/type/list", None, page, page_size)


@app.get("/api/formats")
async def formats(page: int = 1, page_size: int = PAGE_SIZE_DEFAULT):
    return await taxonomy_list("/v1/format/list", None, page, page_size)


@app.get("/api/authors")
async def authors(request: Request, q: str | None = None, page: int = 1, page_size: int = PAGE_SIZE_DEFAULT):
    return await taxonomy_list("/v1/author/list", q, page, page_size)


@app.get("/api/artists")
async def artists(request: Request, q: str | None = None, page: int = 1, page_size: int = PAGE_SIZE_DEFAULT):
    return await taxonomy_list("/v1/artist/list", q, page, page_size)


@app.get("/api/announcements")
async def announcements(page: int = 1, page_size: int = PAGE_SIZE_DEFAULT):
    page, ps, clamped = clamp_page(page, page_size)
    data, meta, source = await upstream(API_BASE, "/v1/announcement/list",
                                        {"page": page, "page_size": ps})
    out = {"data": data, "meta": meta, "source": source}
    if clamped:
        out["_page_size_clamped"] = True
    return out


@app.get("/api/slider")
async def slider():
    data, _, source = await upstream(SLIDER_BASE, "/v1/slider/web")
    return {"data": data, "source": source}


@app.get("/api/search")
async def search(request: Request, q: str = "", page: int = 1, page_size: int = PAGE_SIZE_DEFAULT):
    if not q.strip():
        raise UpstreamError(400, "q is required")
    page, ps, clamped = clamp_page(page, page_size)
    params: dict[str, Any] = {"q": q, "page": page, "page_size": ps}
    data, meta, source = await upstream(API_BASE, "/v1/manga/list", params)
    out = {"query": q, "data": data, "meta": meta, "source": source}
    if clamped:
        out["_page_size_clamped"] = True
    return out


@app.get("/api/explore")
async def explore():
    layout, _, source = await fetch_json(f"{EXPLORE_BASE}/v1/web"), None, f"{EXPLORE_BASE}/v1/web"
    sections: list[dict] = []

    async def resolve(cat: str, size: Any):
        try:
            data, meta, src = await upstream(API_BASE, "/v1/manga/list",
                                             {"page": 1, "page_size": PAGE_SIZE_MAX, "category": cat})
            return {"category": cat, "manga": data, "source": src}
        except UpstreamError as e:
            return {"category": cat, "error": e.message, "status": e.status}

    tabs = layout.get("tabs") or []
    main = layout.get("main_section") or {}
    all_sections = ([{"id": "main", "title": "main_section", "content": main.get("content", [])}] +
                    [{"id": t.get("id"), "title": t.get("title"), "content": t.get("sections", [])}
                     for t in tabs])
    for tab in all_sections:
        entries = []
        for sec in tab.get("content", []):
            for item in sec.get("content", []) if "content" in sec and isinstance(sec.get("content"), list) else [sec]:
                if not isinstance(item, dict):
                    continue
                cat = item.get("category")
                typ = item.get("type")
                if typ == "list" and cat:
                    entries.append(await resolve(cat, item.get("size")))
                elif typ == "slider":
                    entries.append({"category": cat, "type": "slider",
                                    "hint": "use /api/slider"})
                else:
                    entries.append(item)
        sections.append({"id": tab.get("id"), "title": tab.get("title"), "items": entries})
    return {"layout_source": source, "sections": sections}


@app.get("/api/random")
async def random_manga():
    import random as _random
    page = _random.randint(1, 50)
    ps = PAGE_SIZE_MAX
    data, meta, source = await upstream(API_BASE, "/v1/manga/list",
                                        {"page": page, "page_size": ps, "sort_order": "desc"})
    if not data:
        raise UpstreamError(404, "no manga found", source)
    pick = _random.choice(data)
    return {"data": pick, "pick_page": page, "source": source}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8787)
