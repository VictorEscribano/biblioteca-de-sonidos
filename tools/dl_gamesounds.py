#!/usr/bin/env python3
"""Descarga los bundles de Sonniss GDC desde el espejo gamesounds.xyz.

Selecciona con tope de tamano por archivo y presupuesto global de disco. Los
archivos de Sonniss tienen mediana 6.7 MB pero media 31.7 MB (hay grabaciones
de mas de 1 GB), asi que el tope por archivo es lo que decide cuanta variedad
entra: a 20 MB caben 4389 sonidos en 19.8 GB, a 30 MB solo 359 mas por 8.7 GB.

Reanudable: relee lo ya descargado y salta. Ctrl-C y volver a lanzar es seguro.
"""
import argparse
import json
import os
import queue
import sys
import threading
import time
import urllib.parse
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categories import classify  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
CATALOG = BASE / "_cache" / "gamesounds_catalog.json"
DEST = BASE / "_staging" / "gamesounds"
ROOT = "https://gamesounds.xyz/"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_lock = threading.Lock()
stats = {"ok": 0, "skip": 0, "fail": 0, "bytes": 0}


def make_session():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.mount("https://", requests.adapters.HTTPAdapter(
        pool_connections=4, pool_maxsize=4, max_retries=2))
    return s


def select(catalog, cap_bytes, budget_bytes, collections):
    """Elige archivos dentro del tope por archivo y del presupuesto global.

    Reparte el presupuesto en pasadas por categoria (round-robin) para que un
    pack enorme de coches no se coma el hueco de las demas categorias.
    """
    cands = []
    for f in catalog:
        coll = f["path"].split("/")[0]
        if collections and not any(c.lower() in coll.lower() for c in collections):
            continue
        if f["size"] <= 0 or f["size"] > cap_bytes:
            continue
        parts = f["path"].split("/")
        cid, _, _ = classify(parts[-2] if len(parts) > 1 else "", parts[-1])
        cands.append((cid, f))

    buckets = {}
    for cid, f in cands:
        buckets.setdefault(cid, []).append(f)
    # Dentro de cada categoria, primero los pequenos: mas sonidos por GB.
    for v in buckets.values():
        v.sort(key=lambda f: f["size"])

    chosen, total = [], 0
    idx = {k: 0 for k in buckets}
    while True:
        progressed = False
        for cid in sorted(buckets):
            i = idx[cid]
            if i >= len(buckets[cid]):
                continue
            f = buckets[cid][i]
            if total + f["size"] > budget_bytes:
                continue
            chosen.append(f)
            total += f["size"]
            idx[cid] = i + 1
            progressed = True
        if not progressed:
            break
    return chosen, total


def local_path(rel):
    """Ruta local espejo, saneando nombres problematicos."""
    parts = [p.replace("\x00", "") for p in rel.split("/")]
    return DEST.joinpath(*parts)


def worker(q, session):
    while True:
        try:
            f = q.get_nowait()
        except queue.Empty:
            return
        rel = f["path"]
        dest = local_path(rel)
        try:
            if dest.exists() and abs(dest.stat().st_size - f["size"]) < 2048:
                with _lock:
                    stats["skip"] += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            url = ROOT + urllib.parse.quote(rel)
            with session.get(url, stream=True, timeout=180) as r:
                r.raise_for_status()
                tmp = dest.with_name(dest.name + ".part")
                n = 0
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 17):
                        fh.write(chunk)
                        n += len(chunk)
                os.replace(tmp, dest)
            with _lock:
                stats["ok"] += 1
                stats["bytes"] += n
        except Exception:
            with _lock:
                stats["fail"] += 1
            try:
                tmp = dest.with_name(dest.name + ".part")
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
        finally:
            q.task_done()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-gb", type=float, default=20.0,
                    help="presupuesto total de disco")
    ap.add_argument("--cap-mb", type=float, default=20.0,
                    help="tope de tamano por archivo")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--collections", nargs="*", default=["Sonniss"],
                    help="filtra por nombre de coleccion")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    catalog = json.loads(CATALOG.read_text())
    chosen, total = select(catalog, int(args.cap_mb * 1024**2),
                           int(args.budget_gb * 1024**3), args.collections)
    print(f"Seleccionados {len(chosen)} archivos, {total / 1024**3:.2f} GB "
          f"(tope {args.cap_mb:.0f} MB/archivo, presupuesto "
          f"{args.budget_gb:.0f} GB)")
    if args.dry_run:
        return 0

    DEST.mkdir(parents=True, exist_ok=True)
    q = queue.Queue()
    for f in chosen:
        q.put(f)

    t0 = time.time()
    threads = []
    for _ in range(args.workers):
        t = threading.Thread(target=worker, args=(q, make_session()), daemon=True)
        t.start()
        threads.append(t)

    n = len(chosen)
    while any(t.is_alive() for t in threads):
        time.sleep(5)
        with _lock:
            done = stats["ok"] + stats["skip"] + stats["fail"]
            gb = stats["bytes"] / 1024**3
            el = time.time() - t0
        rate = gb / el * 3600 if el > 5 else 0
        eta = (total / 1024**3 - gb) / rate * 60 if rate > 0.01 else 0
        print(f"  {done}/{n}  ok={stats['ok']} skip={stats['skip']} "
              f"fail={stats['fail']}  {gb:.2f} GB  "
              f"{rate:.1f} GB/h  ETA {eta:.0f} min", flush=True)

    for t in threads:
        t.join()
    print(f"\nHecho en {(time.time() - t0) / 60:.1f} min: "
          f"{stats['ok']} descargados, {stats['skip']} ya estaban, "
          f"{stats['fail']} fallidos, {stats['bytes'] / 1024**3:.2f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
