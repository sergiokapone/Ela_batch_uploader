#!/usr/bin/env python3
"""
extract_meta.py — покращена версія для залізобетонного витягування Title та Citation
"""

import re
import sys
import os
import yaml
import fitz  # pymupdf


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def clean_advisor(text):
    """Прибирає звання та підказки в дужках із поля керівника."""
    # Прибираємо підказки в дужках, які часто залишаються на титулках
    text = re.sub(r'\(.*?\)', '', text)
    # Прибираємо слова доцент, професор, ступені
    garbage = [r'\bдоцент\b', r'\bпроф\s*\.', r'\bпрофесор\b', r'\bд\s*\.\s*[тфмн]\s*\.\s*н\s*\.', r'\bк\s*\.\s*[тфмн]\s*\.\s*н\s*\.']
    for g in garbage:
        text = re.sub(g, '', text, flags=re.IGNORECASE)
    return clean(text)


def extract_page1(text):
    data = {}

    m = re.search(r'УДК\s+([\d.:]+)', text)
    if m:
        data['udc'] = m.group(1).strip()

    # ПОКРАЩЕНО: Шукає "на тему", "НА ТЕМУ", підтримує абсолютно всі види лапок «»""“”''
    m = re.search(r'на\s+тему[:\s]*[«"“\'\s](.*?)[»"”\'\n]', text, re.DOTALL | re.IGNORECASE)
    if m:
        data['title'] = clean(m.group(1))
    else:
        # Резервний пошук, якщо лапки взагалі забули поставити
        m = re.search(r'на\s+тему[:\s]+(.*?)(?=\nвыполнил|\nвиконав|\nгрупи|$)', text, re.DOTALL | re.IGNORECASE)
        if m:
            data['title'] = clean(m.group(1))

    m = re.search(r'групи\s+\S+\s*\n(.*?)\n', text)
    if m:
        data['author'] = clean(m.group(1))

    advisor_pattern = r'Науковий\s+кер[іi]вник[:\s]*(.*?)(?:\n\n|\n[А-ЯA-Z][а-яa-z]+|$)'
    m = re.search(advisor_pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        data['advisor'] = clean_advisor(m.group(1))

    m = re.search(r'Київ\s*[–-]\s*(\d{4})', text)
    if m:
        data['year'] = int(m.group(1))
        data['date_issued'] = str(m.group(1))

    m = re.search(r'зi\s+спец[іi]альност[іi]\s+([\d]+)\s+[«"“](.*?)[»"”]', text, re.IGNORECASE)
    if m:
        data['specialty_code'] = m.group(1).strip()
        data['specialty_name'] = clean(m.group(2))

    return data


def extract_abstract(pages_text):
    data = {}
    m = re.search(r'РЕФЕРАТ\s*(.*?)(?:Ключов[іi]\s*слова|$)', pages_text, re.DOTALL | re.IGNORECASE)
    if m:
        data['abstract'] = clean(m.group(1))

    kw_pattern = r'Ключов[іi]\s*слова[:\-\–\.\s]*(.*?)(?:\n\n|\n[А-ЯA-Z\s]{5,}|$)'
    m = re.search(kw_pattern, pages_text, re.DOTALL | re.IGNORECASE)
    if m:
        kw_raw = clean(m.group(1))
        data['keywords'] = [kw.strip().rstrip('.') for kw in re.split(r'[,;]', kw_raw) if kw.strip()]

    return data


def extract_extent(pages_text):
    m = re.search(r'становить\s+(\d+)\s+сторiнок', pages_text)
    return int(m.group(1)) if m else None


def extract_metadata(pdf_path):
    doc = fitz.open(pdf_path)
    pages = [doc[i].get_text() for i in range(min(6, len(doc)))]
    doc.close()

    page1 = pages[0] if len(pages) > 0 else ''
    abstract_pages = '\n'.join(pages[3:6])

    meta = {'file_name': os.path.basename(pdf_path)}
    meta.update(extract_page1(page1))
    meta.update(extract_abstract(abstract_pages))

    extent = extract_extent(abstract_pages)
    if extent:
        meta['pages'] = extent

    meta['author_orcid'] = ""
    meta['advisor_orcid'] = ""
    meta['publisher'] = 'КПІ ім. Ігоря Сікорського'
    meta['publisher_place'] = 'Київ'
    meta['language'] = 'uk'
    meta['type'] = 'Master Thesis'

    # ТЕПЕР ЗГЕНЕРУЄТЬСЯ НАДІЙНІШЕ:
    # Якщо title не знайшовся автоматично, підставимо заглушку для ДСТУ опису, щоб опис з'явився у файлі
    author = meta.get('author', 'Автор')
    title = meta.get('title', '[ВСТАВТЕ НАЗВУ РОБОТИ РУКАМИ]')
    year = meta.get('year', 2026)

    parts = author.split()
    short = parts[0] + ', ' + ' '.join(p[0] + '.' for p in parts[1:]) if len(parts) >= 2 else author

    sp = meta.get('specialty_code', '105')
    sp_name = meta.get('specialty_name', 'Прикладна фізика та наноматеріали')
    pages_str = f" {meta['pages']} с." if meta.get('pages') else ''

    meta['citation'] = (
        f"{short} {title} : магістерська дис. : "
        f"спец. {sp} «{sp_name}» / {author} ; наук. кер. {meta.get('advisor', '')}. – "
        f"{meta['publisher_place']} : {meta['publisher']}, {year}. –{pages_str}"
    )

    return meta


def main():
    if len(sys.argv) < 2:
        print("Використання: python3 extract_meta.py thesis.pdf [output.yaml]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else pdf_path.replace('.pdf', '_meta.yaml')

    meta = extract_metadata(pdf_path)

    with open(out_path, 'w', encoding='utf-8') as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"✓ Збережено: {out_path}")


if __name__ == '__main__':
    main()

