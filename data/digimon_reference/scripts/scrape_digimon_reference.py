#!/usr/bin/env python3
"""Reproducible scraper for the official Japanese Digimon Reference Book."""

from __future__ import annotations

import argparse
import csv
import http.cookiejar
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

from lxml import etree, html as lxml_html


BASE = "https://digimon.net/reference/"
INDEX_URL = BASE
REQUEST_URL = urljoin(BASE, "request.php")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
XHR_HEADERS = {
    "User-Agent": UA,
    "Referer": INDEX_URL,
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
PAGE_HEADERS = {"User-Agent": UA, "Referer": INDEX_URL}


class Response:
    def __init__(self, url, status_code, content, headers):
        self.url, self.status_code, self.content, self.headers = url, status_code, content, headers
        self.encoding = "utf-8"

    @property
    def text(self):
        return self.content.decode(self.encoding, errors="replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.url}")

    def json(self):
        return json.loads(self.content.decode("utf-8"))


class Session:
    def __init__(self):
        jar = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(jar))

    def get(self, url, *, params=None, headers=None, timeout=45):
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params)
        req = Request(url, headers=headers or {}, method="GET")
        with self.opener.open(req, timeout=timeout) as r:
            return Response(r.geturl(), r.status, r.read(), dict(r.headers))


def get_with_retry(session: Session, url: str, *, params=None, headers=None, tries=6):
    last = None
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, headers=headers, timeout=45)
            r.raise_for_status()
            if r.content:
                return r
            last = RuntimeError(f"empty response: {r.url}")
        except Exception as exc:  # retained in failure report by caller
            last = exc
        time.sleep(min(10, 0.8 * (2**attempt)))
    raise RuntimeError(str(last))


def doc(html: str):
    return lxml_html.fromstring(html)


def one(root, xpath):
    hits = root.xpath(xpath)
    return hits[0] if hits else None


def count_from_index(html: str) -> int | None:
    root = doc(html)
    digits = "".join(root.xpath('//li[contains(concat(" ",normalize-space(@class)," ")," p-refCountNumList ")]//img/@alt'))
    return int(digits) if digits else None


def select_values(index_html: str, field: str) -> list[str]:
    root = doc(index_html)
    return root.xpath(f'//select[@name="{field}"]/option[string-length(@value)>0]/@value')


def fetch_listing(session: Session) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    calls: list[dict] = []
    offset = 0
    seen_offsets = set()
    while offset != -1:
        if offset in seen_offsets:
            raise RuntimeError(f"listing offset loop at {offset}")
        seen_offsets.add(offset)
        params = {
            "digimon_name": "",
            "name": "",
            "digimon_level": "",
            "attribute": "",
            "type": "",
            "next": offset,
        }
        r = get_with_retry(session, REQUEST_URL, params=params, headers=XHR_HEADERS)
        data = r.json()
        batch = data.get("rows") or []
        next_offset = data.get("next", -1)
        calls.append({"offset": offset, "row_count": len(batch), "next": next_offset, "url": r.url})
        rows.extend(batch)
        offset = next_offset
    return rows, calls


def text_or_none(node) -> str | None:
    if node is None:
        return None
    # Preserve visible punctuation and line order; trim only surrounding whitespace.
    clone = lxml_html.fromstring(etree.tostring(node, encoding="unicode"))
    for br in clone.xpath('.//br'):
        br.tail = "\n" + (br.tail or "")
    value = "".join(clone.itertext()).strip()
    return value if value != "" else None


def parse_detail(directory_name: str, html: str, url: str, status_code: int) -> dict:
    root = doc(html)
    title_main = one(root, '//*[contains(concat(" ",normalize-space(@class)," ")," c-titleSet__main ")]')
    title_sub = one(root, '//*[contains(concat(" ",normalize-space(@class)," ")," c-titleSet__sub ")]')
    info: dict[str, str | None] = {}
    for dl in root.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," p-ref__info ")]//dl'):
        dt, dd = one(dl, './dt'), one(dl, './dd')
        if dt is not None:
            info["".join(dt.itertext()).strip()] = text_or_none(dd)

    pic_urls = []
    for src_raw in root.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," p-ref__piclist ")]//*[contains(concat(" ",normalize-space(@class)," ")," p-ref__picitem ")]//img[@src]/@src'):
        src = urljoin(url, src_raw)
        if src not in pic_urls:
            pic_urls.append(src)

    related = []
    for a in root.xpath('//a[contains(concat(" ",normalize-space(@class)," ")," p-refRelationList__content ") and contains(@href,"directory_name=")]'):
        href = urljoin(url, a.get("href"))
        m = re.search(r"[?&]directory_name=([^&#]+)", href)
        related.append({
            "directory_name": m.group(1) if m else None,
            "name_ja": text_or_none(one(a, './/*[contains(concat(" ",normalize-space(@class)," ")," p-refRelationList__name ")]')),
            "type_attribute_display": text_or_none(one(a, './/*[contains(concat(" ",normalize-space(@class)," ")," p-refRelationList__type ")]')),
            "url": href,
        })

    level_raw = info.get("レベル")
    type_raw = info.get("タイプ")
    attribute_raw = info.get("属性")
    moves_raw = info.get("必殺技")
    # The site uses Japanese middle dots as bullets; preserve raw and split into ordered entries.
    moves = []
    if moves_raw:
        moves = [x.strip() for x in re.split(r"(?:^|\n)・", moves_raw) if x.strip()]

    return {
        "directory_name": directory_name,
        "detail_url": url,
        "http_status": status_code,
        "name_ja": text_or_none(title_main),
        "name_roman": text_or_none(title_sub),
        "level_raw": level_raw,
        "level_normalized": level_raw,
        "type_raw": type_raw,
        "type_normalized": type_raw,
        "attribute_raw": attribute_raw,
        "attribute_normalized": attribute_raw,
        "special_moves_raw": moves_raw,
        "special_moves": moves,
        "profile_ja": text_or_none(one(root, '//*[contains(concat(" ",normalize-space(@class)," ")," p-ref__profile ")]//*[contains(concat(" ",normalize-space(@class)," ")," -txtProfile ")]')),
        "main_image_url": pic_urls[0] if pic_urls else None,
        "has_additional_illustrations": len(pic_urls) > 1,
        "additional_illustration_urls": pic_urls[1:],
        "all_official_image_urls": pic_urls,
        "related_digimon": related,
        "page_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }


def fetch_one(directory_name: str, cache_dir: Path) -> tuple[str, dict | None, dict | None]:
    url = f"{BASE}detail.php?directory_name={directory_name}"
    cache = cache_dir / f"{directory_name}.html"
    try:
        if cache.exists() and cache.stat().st_size > 1000:
            html = cache.read_text(encoding="utf-8")
            status = 200
        else:
            s = Session()
            r = get_with_retry(s, url, headers=PAGE_HEADERS)
            r.encoding = "utf-8"
            html, status = r.text, r.status_code
            cache.write_text(html, encoding="utf-8")
        parsed = parse_detail(directory_name, html, url, status)
        if not parsed["name_ja"]:
            raise RuntimeError("detail payload missing name")
        return directory_name, parsed, None
    except Exception as exc:
        return directory_name, None, {"directory_name": directory_name, "url": url, "error": str(exc)}


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="digimon_reference")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    root = Path(args.output).resolve()
    for p in ["master", "details", "taxonomy", "moves", "images", "reports", "raw/details"]:
        (root / p).mkdir(parents=True, exist_ok=True)

    session = Session()
    index = get_with_retry(session, INDEX_URL, headers=PAGE_HEADERS)
    index.encoding = "utf-8"
    index_html = index.text
    (root / "raw/index.html").write_text(index_html, encoding="utf-8")
    displayed_count = count_from_index(index_html)
    listing, listing_calls = fetch_listing(session)

    list_duplicates = [k for k, v in Counter(r["directory_name"] for r in listing).items() if v > 1]
    unique_listing = list(dict.fromkeys(r["directory_name"] for r in listing))
    listing_by_id = {r["directory_name"]: r for r in listing}

    details: dict[str, dict] = {}
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_one, d, root / "raw/details"): d for d in unique_listing}
        for i, fut in enumerate(as_completed(futures), 1):
            directory_name, parsed, failure = fut.result()
            if parsed:
                details[directory_name] = parsed
            if failure:
                failures.append(failure)
            if i % 100 == 0:
                print(f"details {i}/{len(unique_listing)} failures={len(failures)}", flush=True)

    ordered_details = [details[d] for d in unique_listing if d in details]
    collected_at = datetime.now(timezone.utc).isoformat()
    for d in ordered_details:
        d["listing_metadata"] = listing_by_id.get(d["directory_name"])
        d["collected_at_utc"] = collected_at

    # Detail JSON: one file per entity plus a combined array.
    for d in ordered_details:
        (root / "details" / f'{d["directory_name"]}.json').write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (root / "master/digimon_master.json").write_text(
        json.dumps(ordered_details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    master_rows = []
    for d in ordered_details:
        master_rows.append({
            "directory_name": d["directory_name"], "detail_url": d["detail_url"],
            "name_ja": d["name_ja"], "name_roman": d["name_roman"],
            "level_raw": d["level_raw"], "level_normalized": d["level_normalized"],
            "type_raw": d["type_raw"], "type_normalized": d["type_normalized"],
            "attribute_raw": d["attribute_raw"], "attribute_normalized": d["attribute_normalized"],
            "special_moves_raw": d["special_moves_raw"], "profile_ja": d["profile_ja"],
            "main_image_url": d["main_image_url"],
            "has_additional_illustrations": d["has_additional_illustrations"],
            "additional_illustration_count": len(d["additional_illustration_urls"]),
        })
    write_csv(root / "master/digimon_master.csv", master_rows, list(master_rows[0]) if master_rows else [])

    def taxonomy(field):
        counts = Counter(d[field] for d in ordered_details)
        return [{"raw_value": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: (x[0] is None, str(x[0])))]

    levels, types, attributes = taxonomy("level_raw"), taxonomy("type_raw"), taxonomy("attribute_raw")
    for name, values, filter_field in [
        ("levels", levels, "digimon_level"), ("types", types, "type"), ("attributes", attributes, "attribute")
    ]:
        payload = {"detail_page_values": values, "index_filter_values": select_values(index_html, filter_field)}
        (root / f"taxonomy/{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    move_rows = []
    image_rows = []
    for d in ordered_details:
        for pos, move in enumerate(d["special_moves"], 1):
            move_rows.append({"directory_name": d["directory_name"], "name_ja": d["name_ja"], "move_order": pos, "move_raw": move})
        for pos, url in enumerate(d["all_official_image_urls"], 1):
            image_rows.append({"directory_name": d["directory_name"], "name_ja": d["name_ja"], "image_order": pos, "is_main": pos == 1, "image_url": url})
    write_csv(root / "moves/special_moves.csv", move_rows, ["directory_name", "name_ja", "move_order", "move_raw"])
    write_csv(root / "images/image_manifest.csv", image_rows, ["directory_name", "name_ja", "image_order", "is_main", "image_url"])

    missing = []
    for d in ordered_details:
        null_fields = [f for f in ["name_roman", "level_raw", "type_raw", "attribute_raw", "special_moves_raw", "profile_ja", "main_image_url"] if d[f] is None]
        if null_fields:
            missing.append({"directory_name": d["directory_name"], "name_ja": d["name_ja"], "null_fields": null_fields})

    names = defaultdict(list)
    for d in ordered_details:
        names[d["name_ja"]].append(d["directory_name"])
    duplicate_names = {k: v for k, v in names.items() if k is not None and len(v) > 1}
    punctuation_families = defaultdict(list)
    for d in ordered_details:
        key = re.sub(r"[：:・\s\-－]+.*$", "", d["name_ja"] or "")
        punctuation_families[key].append({"name_ja": d["name_ja"], "directory_name": d["directory_name"]})
    similar_groups = {k: v for k, v in punctuation_families.items() if k and len(v) > 1}

    validation = {
        "collected_at_utc": collected_at,
        "official_displayed_count": displayed_count,
        "listing_rows_received": len(listing),
        "unique_directory_names": len(unique_listing),
        "successfully_parsed_detail_pages": len(ordered_details),
        "missing_count_vs_official_display": None if displayed_count is None else displayed_count - len(ordered_details),
        "failed_pages": failures,
        "duplicate_directory_names_in_listing": list_duplicates,
        "listing_requests": listing_calls,
        "index_sha256": hashlib.sha256(index_html.encode("utf-8")).hexdigest(),
    }
    (root / "reports/validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "reports/exceptions.json").write_text(json.dumps({"missing_values": missing, "duplicate_exact_names": duplicate_names, "similar_name_groups": similar_groups}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    site_md = f"""# デジモン図鑑 사이트 구조 조사

- 기준 URL: {INDEX_URL}
- 수집 시각(UTC): {collected_at}
- 공식 표시 등록 수: {displayed_count}
- 목록 방식: 초기 HTML 이후 `./request.php`에 XHR GET 요청. `next` 오프셋으로 추가 로딩.
- 한 요청의 기본 반환량: 첫 응답 {listing_calls[0]['row_count'] if listing_calls else '미확인'}개
- 상세 URL: `detail.php?directory_name={{directory_name}}`
- 메인 이미지: `/cimages/digimon/{{directory_name}}.jpg`가 기본 규칙이나 실제 상세 DOM의 URL을 기록함.
- 추가 일러스트: 상세 페이지 `.p-ref__piclist .p-ref__picitem img`의 두 번째 이후 이미지.
- 언어 경로: 일본어 `/reference/`, 영어 `/reference_en/`, 간체 `/reference_zh-CHS/`, 번체 `/reference_zh-CHT/`, 한국어 `/reference_ko/`; 상세 페이지는 같은 `directory_name` 쿼리를 사용.
- 검색: `digimon_name`, 오십음 `name`, `digimon_level`, `attribute`, `type`; 목록 응답은 JSON.
- 마스터 기준: 일본어 페이지 원문. 정규화 필드는 현재 원문과 동일하게 두어 변환/추측을 하지 않음.
- 재현: 저장된 `scrape_digimon_reference.py` 실행 결과이며 `raw/index.html`, `raw/details/*.html`, SHA-256을 검증 근거로 포함.
"""
    (root / "reports/site_structure.md").write_text(site_md, encoding="utf-8")

    exc_md = ["# 누락값과 예외", "", f"- 누락값 보유 개체: {len(missing)}", f"- 정확히 같은 일본어 이름 그룹: {len(duplicate_names)}", f"- 추가 일러스트 보유 개체: {sum(d['has_additional_illustrations'] for d in ordered_details)}", "", "세부 목록은 `exceptions.json`에 원문 식별자와 함께 보존했다."]
    (root / "reports/exceptions.md").write_text("\n".join(exc_md) + "\n", encoding="utf-8")

    val_md = f"""# 수집 검증

| 항목 | 수 |
|---|---:|
| 사이트 표시 등록 수 | {displayed_count} |
| 목록 응답 행 | {len(listing)} |
| 고유 directory_name | {len(unique_listing)} |
| 상세 페이지 성공 | {len(ordered_details)} |
| 실패 페이지 | {len(failures)} |
| 공식 표시 대비 누락 | {None if displayed_count is None else displayed_count - len(ordered_details)} |

실패 페이지와 각 목록 요청 오프셋은 `validation.json`에 기록했다. 모든 내용 필드는 일본어 공식 상세 페이지에서 직접 파싱했으며, 누락값은 추정 보완하지 않았다.
"""
    (root / "reports/validation.md").write_text(val_md, encoding="utf-8")

    manifest = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "file_manifest.json":
            manifest.append({"path": str(p.relative_to(root)), "size_bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    (root / "file_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
