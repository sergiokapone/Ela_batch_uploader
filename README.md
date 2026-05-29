# ela-kpi-uploader

Скрипти для автоматичного завантаження магістерських та бакалаврських дисертацій у репозиторій [ela.kpi.ua](https://ela.kpi.ua) (DSpace 7).

Розроблено для кафедри прикладної фізики ФТІ КПІ ім. Ігоря Сікорського.

---

## Файли

| Файл | Призначення |
|---|---|
| `ela_upload.py` | Основний скрипт — завантажує одну роботу |
| `ela_batch.py` | Пакетне завантаження — обходить папки і запускає `ela_upload.py` для кожної |
| `extract_meta.py` | Витягує метадані з PDF (титулка + реферат) і зберігає в YAML |
| `.env.example` | Шаблон файлу з налаштуваннями |

---

## Встановлення

```bash
pip install requests pyyaml pymupdf python-dotenv
```

Створи файл `.env` у папці зі скриптами (скопіюй з `.env.example`):

```env
ELA_EMAIL=your_account@gmail.com
ELA_PASSWORD=your_password
ELA_COLLECTION_MAGISTR=e475e84c-48ff-4236-9633-694b923e4a82
ELA_COLLECTION_BAKALAVR=13647e65-d1d5-49d3-abfb-49957e3b0d00
```

> **Увага:** `.env` містить пароль — не комітити в git. Файл вже є в `.gitignore`.

---

## Підготовка роботи

### Крок 1 — Автоматичне витягування метаданих

```bash
python extract_meta.py Lytvyn_magistr.pdf
```

Створить `Lytvyn_magistr_meta.yaml` поруч з PDF. Перевір і відкоригуй вручну:

- `title` — назва роботи (якщо в PDF нестандартні лапки — може не витягнутись)
- `advisor` — прізвище керівника (скрипт іноді підхоплює звання замість прізвища)
- `pages` — кількість сторінок (береться з реферату, рядок "становить XX сторінок")
- `date_issued` — рік захисту (рядок у лапках: `'2026'`)

### Крок 2 — Структура YAML

```yaml
file_name: Lytvyn_magistr.pdf
udc: 621.382
title: Назва роботи
author: Литвин Іван Петрович
advisor: Іванова Віта Вікторівна
year: 2026
date_issued: '2026'
pages: 95
specialty_code: '105'
specialty_name: Прикладна фізика та наноматеріали
abstract: 'Текст реферату...'
keywords:
  - ключове слово 1
  - ключове слово 2
author_orcid: '0000-0000-0000-0000'   # або порожній рядок ''
publisher: КПІ ім. Ігоря Сікорського
publisher_place: Київ
language: uk
type: Master Thesis
citation: 'Литвин, І. П. Назва : магістерська дис. : спец. 105 «Прикладна фізика
  та наноматеріали» / Литвин Іван Петрович ; наук. кер. Іванова В. В. – Київ :
  КПІ ім. Ігоря Сікорського, 2026. – 95 с.'
```

---

## Завантаження однієї роботи

```bash
# Магістерська (за замовчуванням)
python ela_upload.py Lytvyn_magistr_meta.yaml

# Бакалаврська
python ela_upload.py Dibilko_bakalavr_meta.yaml --bakalavr
```

Скрипт створює чернетку в ela.kpi.ua, заповнює всі метадані і завантажує PDF. Після завершення заходь на [ela.kpi.ua/mydspace](https://ela.kpi.ua/mydspace), перевіряй і натискай **Submit** вручну.

---

## Пакетне завантаження

Структура папок:

```
Upload_magistr/
  Lytvyn_magistr/
    Lytvyn_magistr.pdf
    Lytvyn_magistr.yaml
  Dibilko_bakalavr/
    Dibilko_bakalavr.pdf
    Dibilko_bakalavr.yaml
```

Тип роботи визначається автоматично по імені папки: якщо містить `bakalavr` — бакалаврська, інакше магістерська.

```bash
# Спочатку перевір що знайде (без реального завантаження)
python ela_batch.py --dry-run

# Завантажити всі з поточної папки
python ela_batch.py

# Або вказати конкретну папку
python ela_batch.py C:/Work/Upload_magistr
```

Після завершення створюється лог-файл `upload_log_YYYYMMDD_HHMMSS.txt`.

---

## Додаткові команди

```bash
# Переглянути назви доступних колекцій
python ela_upload.py --collections

# Список робіт на модерації
python ela_upload.py --list

# Видалити роботу з модерації (workflow)
python ela_upload.py --delete 79175

# Видалити чернетку
python ela_upload.py --delete-draft 88063
```

---

## Поля які заповнюються в ela

| DSpace поле | YAML поле |
|---|---|
| `dc.title` | `title` |
| `dc.contributor.author` | `author` |
| `dc.contributor.advisor` | `advisor` |
| `dc.date.issued` | `date_issued` |
| `dc.description.abstract` | `abstract` |
| `dc.format.extent` | `pages` |
| `dc.subject` | `keywords` |
| `dc.subject.udc` | `udc` |
| `dc.identifier.citation` | `citation` |
| `dc.identifier.orcid` | `author_orcid` |
| `dc.publisher` | `publisher` |
| `dc.publisher.place` | `publisher_place` |
| `dc.language.iso` | `language` |
| `dc.type` | `type` |
