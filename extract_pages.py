# extract_pages.py -- Витягує перші N сторінок з PDF для передачі в ШІ
#
# Використання:
#   python extract_pages.py                  -- обробити всі PDF в поточній теці/підпапках
#   python extract_pages.py C:/Work/Upload   -- вказати папку
#   python extract_pages.py --pages 10        -- витягти 10 сторінок (за замовч. 8)

import os
import sys
import glob
import fitz  # pymupdf


def extract_pages(pdf_path, out_path, n_pages=8):
    try:
        doc = fitz.open(pdf_path)
        total = len(doc)
        pages = min(n_pages, total)

        out = fitz.open()
        out.insert_pdf(doc, from_page=0, to_page=pages - 1)
        out.save(out_path)
        out.close()
        doc.close()
        return pages
    except Exception as e:
        print(f"  ❌ Помилка: {e}")
        return None


def find_pdfs(root_dir):
    """Знаходить всі PDF крім вже витягнутих *_for_info.pdf"""
    results = []

    # Плоска структура
    flat = glob.glob(os.path.join(root_dir, "*.pdf"))
    flat = [p for p in flat if not p.endswith("_for_info.pdf")]
    if flat:
        return flat

    # Підпапки
    for entry in sorted(os.scandir(root_dir), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        pdfs = glob.glob(os.path.join(entry.path, "*.pdf"))
        pdfs = [p for p in pdfs if not p.endswith("_for_info.pdf")]
        results.extend(pdfs)

    return results


def main():
    args = sys.argv[1:]

    n_pages = 5
    if '--pages' in args:
        idx = args.index('--pages')
        n_pages = int(args[idx + 1])
        args = [a for a in args if a != '--pages' and a != str(n_pages)]

    root_dir = args[0] if args else os.getcwd()

    if not os.path.isdir(root_dir):
        print(f"❌ Папка не існує: {root_dir}")
        sys.exit(1)

    print(f"📂 Сканую: {root_dir}")
    print(f"📄 Кількість сторінок: {n_pages}\n")

    pdfs = find_pdfs(root_dir)

    if not pdfs:
        print("❌ PDF файлів не знайдено")
        sys.exit(1)

    print(f"Знайдено {len(pdfs)} PDF:\n")

    ok, fail = 0, 0
    for pdf_path in pdfs:
        base = os.path.splitext(pdf_path)[0]
        out_path = f"{base}_for_info.pdf"
        name = os.path.basename(pdf_path)

        pages = extract_pages(pdf_path, out_path, n_pages)
        if pages:
            print(f"  ✅ {name} → {os.path.basename(out_path)} ({pages} стор.)")
            ok += 1
        else:
            print(f"  ❌ {name} — не вдалось")
            fail += 1

    print(f"\n✅ Готово: {ok}   ❌ Помилки: {fail}")


if __name__ == '__main__':
    main()
