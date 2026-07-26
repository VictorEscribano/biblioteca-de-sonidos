#!/usr/bin/env python3
"""Descarga sonidos de Freesound en calidad original via API v2 + OAuth2.

Flujo:
  1. python3 tools/dl_freesound.py --setup     (una vez: autoriza y guarda token)
  2. python3 tools/dl_freesound.py --run       (descarga)

Se descargan sonidos individuales curados por categoria en vez de packs
enteros: los packs vienen sin filtrar y se comen el limite de 2000
peticiones/dia sin control sobre que entra. Buscando por categoria y ordenando
por numero de descargas se consigue mucha mejor relacion calidad/espacio.

Cada audio se acompana de un sidecar .json con autor, licencia y URL, que
build_index.py usa para generar CREDITS.md.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categories import CATEGORIES  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
DEST = BASE / "_staging" / "freesound"
TOKEN_FILE = BASE / "_cache" / "freesound_token.json"
CREDS_FILE = BASE / "_cache" / "freesound_creds.json"
API = "https://freesound.org/apiv2"

# Terminos de busqueda por categoria. Se combinan con filtros de licencia y
# duracion para quedarnos con efectos cortos y usables, no field recordings.
QUERIES = {
    "impactos": ["impact", "hit punch", "crash smash", "slam door", "thud"],
    "whoosh": ["whoosh", "swoosh transition", "riser", "sweep transition"],
    "interfaz": ["ui click", "beep interface", "notification", "button",
                 "glitch digital", "error alert"],
    "ambiente": ["ambience room", "wind ambience", "rain", "forest ambience",
                 "city ambience", "crowd ambience"],
    "foley": ["foley", "footsteps", "door open close", "paper", "cloth",
              "keys jingle", "wood creak"],
    "humano": ["breath", "laugh", "scream", "crowd cheer", "whisper",
               "cough throat"],
    "cinematico": ["cinematic boom", "trailer hit", "stinger", "suspense drone",
                   "horror atmosphere"],
    "armas": ["gunshot", "sword", "explosion", "reload weapon", "arrow bow"],
    "vehiculos": ["car engine", "motorcycle", "train", "airplane", "brake tire"],
    "magia_scifi": ["magic spell", "laser", "sci-fi ui", "power up",
                    "teleport", "robot"],
    "agua": ["water splash", "bubble", "pour liquid", "underwater", "drip"],
    "animales": ["dog bark", "cat meow", "bird chirp", "horse", "insect",
                 "creature growl"],
}


def load_creds():
    if not CREDS_FILE.exists():
        sys.exit("Faltan credenciales. Ejecuta primero: --setup")
    return json.loads(CREDS_FILE.read_text())


def save_creds(cid, secret):
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDS_FILE.write_text(json.dumps({"client_id": cid, "client_secret": secret}))
    CREDS_FILE.chmod(0o600)


def setup(client_id, client_secret):
    save_creds(client_id, client_secret)
    url = (f"{API}/oauth2/authorize/?client_id={client_id}"
           f"&response_type=code")
    print("\n1) Abre esta URL en tu navegador y autoriza la aplicación:\n")
    print(f"   {url}\n")
    print("2) Freesound te mostrará un código. Pégalo aquí.\n")
    code = input("   Código: ").strip()

    r = requests.post(f"{API}/oauth2/access_token/", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
    }, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Error obteniendo token ({r.status_code}): {r.text[:300]}")
    tok = r.json()
    tok["obtained_at"] = time.time()
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tok))
    TOKEN_FILE.chmod(0o600)
    print(f"\nToken guardado. Caduca en {tok.get('expires_in', 86400)//3600} h "
          f"(se renueva solo con el refresh_token).")
    return 0


def get_token():
    if not TOKEN_FILE.exists():
        sys.exit("No hay token. Ejecuta primero: --setup")
    tok = json.loads(TOKEN_FILE.read_text())
    age = time.time() - tok.get("obtained_at", 0)
    if age < tok.get("expires_in", 86400) - 600:
        return tok["access_token"]

    # Caducado: renovar con el refresh_token.
    creds = load_creds()
    r = requests.post(f"{API}/oauth2/access_token/", data={
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
    }, timeout=30)
    if r.status_code != 200:
        sys.exit(f"No se pudo renovar el token: {r.text[:300]}\n"
                 f"Vuelve a ejecutar --setup")
    new = r.json()
    new["obtained_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(new))
    print("Token renovado.")
    return new["access_token"]


class Api:
    """Cliente con control del limite de 60 req/min y 2000 req/dia."""

    def __init__(self, token, daily_cap=1900):
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"
        self.calls = 0
        self.daily_cap = daily_cap
        self.window = []

    def _throttle(self):
        now = time.time()
        self.window = [t for t in self.window if now - t < 60]
        if len(self.window) >= 55:          # margen bajo el limite de 60/min
            wait = 60 - (now - self.window[0]) + 1
            print(f"    (limite por minuto, espero {wait:.0f}s)", flush=True)
            time.sleep(max(wait, 1))
            self.window = []
        self.window.append(time.time())

    def get(self, url, **kw):
        if self.calls >= self.daily_cap:
            raise RuntimeError("Alcanzado el tope diario de peticiones")
        self._throttle()
        self.calls += 1
        return self.s.get(url, timeout=90, **kw)


def search(api, query, licenses, max_dur, page_size=150):
    lic_filter = " OR ".join(f'"{l}"' for l in licenses)
    params = {
        "query": query,
        "filter": f"duration:[0.2 TO {max_dur}] license:({lic_filter})",
        "sort": "downloads_desc",
        "fields": "id,name,tags,license,username,url,filesize,duration,type",
        "page_size": page_size,
    }
    r = api.get(f"{API}/search/text/", params=params)
    if r.status_code != 200:
        print(f"    busqueda fallida ({r.status_code}): {r.text[:160]}")
        return []
    return r.json().get("results", [])


def download_sound(api, snd, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = snd.get("type") or "wav"
    safe = "".join(c for c in snd["name"] if c.isalnum() or c in " ._-")[:80]
    stem = f"{snd['id']}_{safe}".strip() or str(snd["id"])
    out = dest_dir / f"{stem}.{ext}"
    sidecar = out.with_suffix(out.suffix + ".json")

    if out.exists() and out.stat().st_size > 0:
        return "skip", 0

    r = api.get(f"{API}/sounds/{snd['id']}/download/", stream=True)
    if r.status_code != 200:
        return "fail", 0
    tmp = out.with_suffix(out.suffix + ".part")
    n = 0
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
            n += len(chunk)
    tmp.rename(out)

    sidecar.write_text(json.dumps({
        "name": snd["name"], "tags": snd.get("tags", [])[:14],
        "license": license_short(snd.get("license", "")),
        "author": snd.get("username", ""), "url": snd.get("url", ""),
        "freesound_id": snd["id"],
    }, ensure_ascii=False))
    return "ok", n


def license_short(url_or_name):
    s = (url_or_name or "").lower()
    if "publicdomain" in s or "zero" in s or "/cc0" in s:
        return "CC0"
    if "by-nc" in s:
        return "CC-BY-NC (NO comercial)"
    if "/by/" in s or "attribution" in s:
        return "CC-BY (atribución)"
    return url_or_name or "desconocida"


def run(args):
    token = get_token()
    api = Api(token, daily_cap=args.max_requests)
    licenses = ["Creative Commons 0"]
    if args.include_by:
        licenses.append("Attribution")

    budget = int(args.budget_gb * 1024**3)
    per_cat = args.per_category
    got_bytes = 0
    totals = {"ok": 0, "skip": 0, "fail": 0}

    for cid, label, emoji, _ in CATEGORIES:
        queries = QUERIES.get(cid, [])
        if not queries:
            continue
        print(f"\n{emoji} {label}")
        seen, picked = set(), []
        for q in queries:
            if len(picked) >= per_cat:
                break
            try:
                res = search(api, q, licenses, args.max_duration)
            except RuntimeError as e:
                print(f"  {e}")
                return finish(totals, got_bytes, api)
            for s in res:
                if s["id"] in seen:
                    continue
                seen.add(s["id"])
                if s.get("filesize", 0) > args.max_file_mb * 1024**2:
                    continue
                picked.append(s)
                if len(picked) >= per_cat:
                    break
            print(f"  '{q}': {len(res)} resultados, "
                  f"{len(picked)}/{per_cat} acumulados")

        for s in picked:
            if got_bytes >= budget:
                print("\nPresupuesto de disco agotado.")
                return finish(totals, got_bytes, api)
            try:
                st, n = download_sound(api, s, DEST / cid)
            except RuntimeError as e:
                print(f"  {e}")
                return finish(totals, got_bytes, api)
            totals[st] += 1
            got_bytes += n
            if totals["ok"] % 25 == 0 and st == "ok":
                print(f"    {totals['ok']} descargados, "
                      f"{got_bytes / 1024**3:.2f} GB, "
                      f"{api.calls} peticiones usadas", flush=True)

    return finish(totals, got_bytes, api)


def finish(totals, got_bytes, api):
    print(f"\nHecho: {totals['ok']} descargados, {totals['skip']} ya estaban, "
          f"{totals['fail']} fallidos, {got_bytes / 1024**3:.2f} GB")
    print(f"Peticiones usadas: {api.calls} (limite diario 2000)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--client-id")
    ap.add_argument("--client-secret")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--budget-gb", type=float, default=5.0)
    ap.add_argument("--per-category", type=int, default=140)
    ap.add_argument("--max-duration", type=float, default=25.0,
                    help="segundos; corta los field recordings largos")
    ap.add_argument("--max-file-mb", type=float, default=12.0)
    ap.add_argument("--max-requests", type=int, default=1900)
    ap.add_argument("--include-by", action="store_true", default=True,
                    help="incluye CC-BY además de CC0 (genera CREDITS.md)")
    ap.add_argument("--cc0-only", dest="include_by", action="store_false")
    args = ap.parse_args()

    if args.setup:
        cid = args.client_id or input("Client ID: ").strip()
        sec = args.client_secret or input("Client Secret: ").strip()
        return setup(cid, sec)
    if args.run:
        return run(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
