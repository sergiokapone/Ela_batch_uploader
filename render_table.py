#!/usr/bin/env python3
"""
render_table.py — Читає kpi_works*.json, групує по роках і колекціях,
рендерить HTML через Jinja2 шаблон.

Використання:
  python render_table.py                          — з kpi_works.json, всі роки
  python render_table.py kpi_works_2024.json      — конкретний файл
  python render_table.py --year 2024              — фільтр по році
  python render_table.py --magistr                — тільки магістерські
  python render_table.py --bakalavr               — тільки бакалаврські
  python render_table.py --single                 — один спільний HTML файл
  python render_table.py --wp                     — WP-сторінка: шапка + h2 по роках + таблиці
                                                    (за замовчуванням: окремий файл на кожен рік)
"""

import json
import sys
import os
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader

# ── Налаштування ────────────────────────────────────────────────
TEMPLATE_FILE      = "templates/template.html.j2"       # шаблон однієї таблиці
TEMPLATE_PAGE_FILE = "templates/template_page.html.j2"  # шаблон повної WP-сторінки
OUTPUT_DIR         = "output_html"             # куди складати HTML файли

COLLECTION_LABELS = {
    "magistr":  "Магістерські дисертації (ПФ)",
    "bakalavr": "Бакалаврські роботи (ПФ)",
}

COLLECTION_UUIDS = {
    "magistr":  "e475e84c-48ff-4236-9633-694b923e4a82",
    "bakalavr": "13647e65-d1d5-49d3-abfb-49957e3b0d00",
}

# Порядок колекцій на сторінці: спочатку магістри, потім бакалаври
COL_ORDER = ["magistr", "bakalavr"]
# ────────────────────────────────────────────────────────────────


def load_works(json_path: str) -> list:
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def group_works(works: list, collection_filter=None, year_filter=None) -> dict:
    """
    Повертає структуру:
      { collection: { year: [work, ...] } }
    """
    grouped = defaultdict(lambda: defaultdict(list))
    for w in works:
        col = w.get("collection", "magistr")
        year = w.get("year") or "невідомо"

        if collection_filter and col != collection_filter:
            continue
        if year_filter and year != year_filter:
            continue

        grouped[col][year].append(w)

    # Сортуємо роботи в кожній групі по прізвищу першого автора.
    # DSpace зазвичай зберігає авторів у форматі "Прізвище, Ім'я По-батькові"
    def surname_key(w):
        first_author = (w.get("authors") or [""])[0]
        surname = first_author.split(",")[0].split()[0] if first_author.strip() else ""
        # Нормалізуємо латинські літери що схожі на кириличні (часта проблема DSpace)
        surname = surname.replace("I", "І").replace("i", "і")
        return surname.lower()

    for col in grouped:
        for year in grouped[col]:
            grouped[col][year].sort(key=surname_key)

    return grouped


def render_wp(grouped: dict, env: Environment, output_dir: str):
    """Рендерить фрагмент для вставки в WP (без html/head/body)."""
    os.makedirs(output_dir, exist_ok=True)
    template = env.get_template(TEMPLATE_PAGE_FILE)

    # Збираємо всі роки з усіх колекцій, сортуємо від нового до старого
    all_years = sorted(
        {year for col in grouped.values() for year in col.keys()},
        reverse=True
    )

    html = template.render(
        grouped=grouped,
        years=all_years,
        col_order=COL_ORDER,
        collection_labels=COLLECTION_LABELS,
        collection_uuids=COLLECTION_UUIDS,
    )

    # Для WP потрібен лише вміст <body>, без DOCTYPE/html/head/body
    content = _extract_body(html)

    out_path = os.path.join(output_dir, "wp_page.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  💾 {out_path}")
    return [out_path]


def render(grouped: dict, env: Environment, output_dir: str, single_file: bool):
    os.makedirs(output_dir, exist_ok=True)
    template = env.get_template(TEMPLATE_FILE)
    generated = []

    if single_file:
        # Один великий HTML з усіма секціями
        all_blocks = []
        for col in sorted(grouped.keys()):
            label = COLLECTION_LABELS.get(col, col)
            for year in sorted(grouped[col].keys(), reverse=True):
                works = grouped[col][year]
                block = template.render(
                    collection_label=label,
                    year=year,
                    works=works,
                )
                body = _extract_body(block)
                all_blocks.append(body)

        out_path = os.path.join(output_dir, "all_works.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(_wrap_page("\n\n".join(all_blocks), "Всі роботи ПФ"))
        generated.append(out_path)
        print(f"  💾 {out_path}")

    else:
        # Окремий файл на кожну колекцію+рік
        for col in sorted(grouped.keys()):
            label = COLLECTION_LABELS.get(col, col)
            for year in sorted(grouped[col].keys(), reverse=True):
                works = grouped[col][year]
                html = template.render(
                    collection_label=label,
                    year=year,
                    works=works,
                )
                fname = f"{col}_{year}.html"
                out_path = os.path.join(output_dir, fname)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(html)
                generated.append(out_path)
                print(f"  💾 {out_path}  ({len(works)} робіт)")

    return generated


def _extract_body(html: str) -> str:
    """Витягує вміст між <body> та </body>."""
    start = html.find("<body>")
    end = html.find("</body>")
    if start != -1 and end != -1:
        return html[start + 6:end].strip()
    return html


def _wrap_page(content: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
</head>
<body>
{content}
</body>
</html>"""


def main():
    args = sys.argv[1:]

    # JSON файл
    json_path = "kpi_works.json"
    for a in args:
        if a.endswith(".json") and os.path.exists(a):
            json_path = a
            break

    if not os.path.exists(json_path):
        print(f"❌ Файл не знайдено: {json_path}")
        print("   Спочатку запусти: python get_works.py")
        sys.exit(1)

    # Фільтри
    year_filter       = args[args.index("--year") + 1] if "--year" in args else None
    collection_filter = "magistr"  if "--magistr"  in args else \
                        "bakalavr" if "--bakalavr" in args else None
    single_file       = "--single" in args
    wp_mode           = "--wp"     in args

    print(f"📂 Читаємо: {json_path}")
    works = load_works(json_path)
    print(f"   Всього записів: {len(works)}")

    grouped = group_works(works, collection_filter, year_filter)

    total = sum(len(w) for col in grouped.values() for w in col.values())
    print(f"   Після фільтрації: {total} робіт")

    # Jinja2 — шукаємо шаблон поряд зі скриптом
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True
    )

    print(f"\n🖨️  Рендеримо HTML → папка '{OUTPUT_DIR}/'")

    if wp_mode:
        generated = render_wp(grouped, env, OUTPUT_DIR)
    else:
        generated = render(grouped, env, OUTPUT_DIR, single_file)

    print(f"\n✅ Готово! Створено файлів: {len(generated)}")


if __name__ == "__main__":
    main()
