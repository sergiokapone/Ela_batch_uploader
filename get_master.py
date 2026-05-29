import requests
import json

collection_id = "e475e84c-48ff-4236-9633-694b923e4a82"
url = f"https://ela.kpi.ua/server/api/core/collections/{collection_id}/items"

all_items = []
page = 0
size = 100  # запрашиваем по 100 элементов за раз

while True:
    response = requests.get(url, params={"page": page, "size": size})
    if response.status_code != 200:
        print("Ошибка запроса:", response.status_code)
        break

    data = response.json()
    # Проверяем, есть ли элементы в ответе
    items = data.get("_embedded", {}).get("items", [])
    if not items:
        break

    all_items.extend(items)
    print(f"Загружено работ: {len(all_items)}")

    # Проверяем, есть ли следующая страница в ссылках (_links)
    if "next" not in data.get("_links", {}):
        break

    page += 1

# Сохраняем результат в файл
with open("kpi_works.json", "w", encoding="utf-8") as f:
    json.dump(all_items, f, ensure_ascii=False, indent=4)

print("Готово! Все данные сохранены в kpi_works.json")
