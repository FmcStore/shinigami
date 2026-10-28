#!/usr/bin/env bash
# Smoke test for Shinigami API (default http://127.0.0.1:8787). Verdict to stderr.
set -u
BASE="${1:-http://127.0.0.1:8787}"
PASS=0; FAIL=0

check() { # name url jq_expr expected
  local name="$1" url="$2" expr="$3" expected="$4" got
  got=$(curl -s -m 30 "$url" | python3 -c "import sys,json;d=json.load(sys.stdin);print(eval(sys.argv[1],{'d':d}))" "$expr" 2>/dev/null)
  if [ "$got" = "$expected" ]; then
    PASS=$((PASS+1)); echo "PASS: $name"
  else
    FAIL=$((FAIL+1)); echo "FAIL: $name (got: $got, want: $expected)" >&2
  fi
}

check "catalog"        "$BASE/"                        "bool(d['endpoints'])"              "True"
check "health"         "$BASE/api/health"              "d['ok']"                           "True"
check "home"           "$BASE/api/home"                "len(d['top']['daily'])>0"          "True"
check "manga/list"     "$BASE/api/manga/list?page=1&page_size=3" "isinstance(d['data'],list)" "True"
check "manga/list q"   "$BASE/api/manga/list?q=demon"  "isinstance(d['data'],list)"        "True"
check "manga/top"      "$BASE/api/manga/top?filter=weekly" "isinstance(d['data'],list)"    "True"
check "top bad filter" "$BASE/api/manga/top?filter=bogus" "d['status']"                    "400"
check "genres"         "$BASE/api/genres"              "len(d['data'])>0"                  "True"
check "types"          "$BASE/api/types"               "len(d['data'])>0"                  "True"
check "formats"        "$BASE/api/formats"             "len(d['data'])>0"                  "True"
check "authors"        "$BASE/api/authors?q=a"         "isinstance(d['data'],list)"        "True"
check "artists"        "$BASE/api/artists?q=a"         "isinstance(d['data'],list)"        "True"
check "announcements"  "$BASE/api/announcements"       "isinstance(d['data'],list)"        "True"
check "slider"         "$BASE/api/slider"              "isinstance(d['data'],list)"        "True"
check "search"         "$BASE/api/search?q=demon"      "len(d['data'])>0"                  "True"
check "search no q"    "$BASE/api/search"              "d['status']"                       "400"
check "explore"        "$BASE/api/explore"             "len(d['sections'])>0"              "True"
check "random"         "$BASE/api/random"              "isinstance(d['data'],dict)"        "True"

MID=$(curl -s -m 30 "$BASE/api/manga/list?page=1&page_size=1" | python3 -c "import sys,json;print(json.load(sys.stdin)['data'][0]['manga_id'])")
check "manga detail"   "$BASE/api/manga/$MID"          "d['data']['manga_id']=='$MID'"     "True"
check "manga chapters" "$BASE/api/manga/$MID/chapters" "isinstance(d['chapters'],list)"    "True"
check "manga 404"      "$BASE/api/manga/does-not-exist" "d['status']"                      "404"

CID=$(curl -s -m 30 "$BASE/api/manga/$MID" | python3 -c "import sys,json;print(json.load(sys.stdin)['chapters']['latest_chapter_id'])")
check "chapter detail" "$BASE/api/chapter/$CID"        "len(d['images'])>0 and bool(d['images'][0]['url'])" "True"
check "chapter 404"    "$BASE/api/chapter/nope"        "d['status']"                       "404"

echo "passed=$PASS failed=$FAIL" >&2
[ "$FAIL" -eq 0 ] && echo "SMOKE VERDICT: ALL PASS" >&2 || echo "SMOKE VERDICT: FAILURES" >&2
[ "$FAIL" -eq 0 ]
