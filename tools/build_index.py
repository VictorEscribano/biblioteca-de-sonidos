#!/usr/bin/env python3
"""Unifica todo lo descargado en una sola libreria indexada.

Pasos: descomprime lo que venga en zip, deduplica, extrae metadatos con
ffprobe, clasifica en las 12 categorias, enlaza por hardlink en
library/<categoria>/ y escribe index.json + CREDITS.md.

Se usa hardlink en vez de copia para no duplicar los ~20 GB en disco. Al ser
el mismo sistema de archivos cuesta cero y _staging/ se puede borrar despues
sin perder los audios.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categories import (CATEGORY_INFO, CATEGORY_ORDER, ICONS,  # noqa: E402
                        classify, extract_tags)
from thesaurus import searchable_text  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
STAGING = BASE / "_staging"
LIBRARY = BASE / "library"
INDEX = BASE / "index.json"
CREDITS = BASE / "CREDITS.md"

AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".aif", ".aiff"}

# Procedencia y licencia por carpeta de staging.
SOURCES = {
    "kenney": ("Kenney.nl", "CC0", False),
    "gamesounds": ("Sonniss GDC (espejo gamesounds.xyz)", "Sonniss GDC", False),
    "sonniss": ("Sonniss GDC", "Sonniss GDC", False),
    "freesound": ("Freesound", None, True),  # licencia real desde su sidecar
    "manual": ("Manual", None, False),       # procedencia desde el registro
}

# Packs anadidos a mano con tools/add_pack.py: _staging/manual/<vendor>/<pack>
MANUAL_REGISTRY = BASE / "_cache" / "manual_sources.json"


def load_manual_registry():
    if MANUAL_REGISTRY.exists():
        try:
            return json.loads(MANUAL_REGISTRY.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def manual_meta(path, registry):
    """Vendor y licencia de un audio bajo _staging/manual/, si aplica."""
    try:
        rel = path.relative_to(STAGING / "manual").parts
    except ValueError:
        return None
    if len(rel) < 2:
        return None
    entry = registry.get(f"{rel[0]}/{rel[1]}")
    if not entry:
        return {"vendor": rel[0], "license": "sin especificar", "url": ""}
    return entry


def unzip_all():
    """Descomprime los zips de staging una sola vez (marca con .extracted)."""
    for zp in sorted(STAGING.rglob("*.zip")):
        marker = zp.with_suffix(".extracted")
        if marker.exists():
            continue
        out = zp.with_suffix("")
        out.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zp) as z:
                members = [m for m in z.namelist()
                           if Path(m).suffix.lower() in AUDIO_EXT]
                for m in members:
                    # Conserva la estructura de carpetas: el nombre del pack /
                    # proveedor es señal para el clasificador. Se sanea contra
                    # zip-slip en vez de aplanar, que perdia archivos con el
                    # mismo nombre base en subcarpetas distintas.
                    parts = [p for p in Path(m.replace("\\", "/")).parts
                             if p not in ("", ".", "..") and not p.startswith("/")]
                    if not parts:
                        continue
                    target = out.joinpath(*parts)
                    target = Path(os.path.normpath(target))
                    if not str(target).startswith(str(out.resolve().parent)):
                        continue  # fuera del destino: descarta
                    if target.exists():
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(m) as src, open(target, "wb") as dst:
                        dst.write(src.read())
            marker.write_text("ok")
            print(f"  descomprimido {zp.name}: {len(members)} audios")
        except Exception as e:
            print(f"  ERROR descomprimiendo {zp.name}: {e}")


def fingerprint(path, size):
    """Huella barata: tamano + hash de los primeros 256 KB.

    Hashear 20 GB enteros seria lentisimo y para duplicados exactos esto basta.
    """
    h = hashlib.blake2b(digest_size=16)
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(262144))
    return h.hexdigest()


def probe(path):
    """Duracion, sample rate, canales y bitrate via ffprobe."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries",
             "format=duration,bit_rate:stream=sample_rate,channels",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30)
        d = json.loads(out.stdout or "{}")
        st = (d.get("streams") or [{}])[0]
        fm = d.get("format") or {}
        return {
            "dur": round(float(fm.get("duration") or 0), 2),
            "sr": int(st.get("sample_rate") or 0),
            "ch": int(st.get("channels") or 0),
            "br": int(fm.get("bit_rate") or 0),
        }
    except Exception:
        return {"dur": 0, "sr": 0, "ch": 0, "br": 0}


def slugify(name, maxlen=90):
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[^\w\s.,&+-]", "", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:maxlen] or "sound"


def sidecar_meta(path):
    """Lee el .json que deja el descargador de Freesound junto al audio."""
    sc = path.with_suffix(path.suffix + ".json")
    if sc.exists():
        try:
            return json.loads(sc.read_text())
        except Exception:
            return {}
    return {}


def collect():
    files = []
    for src_dir, (src_name, lic, per_file_lic) in SOURCES.items():
        root = STAGING / src_dir
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXT:
                files.append((p, src_name, lic, per_file_lic))
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--skip-unzip", action="store_true")
    args = ap.parse_args()

    if not args.skip_unzip:
        print("Descomprimiendo zips de staging...")
        unzip_all()

    print("\nRecolectando archivos de audio...")
    raw = collect()
    print(f"  {len(raw)} archivos encontrados en _staging/")

    print("\nDeduplicando (tamano + hash de cabecera)...")
    seen, uniq, dups = {}, [], 0
    for p, src, lic, pfl in raw:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size < 1024:  # descarta archivos vacios o truncados
            continue
        fp = fingerprint(p, size)
        if fp in seen:
            dups += 1
            continue
        seen[fp] = True
        uniq.append((p, src, lic, pfl, size, fp))
    print(f"  {len(uniq)} unicos, {dups} duplicados descartados")

    print(f"\nExtrayendo metadatos con ffprobe ({args.workers} hilos)...")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        metas = list(pool.map(lambda t: probe(t[0]), uniq))
    print(f"  {sum(1 for m in metas if m['dur'] > 0)} con duracion valida")

    print("\nClasificando y enlazando en library/...")
    for cid in CATEGORY_ORDER:
        (LIBRARY / cid).mkdir(parents=True, exist_ok=True)

    manual_reg = load_manual_registry()
    if manual_reg:
        print(f"  {len(manual_reg)} packs manuales registrados")
    entries, used_names, linked, link_fail = [], set(), 0, 0
    for (p, src, lic, pfl, size, fp), meta in zip(uniq, metas):
        rel_parts = p.relative_to(STAGING).parts
        folder = rel_parts[-2] if len(rel_parts) > 1 else ""
        stem = p.stem

        sc = sidecar_meta(p) if pfl else {}
        tag_src = " ".join(sc.get("tags", [])) if sc else ""
        cid, label, emoji = classify(folder, stem + " " + tag_src)

        tags = sc.get("tags") or extract_tags(folder, stem)
        license_name = sc.get("license") or lic or "desconocida"
        author = sc.get("author") or ""

        mm = manual_meta(p, manual_reg)
        if mm:
            src = mm["vendor"]
            license_name = mm["license"]

        # Nombre final unico dentro de su categoria.
        cand = slugify(stem) + p.suffix.lower()
        n = 1
        while (cid, cand.lower()) in used_names:
            cand = f"{slugify(stem)} ({n}){p.suffix.lower()}"
            n += 1
        used_names.add((cid, cand.lower()))

        dest = LIBRARY / cid / cand
        try:
            if not dest.exists():
                os.link(p, dest)
            linked += 1
        except OSError:
            try:
                if not dest.exists():
                    import shutil
                    shutil.copy2(p, dest)
                linked += 1
            except Exception:
                link_fail += 1
                continue

        entries.append({
            "id": fp,
            "name": stem,
            "file": f"{cid}/{cand}",
            "cat": cid,
            "tags": tags,
            # Texto enriquecido con el tesauro ES-EN y las abreviaturas UCS.
            # El pack va como literal: buscable, pero sin activar conceptos.
            "txt": searchable_text(
                f"{stem} {' '.join(tags)} {CATEGORY_INFO[cid][0]}",
                literal=folder),
            "dur": meta["dur"],
            "sr": meta["sr"],
            "ch": meta["ch"],
            "size": size,
            "src": src,
            "lic": license_name,
            "author": author,
            "url": sc.get("url", ""),
            "pack": folder,
        })

    print(f"  {linked} enlazados, {link_fail} fallidos")

    entries.sort(key=lambda e: (e["cat"], e["name"].lower()))
    cats = [{"id": cid, "label": CATEGORY_INFO[cid][0],
             "icon": ICONS.get(cid, "layers"),
             "count": sum(1 for e in entries if e["cat"] == cid)}
            for cid in CATEGORY_ORDER]

    # Fuentes: cada proveedor es su propia seccion en la barra lateral, para
    # poder ir directo al material de un estudio concreto.
    src_count = {}
    for e in entries:
        src_count[e["src"]] = src_count.get(e["src"], 0) + 1
    sources = [{"id": s, "label": s, "count": n}
               for s, n in sorted(src_count.items(), key=lambda x: -x[1])]

    INDEX.write_text(json.dumps(
        {"categories": cats, "sources": sources, "sounds": entries,
         "total": len(entries),
         "bytes": sum(e["size"] for e in entries),
         "root": str(LIBRARY)},
        ensure_ascii=False))
    print(f"\nindex.json escrito: {len(entries)} sonidos")

    write_credits(entries)

    print("\nResumen por categoria:")
    mx = max((c["count"] for c in cats), default=1) or 1
    for c in cats:
        bar = "#" * int(40 * c["count"] / mx)
        # El emoji sale de CATEGORY_INFO, no del dict de salida: ese ya solo
        # lleva el id del icono SVG que usa la interfaz.
        emoji = CATEGORY_INFO[c["id"]][1]
        print(f"  {emoji} {c['label']:26s} {c['count']:5d}  {bar}")

    if sources:
        print("\nPor fuente:")
        for s in sources:
            print(f"  {s['count']:6d}  {s['label']}")

    total_gb = sum(e["size"] for e in entries) / 1024**3
    total_h = sum(e["dur"] for e in entries) / 3600
    print(f"\nTOTAL: {len(entries)} sonidos, {total_gb:.2f} GB, "
          f"{total_h:.1f} horas de audio")
    return 0


def write_credits(entries):
    """CREDITS.md solo con lo que realmente exige atribucion (CC-BY)."""
    need = [e for e in entries if "attribution" in e["lic"].lower()
            and "noncommercial" not in e["lic"].lower()]
    lines = [
        "# Créditos y licencias",
        "",
        "Generado automáticamente por `tools/build_index.py`.",
        "",
        "## Fuentes sin atribución obligatoria",
        "",
        "- **Sonniss GDC Game Audio Bundle** — royalty-free, uso comercial "
        "ilimitado, sin atribución. (El uso para entrenar modelos de IA está "
        "expresamente prohibido por su licencia.)",
        "- **Kenney.nl** — CC0 / dominio público.",
        "- **Freesound CC0** — dominio público.",
        "",
    ]
    if need:
        lines += [
            f"## Atribución obligatoria (CC-BY) — {len(need)} sonidos",
            "",
            "Si usas alguno de estos sonidos, incluye su línea de crédito:",
            "",
        ]
        for e in sorted(need, key=lambda x: x["name"].lower()):
            author = e["author"] or "autor desconocido"
            url = f" — {e['url']}" if e["url"] else ""
            lines.append(f"- «{e['name']}» por **{author}** ({e['lic']}){url}")
    else:
        lines += ["## Atribución obligatoria (CC-BY)", "",
                  "_Ninguno todavía._", ""]
    CREDITS.write_text("\n".join(lines) + "\n")
    print(f"CREDITS.md escrito: {len(need)} sonidos requieren atribución")


if __name__ == "__main__":
    sys.exit(main())
