#!/usr/bin/env python3
"""
get_works.py — Вивантажує магістерські та бакалаврські роботи з ela.KPI
через публічний DSpace REST API (без авторизації).

Використання:
  python get_works.py                    — завантажити обидві колекції
  python get_works.py --magistr          — тільки магістерські
  python get_works.py --bakalavr         — тільки бакалаврські
  python get_works.py --year 2024        — фільтр по році
"""

import requests
import json
import sys
import time

BASE_URL = "https://ela.kpi.ua/server/api"

COLLECTIONS = {
    "magistr":  "e475e84c-48ff-4236-9633-694b923e4a82",
    "bakalavr": "13647e65-d1d5-49d3-abfb-49957e3b0d00",
}

PAGE_SIZE = 100


def get_meta_value(metadata: dict, key: str, default=None):
    entries = metadata.get(key, [])
    return entries[0].get("value", default) if entries else default


def get_meta_all(metadata: dict, key: str) -> list:
    return [e.get("value", "") for e in metadata.get(key, [])]


def parse_item(item_data: dict) -> dict:
    """Парсить метадані з об'єкта item."""
    meta = item_data.get("metadata", {})
    return {
        "uuid":       item_data.get("uuid", ""),
        "handle":     item_data.get("handle", ""),
        "url":        f"https://ela.kpi.ua/handle/{item_data.get('handle', '')}",
        "title":      get_meta_value(meta, "dc.title"),
        "title_alt":  get_meta_value(meta, "dc.title.alternative"),
        "authors":    get_meta_all(meta, "dc.contributor.author"),
        "advisors":   get_meta_all(meta, "dc.contributor.advisor"),
        "date":       get_meta_value(meta, "dc.date.issued"),
        "year":       (get_meta_value(meta, "dc.date.issued") or "")[:4] or None,
        "language":   get_meta_value(meta, "dc.language.iso"),
        "abstract":   get_meta_value(meta, "dc.description.abstract"),
        "keywords":   get_meta_all(meta, "dc.subject"),
        "type":       get_meta_value(meta, "dc.type"),
        "degree":     get_meta_value(meta, "dc.description.degree"),
        "speciality": get_meta_value(meta, "dc.subject.speciality"),
        "department": get_meta_value(meta, "dc.publisher"),
        "identifier": get_meta_value(meta, "dc.identifier.uri"),
    }


def fetch_collection(collection_name: str, collection_uuid: str,
                     year_filter: str | None = None) -> list:
    print(f"\n{'='*55}")
    print(f"  📚 Колекція: {collection_name.upper()}")
    print(f"  UUID: {collection_uuid}")
    print(f"{'='*55}")

    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (get_works.py; ela.kpi.ua exporter)"
    })

    result = []
    page = 0

    print("  ⬇️  Завантажуємо роботи...")
    while True:
        try:
            res = session.get(
                f"{BASE_URL}/discover/search/objects",
                params={
                    "scope":   collection_uuid,
                    "dsoType": "item",
                    "page":    page,
                    "size":    PAGE_SIZE,
                },
                timeout=30
            )
        except requests.RequestException as e:
            print(f"\n  ❌ Мережева помилка на сторінці {page}: {e}")
            break

        if res.status_code != 200:
            print(f"\n  ❌ Помилка запиту: {res.status_code}")
            break

        data = res.json()

        # Структура: _embedded.searchResult._embedded.objects[]
        search_result = data.get("_embedded", {}).get("searchResult", {})
        objects = search_result.get("_embedded", {}).get("objects", [])

        if not objects:
            break

        for obj in objects:
            # Реальний item лежить всередині _embedded.indexableObject
            item_data = obj.get("_embedded", {}).get("indexableObject", {})
            if not item_data or item_data.get("type") != "item":
                continue

            parsed = parse_item(item_data)

            if year_filter and parsed.get("year") != year_filter:
                continue

            parsed["collection"] = collection_name
            result.append(parsed)

        # Пагінація через page-об'єкт
        page_info = search_result.get("page", {})
        total_pages = page_info.get("totalPages", 1)
        total_elements = page_info.get("totalElements", "?")

        print(f"  → Сторінка {page+1}/{total_pages} | "
              f"Відібрано: {len(result)}/{total_elements}", end="\r")

        if page + 1 >= total_pages:
            break

        page += 1
        time.sleep(0.1)

    print(f"\n  ✓ Готово! Відібрано робіт: {len(result)}")
    return result


def main():
    args = sys.argv[1:]

    if "--magistr" in args:
        to_fetch = ["magistr"]
    elif "--bakalavr" in args:
        to_fetch = ["bakalavr"]
    else:
        to_fetch = ["magistr", "bakalavr"]

    year_filter = None
    if "--year" in args:
        idx = args.index("--year")
        if idx + 1 < len(args):
            year_filter = args[idx + 1]
            print(f"  🗓️  Фільтр по році: {year_filter}")

    all_works = []
    for name in to_fetch:
        works = fetch_collection(name, COLLECTIONS[name], year_filter=year_filter)
        all_works.extend(works)

    suffix = f"_{year_filter}" if year_filter else ""
    suffix += f"_{'_'.join(to_fetch)}" if len(to_fetch) == 1 else ""
    output_file = f"kpi_works{suffix}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_works, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"  🎉 Готово! Всього робіт: {len(all_works)}")
    print(f"  💾 Збережено у файл: {output_file}")
    print(f"{'='*55}")

    by_year = {}
    for w in all_works:
        y = w.get("year") or "невідомо"
        by_year[y] = by_year.get(y, 0) + 1
    print("\n  📊 Розподіл по роках:")
    for y in sorted(by_year.keys(), reverse=True)[:10]:
        print(f"     {y}: {by_year[y]} робіт")


if __name__ == "__main__":
    main()
