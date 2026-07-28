#!/usr/bin/env python3
"""Добавляет официальные греческие названия (name_el) в data/signs_full.json.

Источник — греческая версия того же каталога: https://driving.cy/el/signs.
Подписи берутся из атрибута alt у картинки и связываются с карточкой по имени
файла изображения, поэтому перевод не нужен: это формулировки самого сайта.

Запуск: python3 scripts/fetch_greek_names.py [--dry-run]
"""
import html
import json
import os
import re
import sys
import urllib.request
from urllib.parse import unquote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "signs_full.json")
URL_EL = "https://driving.cy/el/signs"
DRY_RUN = "--dry-run" in sys.argv

IMG_RE = re.compile(r'<img alt="([^"]*)"[^>]*?src="/signs/Signs/([^"]+)"')


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (study flashcards)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def labels(page):
    """{имя файла изображения: подпись} — первое вхождение файла на странице."""
    out = {}
    for alt, fname in IMG_RE.findall(page):
        out.setdefault(unquote(fname), html.unescape(alt).strip())
    return out


def main():
    el = labels(fetch(URL_EL))
    print(f"получено подписей с {URL_EL}: {len(el)}")

    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    missing = []
    for card in data["cards"]:
        fname = unquote(card["image_url"].rsplit("/", 1)[-1])
        name_el = el.get(fname)
        if not name_el:
            missing.append(card["id"])
            continue
        card["name_el"] = name_el

    print(f"проставлено name_el: {len(data['cards']) - len(missing)} из {len(data['cards'])}")
    for cid in missing:
        print(f"  НЕТ ГРЕЧЕСКОГО НАЗВАНИЯ: {cid}")

    if DRY_RUN:
        print("--dry-run: файл не изменён")
        return
    if missing:
        print("Есть карточки без греческого названия — файл не изменён", file=sys.stderr)
        sys.exit(1)

    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"записано: {DATA}")


if __name__ == "__main__":
    main()
