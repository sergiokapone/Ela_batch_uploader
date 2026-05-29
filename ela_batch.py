#!/usr/bin/env python3
# ela_batch.py -- Пакетне завантаження магістерських та бакалаврських робіт в ela.KPI.
#
# Структура папок:
#   Upload_magistr/
#     Lytvyn_magistr/
#       Lytvyn_magistr.pdf
#       Lytvyn_magistr.yaml        (або Lytvyn_magistr_meta.yaml)
#     Dibilko_bakalavr/
#       Dibilko_bakalavr.pdf
#       Dibilko_bakalavr.yaml
#
# Використання:
#   python ela_batch.py                  -- обробити всі папки в поточній теці
#   python ela_batch.py C:/Work/Upload   -- вказати конкретну теку
#   python ela_batch.py --dry-run        -- показати що буде зроблено без завантаження

import os
import sys
import subprocess
import glob
from datetime import datetime


def find_pair_in_folder(folder, name):
    """Шукає пару PDF+YAML в одній папці"""
    yaml_candidates = (
        glob.glob(os.path.join(folder, f"{name}_meta.yaml")) +
        glob.glob(os.path.join(folder, f"{name}.yaml")) +
        glob.glob(os.path.join(folder, "*.yaml"))
    )
    pdf_candidates = (
        glob.glob(os.path.join(folder, f"{name}.pdf")) +
        glob.glob(os.path.join(folder, "*.pdf"))
    )
    return yaml_candidates, pdf_candidates


def find_pairs(root_dir):
    """Знаходить всі пари PDF+YAML — як у підпапках, так і в поточній теці"""
    pairs = []

    # --- Варіант 1: файли лежать прямо в root_dir ---
    root_yamls = glob.glob(os.path.join(root_dir, "*.yaml"))
    root_pdfs  = glob.glob(os.path.join(root_dir, "*.pdf"))
    if root_yamls and root_pdfs:
        # Зіставляємо по імені без розширення
        pdf_map = {os.path.splitext(os.path.basename(p))[0]: p for p in root_pdfs}
        for yaml_path in sorted(root_yamls):
            name = os.path.splitext(os.path.basename(yaml_path))[0]
            name = name.replace('_meta', '')
            pdf_path = pdf_map.get(name)
            if not pdf_path:
                print(f"  ⚠️  [{name}] — PDF не знайдено поруч, пропускаємо")
                continue
            is_bakalavr = 'bakalavr' in name.lower() or 'бакалавр' in name.lower()
            pairs.append({'name': name, 'yaml': yaml_path, 'pdf': pdf_path, 'is_bakalavr': is_bakalavr})
        return pairs

    # --- Варіант 2: кожна робота в окремій підпапці ---
    for entry in sorted(os.scandir(root_dir), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        folder = entry.path
        name = entry.name

        yaml_candidates, pdf_candidates = find_pair_in_folder(folder, name)

        if not yaml_candidates:
            print(f"  ⚠️  [{name}] — YAML не знайдено, пропускаємо")
            continue
        if not pdf_candidates:
            print(f"  ⚠️  [{name}] — PDF не знайдено, пропускаємо")
            continue

        is_bakalavr = 'bakalavr' in name.lower() or 'бакалавр' in name.lower()
        pairs.append({
            'name':        name,
            'yaml':        yaml_candidates[0],
            'pdf':         pdf_candidates[0],
            'is_bakalavr': is_bakalavr,
        })

    return pairs


def run_upload(pair, dry_run=False, log_file=None, submit=False):
    """Запускає ela_upload.py для одної пари"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ela_upload.py')

    cmd = [sys.executable, script, pair['yaml']]
    if pair['is_bakalavr']:
        cmd.append('--bakalavr')
    if submit:
        cmd.append('--submit')

    label = f"{'[BAKALAVR]' if pair['is_bakalavr'] else '[MAGISTR] '} {pair['name']}"

    if dry_run:
        print(f"  🔍 {label}")
        print(f"     YAML: {pair['yaml']}")
        print(f"     PDF:  {pair['pdf']}")
        print(f"     CMD:  {' '.join(cmd)}")
        return True

    print(f"\n{'='*60}")
    print(f"🚀 {label}")
    print(f"{'='*60}")

    result = subprocess.run(cmd, capture_output=False, text=True)
    success = result.returncode == 0

    status = "✅ OK" if success else "❌ FAIL"
    log_line = f"{datetime.now().strftime('%H:%M:%S')} {status} {label}\n"

    if log_file:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_line)

    return success


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    submit  = '--submit'   in args
    args = [a for a in args if a not in ('--dry-run', '--submit')]

    root_dir = args[0] if args else os.getcwd()

    if not os.path.isdir(root_dir):
        print(f"❌ Папка не існує: {root_dir}")
        sys.exit(1)

    print(f"📂 Сканую: {root_dir}")
    if dry_run:
        print("🔍 РЕЖИМ ПЕРЕГЛЯДУ (dry-run) — реального завантаження не буде\n")
    if submit:
        print("🚀 РЕЖИМ --submit — роботи одразу підуть на модерацію без зупинки\n")

    pairs = find_pairs(root_dir)

    if not pairs:
        print("❌ Не знайдено жодної пари PDF+YAML")
        sys.exit(1)

    print(f"\n📋 Знайдено {len(pairs)} роботи(и):")
    for p in pairs:
        kind = 'бакалавр' if p['is_bakalavr'] else 'магістр '
        print(f"  [{kind}] {p['name']}")

    if dry_run:
        print("\n--- Деталі ---")
        for p in pairs:
            run_upload(p, dry_run=True, submit=submit)
        sys.exit(0)

    # Підтвердження
    print(f"\nЗапустити завантаження для всіх {len(pairs)}? [y/N] ", end='')
    answer = input().strip().lower()
    if answer != 'y':
        print("Скасовано.")
        sys.exit(0)

    # Лог-файл
    log_path = os.path.join(root_dir, f"upload_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    print(f"\n📝 Лог: {log_path}\n")

    ok, fail = 0, 0
    failed_names = []

    for p in pairs:
        success = run_upload(p, dry_run=False, log_file=log_path, submit=submit)
        if success:
            ok += 1
        else:
            fail += 1
            failed_names.append(p['name'])

    print(f"\n{'='*60}")
    print(f"✅ Успішно: {ok}   ❌ Помилки: {fail}")
    if failed_names:
        print("Не вдалось завантажити:")
        for n in failed_names:
            print(f"  - {n}")
    print(f"Лог збережено: {log_path}")


if __name__ == '__main__':
    main()
