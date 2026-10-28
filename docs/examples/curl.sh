#!/usr/bin/env bash
# Contoh curl untuk semua endpoint publik Shinigami API (port 8787).
BASE="${1:-http://127.0.0.1:8787}"

set -x
curl -s "$BASE/"
curl -s "$BASE/api/home"
curl -s "$BASE/api/manga/list?page=1&page_size=10&sort=latest&sort_order=desc"
curl -s "$BASE/api/manga/list?format=manhwa&genre_include=action&is_update=true"
curl -s "$BASE/api/manga/top?filter=daily"
curl -s "$BASE/api/manga/top?filter=weekly"
curl -s "$BASE/api/manga/top?filter=all_time"
# manga_id: isi dengan id nyata dari /api/manga/list
curl -s "$BASE/api/manga/{manga_id}"
curl -s "$BASE/api/manga/{manga_id}/chapters"
# chapter_id: isi dengan latest_chapter.id dari detail manga
curl -s "$BASE/api/chapter/{chapter_id}"
curl -s "$BASE/api/genres"
curl -s "$BASE/api/types"
curl -s "$BASE/api/formats"
curl -s "$BASE/api/authors?q=a"
curl -s "$BASE/api/artists?q=a"
curl -s "$BASE/api/announcements?page=1&page_size=10"
curl -s "$BASE/api/slider"
curl -s "$BASE/api/search?q=solo"
curl -s "$BASE/api/explore"
curl -s "$BASE/api/random"
set +x

# Contoh error mapping:
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/manga/top?filter=hourly"      # 400
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/manga/does-not-exist"          # 404
