#!/usr/bin/env python3
"""Cataloga los bundles de Sonniss GDC espejados en gamesounds.xyz.

El listado de directorios ya expone nombre y tamano, asi que se construye el
catalogo completo sin peticiones HEAD. El resultado se cachea en JSON para que
la seleccion por presupuesto de disco sea instantanea.

Licencia Sonniss GDC: royalty-free, uso comercial ilimitado, sin atribucion.
"""
import json
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import requests

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "_cache" / "gamesounds_catalog.json"
ROOT = "https://gamesounds.xyz/"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".aif", ".aiff")

# Directorios de servicio del listador que no contienen audio.
SKIP_DIRS = {"awstats-icon", "awstatsicons", "icon"}

SIZE_RE = re.compile(r"([\d.]+)\s*(B|KB|MB|GB)\b", re.I)
MULT = {"b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}

session = requests.Session()
session.headers["User-Agent"] = UA
adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16,
                                        max_retries=3)
session.mount("https://", adapter)

_print_lock = Lock()
_seen_lock = Lock()
seen_dirs = set()


def parse_size(text):
    m = SIZE_RE.search(text)
    if not m:
        return 0
    return int(float(m.group(1)) * MULT[m.group(2).lower()])


def fetch_dir(rel):
    """Lista un directorio: devuelve (subdirs, archivos_de_audio)."""
    url = ROOT + "?dir=" + urllib.parse.quote(rel)
    for attempt in range(3):
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
            break
        except Exception:
            if attempt == 2:
                return [], []
            time.sleep(2 * (attempt + 1))

    html = r.text
    subdirs, files = [], []

    for d in re.findall(r"\?dir=([^\"'&<>]*)", html):
        d = urllib.parse.unquote(d)
        # El listador incluye enlaces al propio dir y a ancestros; filtra.
        if d and d != rel and d.startswith(rel + "/") and d.count("/") == rel.count("/") + 1:
            subdirs.append(d)

    # Cada fila de archivo: href="ruta.wav" ... luego el tamano en un div.
    for m in re.finditer(r'href="([^"]+)"', html):
        href = urllib.parse.unquote(m.group(1))
        if not href.lower().endswith(AUDIO_EXT):
            continue
        size = parse_size(html[m.end():m.end() + 1800])
        files.append({"path": href, "size": size})

    return sorted(set(subdirs)), files


def crawl(roots, workers=8):
    all_files = []
    queue = list(roots)
    done = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while queue:
            futures = {pool.submit(fetch_dir, d): d for d in queue}
            queue = []
            for fut in as_completed(futures):
                subdirs, files = fut.result()
                done += 1
                with _seen_lock:
                    for s in subdirs:
                        if s not in seen_dirs:
                            seen_dirs.add(s)
                            queue.append(s)
                all_files.extend(files)
                if done % 25 == 0:
                    with _print_lock:
                        print(f"  {done} dirs recorridos, "
                              f"{len(all_files)} archivos, "
                              f"{len(queue)} en cola", flush=True)
    return all_files


def main():
    print("Listando directorios raiz de gamesounds.xyz...")
    r = session.get(ROOT, timeout=45)
    r.raise_for_status()
    roots = sorted({urllib.parse.unquote(d)
                    for d in re.findall(r"\?dir=([^\"'&<>]*)", r.text)})
    roots = [d for d in roots if d and d not in SKIP_DIRS and "/" not in d]
    print(f"Colecciones encontradas: {len(roots)}")
    for d in roots:
        print("  -", d)
    print()

    seen_dirs.update(roots)
    t0 = time.time()
    files = crawl(roots)

    total = sum(f["size"] for f in files)
    print(f"\nCatalogo completo: {len(files)} archivos, "
          f"{total / 1024**3:.1f} GB, en {time.time() - t0:.0f}s")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(files, ensure_ascii=False))
    print(f"Guardado en {CACHE}")

    # Desglose por coleccion.
    by_coll = {}
    for f in files:
        coll = f["path"].split("/")[0]
        e = by_coll.setdefault(coll, [0, 0])
        e[0] += 1
        e[1] += f["size"]
    print("\nPor coleccion:")
    for coll, (n, sz) in sorted(by_coll.items(), key=lambda x: -x[1][1]):
        print(f"  {sz / 1024**3:7.2f} GB  {n:6d} archivos  {coll[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
