# Shinigami API

REST API (FastAPI, port 8787) yang mem-proxy & menyeragamkan API backend publik **11.shinigami.asia** (`api.shngm.io`, `slider.shinigami.io`, `explore.shngm.io`). Live-fetch + in-memory cache TTL 60s, tanpa penyimpanan permanen. JSON-only, CORS open.

## Menjalankan

```bash
~/.venvs/shinigami/bin/python app.py
# atau
~/.venvs/shinigami/bin/uvicorn app:app --host 0.0.0.0 --port 8787
# atau Docker
docker build -t shinigami-api . && docker run -p 8787:8787 shinigami-api
```

## Endpoint (prefix `/api`)

| Endpoint | Keterangan |
|---|---|
| `GET /` | Katalog endpoint |
| `GET /api/home` | Slider + announcements + top daily/weekly/all_time + latest update |
| `GET /api/manga/list` | Passthrough: `page,page_size(max 24, di-clamp),q,format,type,category,genre_include(repeatable),is_recommended,is_update,sort,sort_order` |
| `GET /api/manga/top?filter=daily\|weekly\|all_time` | Top manga |
| `GET /api/manga/{manga_id}` | Detail lengkap + `chapters` meta ringkas (latest_chapter_*) |
| `GET /api/manga/{manga_id}/chapters` | `latest` chapter + penjelasan traversal (upstream tidak punya endpoint list chapter penuh) |
| `GET /api/chapter/{chapter_id}` | Detail + `images[]` (URL absolut high & low + varian mirror) + prev/next |
| `GET /api/genres` `/api/types` `/api/formats` | Taksonomi |
| `GET /api/authors?q=` `/api/artists?q=` | Paged |
| `GET /api/announcements` | Paged |
| `GET /api/slider` | Slider homepage |
| `GET /api/search?q=` | Alias `manga/list?q=` |
| `GET /api/explore` | Layout explore + resolve tiap category list ke manga |
| `GET /api/random` | Manga acak |
| `GET /api/health` | Health check |

## Error mapping

- Upstream 4xx → **404** (manga/chapter tidak ada)
- Upstream 5xx / network error → **502**
- Param invalid / tidak dikenal → **400**
- Format error: `{"error":true,"status":N,"message":"...","source":"<upstream url>"}`

## Cache & clamp

- Cache in-memory TTL 60 detik, key = URL + querystring penuh.
- `page_size` di-clamp ke 1..24; bila di-clamp, response menyertakan `"_page_size_clamped": true`.
- Setiap response sukses menyertakan `"source"` (URL upstream asli).

## Smoke test

```bash
bash templates/smoke.sh http://127.0.0.1:8787   # verdict ke stderr
```

## Out of scope

Endpoint auth-only upstream (user/profile, bookmark/*, readlist/*, history/*, auth/supabase/*, check-premium) tidak disediakan.
