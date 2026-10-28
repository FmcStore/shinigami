# PRD — Shinigami REST API (11.shinigami.asia)

## Context
- Situs https://11.shinigami.asia/ = SvelteKit SPA, diblok Cloudflare untuk HTTP polos (403 "Just a moment"), TAPI API backend-nya TERBUKA (tanpa Cloudflare, tanpa auth untuk endpoint publik):
  - `https://api.shngm.io/v1/...` (utama)
  - `https://slider.shinigami.io/v1/...` (slider homepage)
  - `https://explore.shngm.io/v1/web` (layout explore)
  - `https://ads.shinigami.io/v1/pages/{homepage,explore,search}` (slot iklan; boleh diabaikan)
- Envelope upstream: `{"retcode":0,"message":"success","meta":{...},"data":...}`.

## Kontrak upstream terverifikasi (live, 2026-10-25)
- `GET /v1/manga/list` params: `page`, `page_size` (default 10, max teramati 24; clamp), `q` (search), `type`, `format` (manga|manhua|manhwa), `category` (explore-list-1..3), `genre_include` (slug, repeatable), `is_recommended`, `is_update`, `sort` (latest), `sort_order` (desc). Envelope meta: total_page, total_record (max 1000 di window).
- `GET /v1/manga/top` params: `filter` (daily|weekly|all_time), `page`, `page_size`.
- `GET /v1/manga/detail/{manga_id}` — detail lengkap (taxonomy, user_rate, view_count, dst). chapters array kosong dari endpoint ini; ambil chapter terbaru dari `latest_chapter_id`.
- `GET /v1/chapter/detail/{chapter_id}` — data halaman baca: `base_url` + `chapter.path` + `chapter.data[]` (nama file) = URL gambar penuh. Terverifikasi: `base_url + path + file` -> 200 image. Juga `prev/next_chapter_id`.
- `GET /v1/genre/list`, `/v1/type/list`, `/v1/format/list`, `/v1/author/list?q=`, `/v1/artist/list?q=` (paged).
- `GET /v1/announcement/list?page&page_size`.
- `GET https://slider.shinigami.io/v1/slider/web`.
- Mirror gambar (fallback/opsional): storage.shngm.id, delivery.shngm.id, mirror1/2.shngm.id.
- Auth-only (OUT OF SCOPE, jawab 405/401): user/profile, bookmark/*, readlist/*, history/*, auth/supabase/*, check-premium.

## Goals
REST API JSON-only (FastAPI, port 8787) yang mem-proxy & menyeragamkan data di atas, live-fetch + cache TTL singkat (60s), tanpa penyimpanan permanen.

## Must
- Endpoint wajib (prefix `/api`):
  - `GET /` katalog endpoint (JSON)
  - `GET /api/home` — slider + announcement + top daily/weekly/all_time + latest update (fan-out paralel)
  - `GET /api/manga/list` (passthrough param: page,page_size,q,format,type,category,genre_include,is_recommended,is_update,sort,sort_order)
  - `GET /api/manga/top?filter=daily|weekly|all_time`
  - `GET /api/manga/{manga_id}` (detail + chapters meta ringkas: latest_chapter_*)
  - `GET /api/manga/{manga_id}/chapters` — daftar chapter: TURUN dari detail? TIDAK ADA endpoint list chapter upstream. Solusi: kembalikan dari `chapter.detail` traversal TIDAK memungkinkan utk list penuh -> sediakan `latest` + penjelasan; PLUS endpoint `/api/chapter/{chapter_id}` yang mengembalikan detail + `images[]` URL penuh (base_url+path+file, plus varian mirror).
  - `GET /api/chapter/{chapter_id}` — detail + images[] (absolut, high & low) + prev/next
  - `GET /api/genres|/api/types|/api/formats`
  - `GET /api/authors?q=`, `/api/artists?q=`
  - `GET /api/announcements`
  - `GET /api/slider`
  - `GET /api/search?q=` (alias manga/list?q=)
  - `GET /api/explore` (explore.shngm.io/v1/web + resolve tiap category list ke manga)
  - `GET /api/random` (resolve via manga/list random page)
- Error mapping: upstream 4xx -> 404 (manga/chapter tidak ada), 5xx/network -> 502; param invalid -> 400.
- CORS open. Cache in-memory TTL 60s keyed by full querystring.
- README.md + smoke test bash (templates/smoke.sh style, verdict ke stderr).

## Should
- per_pageClamped info bila di-clamp. `source` field berisi URL upstream asli per request.
- Dockerfile.

## Nice
- /api/db/* offline cache (SKIP — user mau live).

## Tech
Python 3.11 + FastAPI + httpx (di venv ~/.venvs/komikindo pattern). Project dir: ~/Projects/shinigami-api/.
