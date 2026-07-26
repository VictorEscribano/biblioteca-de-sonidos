#!/usr/bin/env python3
"""Servidor local de la libreria de efectos de sonido.

Sirve la interfaz web, el indice y los audios. Implementa peticiones Range
(http.server no las soporta) porque sin ellas el navegador no puede hacer seek
en los WAV largos: los descarga enteros antes de sonar.

Endpoints propios:
  GET  /api/index          -> index.json
  POST /api/export         -> agrupa sonidos en exports/<nombre>/ por hardlink
  POST /api/reveal         -> abre una carpeta en el gestor de archivos
"""
import argparse
import json
import mimetypes
import os
import re
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
WEB = BASE / "web"
LIBRARY = BASE / "library"
INDEX = BASE / "index.json"
EXPORTS = BASE / "exports"
DEFAULT_PORT = 7777

mimetypes.add_type("audio/wav", ".wav")
mimetypes.add_type("audio/ogg", ".ogg")
mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/aiff", ".aif")
mimetypes.add_type("audio/aiff", ".aiff")

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")

# Estado de la importacion en curso, compartido entre el hilo de trabajo y
# las peticiones a /api/job.
JOB = {
    "lock": threading.Lock(),
    "running": False,
    "done": False,
    "error": None,
    "log": [],
    "added": 0,
}


def job_log(msg):
    with JOB["lock"]:
        JOB["log"].append(msg)
    print(f"[import] {msg}", flush=True)


def run_import(target, vendor, license_name, url):
    """Copia el pack a _staging/manual/ y relanza el indexado."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import add_pack

        pack = add_pack.safe_name(target.stem)
        vendor_safe = add_pack.safe_name(vendor)
        dest = BASE / "_staging" / "manual" / vendor_safe / pack
        dest.mkdir(parents=True, exist_ok=True)

        job_log(f"Importando «{pack}» de {vendor}…")
        if target.is_file():
            n = add_pack.extract_zip(target, dest)
            job_log(f"Descomprimidos {n} audios")
        else:
            n = add_pack.copy_tree(target, dest, link=True)
            job_log(f"Enlazados {n} audios")

        if not n:
            raise RuntimeError("No se encontró ningún archivo de audio dentro")

        reg = add_pack.load_registry()
        reg[f"{vendor_safe}/{pack}"] = {
            "vendor": vendor, "license": license_name, "url": url, "files": n,
        }
        add_pack.REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        add_pack.REGISTRY.write_text(
            json.dumps(reg, ensure_ascii=False, indent=2))
        job_log(f"Registrado como fuente: {vendor} · {license_name}")

        job_log("Reindexando la biblioteca (puede tardar)…")
        r = subprocess.run(
            [sys.executable, str(BASE / "tools" / "build_index.py")],
            capture_output=True, text=True, cwd=str(BASE), timeout=3600)
        if r.returncode != 0:
            raise RuntimeError(f"El indexado falló: {r.stderr[-400:]}")
        for line in r.stdout.strip().splitlines()[-3:]:
            job_log(line.strip())

        with JOB["lock"]:
            JOB["added"] = n
        job_log("Listo.")
    except Exception as e:
        with JOB["lock"]:
            JOB["error"] = str(e)
        job_log(f"ERROR: {e}")
    finally:
        with JOB["lock"]:
            JOB["running"] = False
            JOB["done"] = True


def safe_under(root, rel):
    """Resuelve rel bajo root rechazando cualquier escape del arbol."""
    target = (root / rel.lstrip("/")).resolve()
    root = root.resolve()
    if target != root and root not in target.parents:
        return None
    return target


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, fmt, *args):
        # Silencia el log por peticion: con cientos de audios es ilegible.
        pass

    # ---------- GET ----------
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/index":
            return self.send_json_file(INDEX)
        if path == "/api/job":
            with JOB["lock"]:
                return self.send_json({k: v for k, v in JOB.items()
                                       if k != "lock"})
        if path.startswith("/audio/"):
            rel = urllib.parse.unquote(path[len("/audio/"):])
            target = safe_under(LIBRARY, rel)
            if not target or not target.is_file():
                return self.send_error(404, "sonido no encontrado")
            return self.send_file_ranged(target)
        return super().do_GET()

    # ---------- POST ----------
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self.send_json({"error": "JSON inválido"}, 400)

        if path == "/api/export":
            return self.api_export(body)
        if path == "/api/reveal":
            return self.api_reveal(body)
        if path == "/api/import":
            return self.api_import(body)
        return self.send_error(404)

    def api_import(self, body):
        """Importa una libreria desde una ruta del disco y reindexa.

        Se lanza en segundo plano porque reindexar pasa ffprobe por miles de
        archivos; el cliente sigue el avance con GET /api/job.
        """
        src = (body.get("path") or "").strip()
        vendor = (body.get("vendor") or "").strip()
        if not src or not vendor:
            return self.send_json({"error": "Faltan la ruta y el proveedor"}, 400)

        target = Path(src).expanduser()
        if not target.exists():
            return self.send_json({"error": f"No existe la ruta: {target}"}, 400)
        if target.is_file() and target.suffix.lower() != ".zip":
            return self.send_json(
                {"error": "Si es un archivo debe ser un .zip"}, 400)

        with JOB["lock"]:
            if JOB["running"]:
                return self.send_json({"error": "Ya hay una importación en curso"}, 409)
            JOB.update(running=True, done=False, error=None, log=[], added=0)

        threading.Thread(target=run_import, daemon=True, args=(
            target, vendor,
            (body.get("license") or "Comercial royalty-free").strip(),
            (body.get("url") or "").strip(),
        )).start()
        return self.send_json({"ok": True})

    def api_export(self, body):
        """Agrupa los sonidos elegidos en una carpeta lista para Resolve."""
        files = body.get("files") or []
        name = body.get("name") or datetime.now().strftime("seleccion-%Y%m%d-%H%M")
        name = re.sub(r"[^\w .-]", "", name).strip() or "seleccion"
        out = EXPORTS / name
        out.mkdir(parents=True, exist_ok=True)

        ok = fail = 0
        for rel in files:
            src = safe_under(LIBRARY, rel)
            if not src or not src.is_file():
                fail += 1
                continue
            dst = out / src.name
            n = 1
            while dst.exists():
                dst = out / f"{src.stem} ({n}){src.suffix}"
                n += 1
            try:
                os.link(src, dst)      # hardlink: no duplica espacio
            except OSError:
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    fail += 1
                    continue
            ok += 1
        return self.send_json({"ok": ok, "fail": fail, "path": str(out)})

    def api_reveal(self, body):
        target = Path(body.get("path") or EXPORTS)
        if not target.exists():
            return self.send_json({"error": "no existe"}, 404)
        try:
            subprocess.Popen(["xdg-open", str(target)],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return self.send_json({"ok": True})
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)

    # ---------- helpers ----------
    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json_file(self, path):
        if not path.exists():
            return self.send_json(
                {"error": "index.json no existe todavía; ejecuta "
                          "tools/build_index.py"}, 404)
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def send_file_ranged(self, path):
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        rng = self.headers.get("Range")

        start, end = 0, size - 1
        partial = False
        if rng:
            m = RANGE_RE.match(rng.strip())
            if m:
                g1, g2 = m.group(1), m.group(2)
                if g1:
                    start = int(g1)
                    if g2:
                        end = min(int(g2), size - 1)
                elif g2:                      # sufijo: bytes=-N
                    start = max(0, size - int(g2))
                if start >= size or start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                partial = True

        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1 << 16, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return           # el navegador cambio de sonido: normal
                remaining -= len(chunk)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class Server6(Server):
    address_family = socket.AF_INET6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="sfx.localhost",
                    help="nombre a mostrar y abrir en el navegador")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if not INDEX.exists():
        print("Aviso: no hay index.json. Ejecuta antes:")
        print("  python3 tools/build_index.py\n")

    EXPORTS.mkdir(exist_ok=True)
    url = f"http://{args.host}:{args.port}/"

    # Se escucha en las dos loopback: "sfx.localhost" resuelve a ::1 antes que
    # a 127.0.0.1, asi que atendiendo solo IPv4 el navegador se come un
    # rechazo de conexion antes de reintentar.
    servers = []
    try:
        servers.append(Server(("127.0.0.1", args.port), Handler))
    except OSError as e:
        print(f"No se pudo escuchar en 127.0.0.1:{args.port} -> {e}")
    try:
        s6 = Server6(("::1", args.port), Handler)
        servers.append(s6)
    except OSError:
        pass                       # sistema sin IPv6: con IPv4 basta

    if not servers:
        print(f"El puerto {args.port} está ocupado.")
        return 1

    print(f"Biblioteca de sonidos servida en  {url}")
    print(f"  escuchando en: "
          f"{', '.join(s.server_address[0] for s in servers)}  puerto {args.port}")
    print(f"  libreria : {LIBRARY}")
    print(f"  exports  : {EXPORTS}")
    print("\nCtrl-C para parar.")

    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        print("\nParado.")
    finally:
        for s in servers:
            s.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
