# Shinigami API — Kontrak REST (JSON-only)

Base URL: `http://127.0.0.1:8787` (FastAPI, port 8787). Semua respons JSON murni — **tidak ada HTML/dashboard**.

## Prinsip

1. **Envelope seragam** untuk SEMUA endpoint:
   ```json
   {
     "retcode": 0,
     "message": "success",
     "meta": { ... },
     "data": { ... }
   }
   ```
   Error mengikuti envelope yang sama dengan `retcode != 0`.
2. **Field `source`** di `meta` berisi URL upstream asli per request (Should).
3. **Cache** in-memory TTL 60s, keyed by full querystring. Header `X-Cache: HIT|MISS` diresponse.
4. **CORS open** (`Access-Control-Allow-Origin: *`).
5. Tanpa penyimpanan permanen; live-fetch saja.

## Error mapping (WAJIB)

| Kondisi | HTTP | retcode | message contoh |
|---|---|---|---|
| Param invalid (filter di luar daily/weekly/all_time, page_size > clamp, dsb.) | 400 | 400 | `"invalid parameter: filter must be daily|weekly|all_time"` |
| Manga/chapter/entitas tidak ada (upstream 4xx) | 404 | 404 | `"manga not found: {id}"` |
| Upstream 5xx / network error / timeout | 502 | 502 | `"upstream error: {detail}"` |
| Method tidak didukung di endpoint auth-only | 405 | 405 | `"endpoint auth-only, out of scope"` |

Auth-only upstream (user/profile, bookmark/*, readlist/*, history/*, auth/supabase/*, check-premium) **tidak diproxy** — selalu 405/401.

## Endpoint (prefix `/api`)

### `GET /` — Katalog endpoint
JSON daftar semua endpoint + deskripsi singkat + versi. Bukan halaman HTML.

### `GET /api/home`
Fan-out paralel: slider + announcements + top (daily/weekly/all_time) + latest update.
```json
{ "retcode":0, "message":"success", "meta":{"source":"[...upstream urls...]","cache":"MISS"},
  "data": { "slider":[MangaCard], "announcement":[Announcement],
            "top":{ "daily":[MangaCard], "weekly":[MangaCard], "all_time":[MangaCard] },
            "latest":[MangaCard] } }
```

### `GET /api/manga/list`
Passthrough param: `page`, `page_size` (default 10, clamp ke 24), `q`, `type`, `format` (manga|manhua|manhwa), `category` (explore-list-1..3), `genre_include` (slug, repeatable), `is_recommended`, `is_update`, `sort` (latest), `sort_order` (desc).
`meta` upstream dipertahankan: `total_page`, `total_record` (max 1000 di window upstream).
Bila page_size di-clamp, tambahkan `meta.clamped: true` (Should).

### `GET /api/manga/top?filter=daily|weekly|all_time&page=1&page_size=10`
`filter` di luar 3 nilai valid → 400.

### `GET /api/manga/{manga_id}`
Detail lengkap (taxonomy, user_rate, view_count, dst) + meta chapter ringkas:
```json
"data": { ...detail_upstream..., "latest_chapter": { "id":"...", "number":"...", "title":"..." } }
```
Catatan: `chapters` array dari upstream kosong; jangan disi palsu.

### `GET /api/manga/{manga_id}/chapters`
TIDAK ada endpoint list chapter upstream — tidak memungkinkan list penuh. Respons jujur:
```json
"data": { "manga_id":"...", "note":"upstream tidak menyediakan full chapter list",
          "latest": { "id":"...", "number":"..." } }
```

### `GET /api/chapter/{chapter_id}`
Detail chapter + gambar absolut:
```json
"data": { "id":"...", "title":"...", "base_url":"https://...",
          "images": [ { "page":1, "high":"<base_url+path+file>", "low":"<varian mirror>" } ],
          "prev_chapter_id": "...", "next_chapter_id": "..." }
```
`high` = base_url + path + file (terverifikasi 200 image). Mirror fallback: storage.shngm.id, delivery.shngm.id, mirror1/2.shngm.id.

### `GET /api/genres` | `/api/types` | `/api/formats`
Paged passthrough (page, page_size).

### `GET /api/authors?q=` | `/api/artists?q=`
Paged + `q` passthrough.

### `GET /api/announcements?page=1&page_size=10`

### `GET /api/slider`
Proxy `https://slider.shinigami.io/v1/slider/web`.

### `GET /api/search?q=`
Alias dari `/api/manga/list?q=`. `q` kosong → 400.

### `GET /api/explore`
Proxy `explore.shngm.io/v1/web`, lalu resolve tiap category list ke item manga.

### `GET /api/random`
Resolve via manga/list (random page) → 1 manga card + detail minimal.

## Koordinasi implementasi
- File ini adalah sumber kebenaran kontrak respons; implementasi FastAPI (main.py, milik Budi) harus mematuhi struktur envelope & error mapping di atas tanpa mengubah file lain.
- Spec machine-readable: `docs/openapi.yaml`.
- Contoh request: `docs/examples/requests.http` dan `docs/examples/curl.sh`.
