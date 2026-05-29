#!/usr/bin/env python3
"""
КРОК 2: ela_upload.py — Зчитує перевірений YAML, завантажує PDF та метадані в ela.KPI.
Використання: python ela_upload.py thesis_meta.yaml
"""

import sys
import os
import re
import yaml
import requests

# === НАЛАШТУВАННЯ АВТОРИЗАЦІЇ ===
BASE_URL = "https://ela.kpi.ua/server/api"
EMAIL = "phes.ipt.kpi@gmail.com"
PASSWORD = "phes_4549057"  # Впиши пароль від акаунту кафедри
# Колекції кафедри — заповнюється після python ela_upload.py --collections
COLLECTIONS = {
    "magistr":  "e475e84c-48ff-4236-9633-694b923e4a82",
    "bakalavr": "13647e65-d1d5-49d3-abfb-49957e3b0d00",
}

# UUID за замовчуванням (якщо не вказано --type)
COLLECTION_UUID = COLLECTIONS["magistr"]


class ElaClient:
    def __init__(self, email, password):
        self.session = requests.Session()
        self.email = email
        self.password = password
        self.token = None
        self.xsrf_token = None

    def login(self):
        print("🔑 Авторизація в ela.KPI...")

        # 1. Смикаємо базовий URL API
        init_res = self.session.get(f"{BASE_URL}")
        if init_res.status_code != 200:
            print(f"❌ Не вдалося з'єднатися з API. Код відповіді: {init_res.status_code}")
            return False

        # 2. Формуємо точну адресу логіну
        try:
            links = init_res.json().get('_links', {})
            if 'authn' in links:
                base_auth = links['authn']['href']
                login_url = f"{base_auth.rstrip('/')}/login"
            else:
                login_url = f"{BASE_URL}/authn/login"
        except Exception:
            login_url = f"{BASE_URL}/authn/login"

        # 3. Витягуємо первинний XSRF токен
        self.xsrf_token = (
            self.session.cookies.get("XSRF-TOKEN") or
            self.session.cookies.get("DSPACE-XSRF-COOKIE")
        )

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        if self.xsrf_token:
            headers["X-XSRF-TOKEN"] = self.xsrf_token

        # 4. Спроба входу
        login_res = self.session.post(
            login_url,
            data={"user": self.email, "password": self.password},
            headers=headers
        )

        if login_res.status_code == 200:
            auth_header = login_res.headers.get("Authorization")
            if auth_header and "Bearer " in auth_header:
                self.token = auth_header.split("Bearer ")[1]

                # === КРИТИЧНЕ ОНОВЛЕННЯ ТУТ ===
                # DSpace змінив токен! Обов'язково витягуємо новий авторизований CSRF токен з куків сесії
                self.xsrf_token = (
                    self.session.cookies.get("XSRF-TOKEN") or
                    self.session.cookies.get("DSPACE-XSRF-COOKIE")
                )

                # Якщо кука не встигла оновитися в jar, дістаємо її напряму з заголовка Set-Cookie відповіді логіну
                if "Set-Cookie" in login_res.headers:
                    cookies_header = login_res.headers["Set-Cookie"]
                    m = re.search(r'(?:XSRF-TOKEN|DSPACE-XSRF-COOKIE)=([^;]+)', cookies_header)
                    if m:
                        self.xsrf_token = m.group(1)
                        # Синхронізуємо її назад у сесію
                        self.session.cookies.set("XSRF-TOKEN", self.xsrf_token)

                print("✓ Авторизація успішна!")
                return True

        elif login_res.status_code in [401, 403]:
            print(f"❌ Помилка входу: {login_res.status_code}. Сервер відхилив логін або пароль.")
            return False
        else:
            print(f"❌ Помилка входу: {login_res.status_code} на адресу {login_url}")
            return False


    def get_headers(self, content_type="application/json"):
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "uk;q=1,ru;q=0.1,en-US;q=0.09,uk;q=0.08",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": content_type,
            "Origin": "https://ela.kpi.ua",
            "Pragma": "no-cache",
            "Referer": "https://ela.kpi.ua/home",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            # Повністю копіюємо твій User-Agent з Windows 10
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"'
        }

        if hasattr(self, 'token') and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        xsrf_token = self.session.cookies.get("XSRF-TOKEN") or self.session.cookies.get("DSPACE-XSRF-COOKIE")
        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token

        return headers


    def create_workspace_item(self, collection_uuid):
        print("📝 Створення чернетки...")
        try:
            headers = self.get_headers(content_type="application/json")
            res = self.session.post(
                f"{BASE_URL}/submission/workspaceitems?owningCollection={collection_uuid}",
                headers=headers,
                data="",
                timeout=45
            )
            if res.status_code == 201:
                item_id = res.json()['id']
                print(f"✓ Чернетку створено! ID: {item_id}")
                return item_id
            else:
                print(f"❌ Помилка створення: {res.status_code} | {res.text[:300]}")
                return None
        except Exception as e:
            print(f"❌ Помилка: {e}")
            return None

    def check_workspace_item(self, workspace_id):
        """Перевіряє стан чернетки і які секції мають помилки валідації"""
        url = f"{BASE_URL}/submission/workspaceitems/{workspace_id}"
        res = self.session.get(url, headers=self.get_headers(), timeout=30)
        if res.status_code == 200:
            data = res.json()
            # Помилки валідації
            errors = data.get('errors', [])
            if errors:
                print(f"  ⚠️  Помилки валідації ({len(errors)}):")
                for e in errors:
                    print(f"     - {e.get('message')} → {e.get('paths')}")
            else:
                print("  ✓ Помилок валідації немає")
            # Заповнені секції
            sections = data.get('sections', {})
            print(f"  📋 Секції: {list(sections.keys())}")
            return errors
        else:
            print(f"  GET чернетки: {res.status_code} | {res.text[:300]}")
            return []


    def upload_pdf_file(self, workspace_id, file_path):
        print(f" Завантаження файлу {os.path.basename(file_path)}...")
        url = f"{BASE_URL}/submission/workspaceitems/{workspace_id}"
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            res = self.session.post(url, headers=self.get_headers(content_type=None), files=files)
        return res.status_code == 201

    def patch_metadata(self, workspace_id, meta):
        print(" Заповнення перевірених метаданих (JSON Patch)...")
        url = f"{BASE_URL}/submission/workspaceitems/{workspace_id}"

        patch_data = []

        if 'title' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.title", "value": [{"value": meta['title'], "language": "uk"}]})
        if 'author' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.contributor.author", "value": [{"value": meta['author']}]})
        if 'advisor' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.contributor.advisor", "value": [{"value": meta['advisor']}]})
        if 'udc' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpagetwo/dc.subject.udc", "value": [{"value": meta['udc']}]})
        if 'pages' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.format.extent", "value": [{"value": str(meta['pages'])}]})
        if 'abstract' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpagetwo/dc.description.abstract", "value": [{"value": meta['abstract'], "language": "uk"}]})
        if 'keywords' in meta and meta['keywords']:
            kw_value = [{"value": kw, "language": "uk", "place": i} for i, kw in enumerate(meta['keywords'])]
            patch_data.append({"op": "add", "path": "/sections/traditionalpagetwo/dc.subject", "value": kw_value})

        # дата публікації (рік захисту)
        date_issued = meta.get('date_issued') or meta.get('year') or '2025'
        patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.date.issued", "value": [{"value": str(date_issued)}]})

        # видавець
        if 'publisher' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.publisher", "value": [{"value": meta['publisher']}]})

        # місто видання
        if 'publisher_place' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.publisher.place", "value": [{"value": meta['publisher_place']}]})

        # бібліографічний опис (citation)
        if 'citation' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.identifier.citation", "value": [{"value": meta['citation']}]})

        # ORCID автора (тільки якщо заповнений)
        if meta.get('author_orcid'):
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.identifier.orcid", "value": [{"value": meta['author_orcid']}]})

        # тип документу
        if 'type' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.type", "value": [{"value": meta['type']}]})

        # мова
        if 'language' in meta:
            patch_data.append({"op": "add", "path": "/sections/traditionalpageone/dc.language.iso", "value": [{"value": meta['language']}]})

        res = self.session.patch(url, headers=self.get_headers(), json=patch_data)
        return res.status_code == 200


    def accept_license(self, workspace_id):
        """Програмно приймає ліцензію репозиторію"""
        print(" Прийняття ліцензії...")
        url = f"{BASE_URL}/submission/workspaceitems/{workspace_id}"
        patch_data = [{"op": "replace", "path": "/sections/license/granted", "value": True}]
        res = self.session.patch(url, headers=self.get_headers(), json=patch_data, timeout=30)
        print(f"  Ліцензія: {res.status_code}")
        return res.status_code == 200

    def send_to_workflow(self, workspace_id):
        print(f"🚀 Надсилання чернетки №{workspace_id} на модерацію...")

        workspace_url = f"{BASE_URL}/submission/workspaceitems/{workspace_id}"

        # Спроба А: стандартний DSpace 7 спосіб
        try:
            url = f"{BASE_URL}/workflow/workflowitems"
            headers = self.get_headers(content_type="text/uri-list")
            res = self.session.post(url, headers=headers, data=workspace_url, timeout=45)
            print(f"  Спроба А: {res.status_code} | {res.text[:300]}")
            if res.status_code in [200, 201]:
                return True
        except Exception as e:
            print(f"  Спроба А впала: {e}")

        # Спроба Б: з параметром projection
        try:
            url = f"{BASE_URL}/workflow/workflowitems?projection=full"
            headers = self.get_headers(content_type="text/uri-list")
            res = self.session.post(url, headers=headers, data=workspace_url, timeout=45)
            print(f"  Спроба Б: {res.status_code} | {res.text[:300]}")
            if res.status_code in [200, 201]:
                return True
        except Exception as e:
            print(f"  Спроба Б впала: {e}")

        # Спроба В: деякі DSpace інстанції очікують повний URI з https://
        try:
            full_url = f"https://ela.kpi.ua/server/api/submission/workspaceitems/{workspace_id}"
            url = f"{BASE_URL}/workflow/workflowitems"
            headers = self.get_headers(content_type="text/uri-list")
            res = self.session.post(url, headers=headers, data=full_url, timeout=45)
            print(f"  Спроба В: {res.status_code} | {res.text[:300]}")
            if res.status_code in [200, 201]:
                return True
        except Exception as e:
            print(f"  Спроба В впала: {e}")

        return False


    def list_workflow_items(self):
        print("📋 Список робіт на модерації...")
        # Пробуємо з фільтром по submitter
        for url in [
            f"{BASE_URL}/workflow/workflowitems?size=50&embedLevelDepth=1",
            f"{BASE_URL}/submission/workspaceitems?size=50",  # чернетки
        ]:
            res = self.session.get(url, headers=self.get_headers(), timeout=30)
            print(f"  {url.split('/')[-1].split('?')[0]}: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                items = data.get('_embedded', {}).get('workflowitems',
                        data.get('_embedded', {}).get('workspaceitems', []))
                if items:
                    for item in items:
                        wf_id = item.get('id', '?')
                        page1 = item.get('sections', {}).get('traditionalpageone', {})
                        title = (page1.get('dc.title') or [{}])[0].get('value', '?')
                        author = (page1.get('dc.contributor.author') or [{}])[0].get('value', '?')
                        print(f"  [{wf_id}] {author} — {title[:60]}")
                    return items
        return []


    def delete_workflow_item(self, workflow_id):
        """Видаляє роботу з черги модерації"""
        print(f"🗑️  Видалення роботи №{workflow_id} з модерації...")
        url = f"{BASE_URL}/workflow/workflowitems/{workflow_id}"
        res = self.session.delete(url, headers=self.get_headers(), timeout=30)
        print(f"  Статус: {res.status_code}")
        if res.status_code == 204:
            print("✓ Роботу успішно видалено!")
            return True
        else:
            print(f"  Відповідь: {res.text[:300]}")
            return False

    def delete_workspace_item(self, workspace_id):
        """Видаляє чернетку (ще не відправлену на модерацію)"""
        print(f"🗑️  Видалення чернетки №{workspace_id}...")
        url = f"{BASE_URL}/submission/workspaceitems/{workspace_id}"
        res = self.session.delete(url, headers=self.get_headers(), timeout=30)
        print(f"  Статус: {res.status_code}")
        if res.status_code == 204:
            print("✓ Чернетку успішно видалено!")
            return True
        else:
            print(f"  Відповідь: {res.text[:300]}")
            return False


    def list_collections(self):
        """Показує назви всіх колекцій до яких має доступ акаунт"""
        print("📚 Перевірка колекцій кафедри...\n")
        known_ids = [
            "942", "946", "943", "948", "848", "945", "944",
            "13647e65-d1d5-49d3-abfb-49957e3b0d00",
            "e475e84c-48ff-4236-9633-694b923e4a82"
        ]
        for cid in known_ids:
            # Числові ID — пошук через handle, UUID — напряму
            if cid.isdigit():
                url = f"{BASE_URL}/core/collections?page=0&size=1&query=id:{cid}"
                res = self.session.get(url, headers=self.get_headers(), timeout=15)
                if res.status_code == 200:
                    items = res.json().get('_embedded', {}).get('collections', [])
                    if items:
                        name = items[0].get('name', '?')
                        uuid = items[0].get('uuid', '?')
                        print(f"  [{cid:>5}] {uuid} — {name}")
                        continue
                print(f"  [{cid:>5}] — не вдалось отримати назву")
            else:
                url = f"{BASE_URL}/core/collections/{cid}"
                res = self.session.get(url, headers=self.get_headers(), timeout=15)
                if res.status_code == 200:
                    name = res.json().get('name', '?')
                    print(f"  [uuid ] {cid} — {name}")
                else:
                    print(f"  [uuid ] {cid} — помилка {res.status_code}")


def main():
    if len(sys.argv) < 2:
        print("Використання:")
        print("  python ela_upload.py thesis_meta.yaml              — завантажити магістерську (чернетка)")
        print("  python ela_upload.py thesis_meta.yaml --submit      — завантажити і одразу на модерацію")
        print("  python ela_upload.py thesis_meta.yaml --bakalavr   — завантажити бакалаврську")
        print("  python ela_upload.py --collections                 — список колекцій кафедри")
        print("  python ela_upload.py --list                        — список робіт на модерації")
        print("  python ela_upload.py --delete <id>                 — видалити з модерації")
        print("  python ela_upload.py --delete-draft <id>           — видалити чернетку")
        sys.exit(1)

    client = ElaClient(EMAIL, PASSWORD)

    # --- РЕЖИМ: колекції ---
    if sys.argv[1] == '--collections':
        if not client.login(): sys.exit(1)
        client.list_collections()
        sys.exit(0)

    # --- РЕЖИМ: список ---
    if sys.argv[1] == '--list':
        if not client.login(): sys.exit(1)
        client.list_workflow_items()
        sys.exit(0)

    # --- РЕЖИМ: видалити з модерації ---
    if sys.argv[1] == '--delete':
        if len(sys.argv) < 3:
            print("Вкажи ID: python ela_upload.py --delete <id>")
            sys.exit(1)
        if not client.login(): sys.exit(1)
        client.delete_workflow_item(int(sys.argv[2]))
        sys.exit(0)

    # --- РЕЖИМ: видалити чернетку ---
    if sys.argv[1] == '--delete-draft':
        if len(sys.argv) < 3:
            print("Вкажи ID: python ela_upload.py --delete-draft <id>")
            sys.exit(1)
        if not client.login(): sys.exit(1)
        client.delete_workspace_item(int(sys.argv[2]))
        sys.exit(0)

    # --- РЕЖИМ: завантажити ---
    yaml_path = sys.argv[1]
    if not os.path.exists(yaml_path):
        print(f"❌ Файл метаданих не знайдено: {yaml_path}")
        sys.exit(1)

    # Зчитуємо вже відкоригований YAML
    with open(yaml_path, 'r', encoding='utf-8') as f:
        meta = yaml.safe_load(f)

    # Визначаємо шлях до PDF (шукаємо його в тій же папці, що й YAML)
    yaml_dir = os.path.dirname(os.path.abspath(yaml_path))
    pdf_path = os.path.join(yaml_dir, meta.get('file_name', ''))

    if not os.path.exists(pdf_path):
        # Якщо за відносним шляхом у YAML не знайдено, пробуємо шукати просто в поточній робочій теці
        pdf_path = meta.get('file_name', '')
        if not os.path.exists(pdf_path):
            print(f"❌ PDF файл не знайдено поруч: {meta.get('file_name')}")
            sys.exit(1)

    if not client.login(): sys.exit(1)

    # 1. Створюємо картку чернетки
    # Вибір колекції: за замовчуванням магістерська, з --bakalavr — бакалаврська
    if '--bakalavr' in sys.argv:
        collection = COLLECTIONS.get('bakalavr') or COLLECTION_UUID
        if not collection:
            print("❌ UUID бакалаврської колекції не заповнено. Запусти --collections і впиши в COLLECTIONS['bakalavr']")
            sys.exit(1)
    else:
        collection = COLLECTION_UUID
    w_id = client.create_workspace_item(collection)
    if not w_id:
        print("❌ Помилка створення чернетки."); sys.exit(1)

    # 2. Завантажуємо файл
    if not client.upload_pdf_file(w_id, pdf_path):
        print("❌ Помилка завантаження файлу."); sys.exit(1)


    # 3. Метадані
    if not client.patch_metadata(w_id, meta):
        print("❌ Помилка надсилання метаданих."); sys.exit(1)

    # 3.5 Ліцензія
    if not client.accept_license(w_id):
        print("❌ Помилка прийняття ліцензії."); sys.exit(1)

    # 3.6 Перевірка
    print("\n🔍 Перевірка стану чернетки...")
    errors = client.check_workspace_item(w_id)
    if errors:
        print("  ⛔ Є помилки валідації"); sys.exit(1)

    if '--submit' in sys.argv:
        print("\n🚀 --submit: відправляємо одразу в workflow...")
        if client.send_to_workflow(w_id):
            print(f"🎉 Готово! Роботу '{meta.get('author', '')}' відправлено на модерацію!")
        else:
            print("❌ Помилка відправки в workflow. Чернетка збережена — відправ вручну.")
            print(f"   https://ela.kpi.ua/mydspace")
    else:
        print(f"\n🎉 Готово! Чернетку для '{meta.get('author', '')}' створено та заповнено.")
        print(f"   Перевір та відправ вручну на: https://ela.kpi.ua/mydspace")


if __name__ == "__main__":
    main()

