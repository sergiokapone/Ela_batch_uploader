#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from pathlib import Path
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import os

load_dotenv()

WP_USER   = os.getenv("WP_USER")
WP_PASS   = os.getenv("WP_PASS")
HTML_FILE = "output_html/wp_page.html"
PAGE_ID   = 2426
WP_URL    = "https://apd.ipt.kpi.ua/"

html = Path(HTML_FILE).read_text(encoding="utf-8")

r = requests.post(
    f"{WP_URL}/wp-json/wp/v2/pages/{PAGE_ID}",
    auth=HTTPBasicAuth(WP_USER, WP_PASS),
    json={"content": html},
)
r.raise_for_status()
print(f"OK: {r.json().get('link')}")

input("Press Enter to continue...")
