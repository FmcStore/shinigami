# Changelog — Shinigami API

## 1.0.2 (2026-10-25) — Pretty print
- Semua response JSON kini pretty-print (indent 2, ensure_ascii=False) via custom `PrettyJSONResponse` sebagai default_response_class — terbaca langsung di curl tanpa jq/post-processing. Smoke 23/23 PASS setelah perubahan.

## 1.0.1 (2026-10-25) — QA fix release (Rina, Lead Review)

Semua 23 smoke check: PASS (templates/smoke.sh, live di 127.0.0.1:8787).

### Fixed
- **Validasi `page`/`page_size`** pada `/api/manga/list`: sekarang `Query(ge=1)` + handler global `RequestValidationError` → **400** dengan envelope error seragam (sebelumnya 422 FastAPI default, menyimpang dari kontrak "param invalid → 400"). Terverifikasi: `?page=abc` dan `?page=0` → 400.
- **502 message** dari network error tidak lagi menyertakan repr exception httpx mentah; kini hanya `TypeName: pesan` singkat (menghindari kebocoran detail internal).

### Changed
- **`/api/home`**: 3 fetch `manga/top` (daily/weekly/all_time) kini berjalan **paralel** via `asyncio.gather` dengan penanganan error per-fetch (hasil gagal → `{"error":..., "status":...}` per key, sesuai gaya fail-soft endpoint lain).
- **Cache in-memory**: dibatasi maksimum 512 key (`CACHE_MAX_ENTRIES`); entri kedaluwarsa di-evict saat tulis, dan saat penuh key tertua (insertion-order/FIFO) dibuang — tidak lagi unbounded.

### Catatan rilis
- Kontrak respons lain tidak berubah; tidak ada endpoint baru/dihapus.
- Perbaikan ini menutup 4 temuan minor QA (Agus). Tidak ada blocker; ACC untuk rilis 1.0.1.
- Server di-reload saat pengujian; jalankan ulang `~/.venvs/shinigami/bin/python app.py` bila perlu.
