#!/usr/bin/env python3
"""Descarga todos los packs de audio CC0 de kenney.nl.

Licencia CC0 (dominio publico): uso comercial libre, sin atribucion.
"""
import re
import sys
import zipfile
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
STAGING = BASE / "_staging" / "kenney"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

session = requests.Session()
session.headers["User-Agent"] = UA


def list_audio_packs():
    """Devuelve los slugs de los packs de audio del catalogo de Kenney."""
    r = session.get("https://kenney.nl/assets/category:Audio", timeout=30)
    r.raise_for_status()
    slugs = set(re.findall(r"/assets/([a-z0-9-]+)", r.text))
    return sorted(slugs - {"category", "series", "tag"})


def zip_url_for(slug):
    """Extrae la URL del zip (lleva un hash, hay que raspar la pagina)."""
    r = session.get(f"https://kenney.nl/assets/{slug}", timeout=30)
    r.raise_for_status()
    urls = re.findall(r'https?://[^"\'<> ]*\.zip', r.text)
    return urls[0] if urls else None


def download(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"    ya existe, salto ({dest.stat().st_size / 1024:.0f} KB)")
        return True
    with session.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        tmp.rename(dest)
    print(f"    OK ({dest.stat().st_size / 1024:.0f} KB)")
    return True


def main():
    STAGING.mkdir(parents=True, exist_ok=True)
    packs = list_audio_packs()
    print(f"Packs de audio en Kenney: {len(packs)}\n")

    ok = fail = 0
    for slug in packs:
        print(f"[{slug}]")
        try:
            url = zip_url_for(slug)
            if not url:
                print("    sin enlace de descarga, salto")
                fail += 1
                continue
            dest = STAGING / f"kenney_{slug}.zip"
            download(url, dest)
            # Verifica que el zip no este corrupto antes de darlo por bueno.
            with zipfile.ZipFile(dest) as z:
                n = sum(1 for n in z.namelist()
                        if n.lower().endswith((".wav", ".ogg", ".mp3", ".flac")))
            print(f"    {n} archivos de audio dentro")
            ok += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            fail += 1

    print(f"\nHecho. {ok} packs OK, {fail} fallidos.")
    total = sum(f.stat().st_size for f in STAGING.glob("*.zip"))
    print(f"Total descargado: {total / 1024 / 1024:.1f} MB")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
