#!/usr/bin/env python3
"""Anade a la libreria un pack descargado a mano, con su procedencia.

Uso:
    python3 tools/add_pack.py ~/Downloads/provence.zip \\
        --vendor "Ocular Sounds" --license "Ocular commercial (royalty-free)"

    python3 tools/add_pack.py ~/Downloads/UnaCarpeta --vendor "Ocular Sounds"

Copia (o enlaza) el contenido en _staging/manual/<vendor>/<pack>/ y registra
la procedencia en _cache/manual_sources.json, que build_index.py lee para
etiquetar cada sonido con su fuente y licencia reales en vez de adivinarlas.

Despues: ./sonidos index
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MANUAL = BASE / "_staging" / "manual"
REGISTRY = BASE / "_cache" / "manual_sources.json"
AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".aif", ".aiff"}


def safe_name(s):
    return re.sub(r"[^\w .&-]", "", s).strip() or "pack"


def load_registry():
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def extract_zip(src, dest, depth=0, max_depth=3):
    """Extrae los audios de un zip, entrando en los zip anidados.

    Los Download Center suelen servir un zip que solo contiene otro zip (o uno
    por libreria), asi que mirar un unico nivel devolvia cero archivos.
    """
    n = 0
    nested = []
    with zipfile.ZipFile(src) as z:
        for m in z.namelist():
            suffix = Path(m).suffix.lower()
            if suffix == ".zip" and depth < max_depth:
                nested.append(m)
                continue
            if suffix not in AUDIO_EXT:
                continue
            # Conserva subcarpetas pero sanea contra zip-slip.
            parts = [p for p in Path(m.replace("\\", "/")).parts
                     if p not in ("", ".", "..") and not p.startswith("/")]
            if not parts:
                continue
            target = Path(os.path.normpath(dest.joinpath(*parts)))
            if not str(target).startswith(str(dest.resolve())):
                continue
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as fsrc, open(target, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)
            n += 1

        for m in nested:
            inner_name = Path(m).stem
            print(f"    zip anidado: {inner_name}")
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                with z.open(m) as fsrc:
                    shutil.copyfileobj(fsrc, tmp)
                tmp_path = Path(tmp.name)
            try:
                n += extract_zip(tmp_path, dest / safe_name(inner_name),
                                 depth + 1, max_depth)
            except zipfile.BadZipFile:
                print(f"    (no es un zip válido, se ignora)")
            finally:
                tmp_path.unlink(missing_ok=True)
    return n


def copy_tree(src, dest, link=True):
    n = 0
    for p in src.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in AUDIO_EXT:
            continue
        target = dest / p.relative_to(src)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if link:
                os.link(p, target)     # mismo disco: no duplica espacio
            else:
                shutil.copy2(p, target)
        except OSError:
            shutil.copy2(p, target)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="zip o carpeta descargada")
    ap.add_argument("--vendor", required=True,
                    help='p.ej. "Ocular Sounds"')
    ap.add_argument("--license", default="Comercial royalty-free",
                    help="licencia tal cual la da el proveedor")
    ap.add_argument("--url", default="", help="enlace al producto")
    ap.add_argument("--pack", default="", help="nombre del pack (por defecto, "
                                               "el del archivo o carpeta)")
    ap.add_argument("--copy", action="store_true",
                    help="copiar en vez de enlazar (por defecto enlaza)")
    args = ap.parse_args()

    src = Path(args.source).expanduser().resolve()
    if not src.exists():
        sys.exit(f"No existe: {src}\n"
                 f"Comprueba la ruta; si aún no has descargado el pack, "
                 f"bájalo primero y vuelve a ejecutar.")

    vendor = safe_name(args.vendor)
    pack = safe_name(args.pack or src.stem)
    dest = MANUAL / vendor / pack
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Añadiendo «{pack}» de {vendor}")
    if src.is_file() and src.suffix.lower() == ".zip":
        n = extract_zip(src, dest)
        print(f"  descomprimidos {n} audios")
    elif src.is_dir():
        n = copy_tree(src, dest, link=not args.copy)
        print(f"  {'copiados' if args.copy else 'enlazados'} {n} audios")
    else:
        sys.exit("La fuente debe ser un .zip o una carpeta")

    if not n:
        sys.exit("No se encontró ningún archivo de audio dentro")

    reg = load_registry()
    reg[f"{vendor}/{pack}"] = {
        "vendor": args.vendor,
        "license": args.license,
        "url": args.url,
        "files": n,
    }
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2))

    total = sum(v["files"] for v in reg.values())
    print(f"  registrado como fuente: {args.vendor} · {args.license}")
    print(f"\nPacks manuales registrados: {len(reg)} ({total} audios)")
    print("Ahora ejecuta:  ./sonidos index")
    return 0


if __name__ == "__main__":
    sys.exit(main())
