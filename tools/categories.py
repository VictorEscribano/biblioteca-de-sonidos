#!/usr/bin/env python3
"""Taxonomia de la libreria y clasificador por palabras clave.

Se clasifica sobre la ruta completa (carpeta de proveedor + nombre de archivo)
porque el nombre suele seguir la convencion UCS y la carpeta describe el pack,
p.ej. "Airborne Sound - Eclectic Whooshes/Whoosh,Sound Design,Blast.wav".
"""
import re
import unicodedata

# id -> (etiqueta, emoji, keywords). El orden importa: se evalua por puntuacion,
# y a igualdad gana la categoria mas especifica (las de arriba).
CATEGORIES = [
    ("armas", "Armas y Combate", "🎯", [
        "gun", "gunshot", "weapon", "rifle", "pistol", "shotgun", "revolver",
        "reload", "bullet", "ricochet", "explosion", "explo", "grenade",
        "sword", "blade", "knife", "arrow", "bow", "combat", "battle", "war",
        "gore", "stab", "slash", "melee", "firearm", "ammo", "cannon",
        "artillery", "machinegun", "silencer", "holster",
    ]),
    ("vehiculos", "Vehículos y Motores", "🚗", [
        "car", "engine", "vehicle", "vehmoto", "motor", "truck", "train",
        "plane", "aircraft", "helicopter", "jet", "bike", "motorcycle",
        "moto", "scooter", "drive", "driving", "brake", "tire", "tyre",
        "exhaust", "rev", "idle", "gearbox", "traffic", "bus", "tram",
        "subway", "boat", "ship", "tractor", "forklift",
        # marcas presentes en los packs de coches de Sonniss
        "volvo", "ferrari", "porsche", "bmw", "ford", "mercedes", "yamaha",
        "audi", "toyota", "honda", "nissan", "dodge", "chevrolet", "harley",
    ]),
    ("agua", "Agua y Líquidos", "💧", [
        "water", "splash", "liquid", "bubble", "drip", "pour", "underwater",
        "ocean", "wave", "river", "stream", "swim", "fountain", "faucet",
        "boil", "gurgle", "sludge", "slime", "mud", "wet", "hydro", "rain",
        "puddle", "waterfall", "sink", "shower", "toilet", "flush",
    ]),
    ("animales", "Animales y Criaturas", "🐾", [
        "animal", "creature", "monster", "beast", "dragon", "dog", "bark",
        "cat", "meow", "bird", "chirp", "horse", "insect", "bug", "growl",
        "roar", "snarl", "hiss", "cow", "pig", "sheep", "chicken", "wolf",
        "lion", "bear", "frog", "cricket", "bee", "fly", "seagull", "owl",
        "zombie", "goblin", "orc", "alienvoice", "mutant",
        "barking", "squawk", "shriek", "hawk", "deer", "vocalization",
        "chitter", "purr", "neigh", "bleat", "howl", "whinny", "goat",
        "duck", "goose", "crow", "raven", "rodent", "rat", "mouse squeak",
    ]),
    ("magia_scifi", "Magia y Ciencia Ficción", "✨", [
        "magic", "spell", "scifi", "sci-fi", "sci fi", "laser", "energy",
        "plasma", "robot", "droid", "alien", "teleport", "portal", "force",
        "fantasy", "mystical", "arcane", "enchant", "power up", "powerup",
        "powerdown", "beam", "shield", "warp", "hologram", "cyber", "mech",
        "spaceship", "spacecraft", "futuristic", "sparkle", "shimmer",
        "dsgn", "sound design", "sounddesign", "sfx design",
    ]),
    ("cinematico", "Cinemático y Tensión", "🎬", [
        "cinematic", "trailer", "braam", "stinger", "suspense", "tension",
        "horror", "scary", "dark", "epic", "drone", "dsgndron", "sub drop",
        "subdrop", "boom", "hit trailer", "orchestral hit", "dread",
        "ominous", "eerie", "creepy", "tense", "build up", "buildup",
        "impact cinematic", "downer", "brass hit",
    ]),
    ("whoosh", "Whooshes y Transiciones", "🌀", [
        "whoosh", "woosh", "swoosh", "swish", "transition", "riser", "sweep",
        "pass by", "passby", "flyby", "fly by", "whip", "whizz", "whoop",
        "swipe", "descend", "ascend", "turbulence", "doppler", "bypass",
        "acceleration", "sweeper",
    ]),
    ("impactos", "Impactos y Golpes", "💥", [
        "impact", "hit", "punch", "crash", "smash", "slam", "thud", "bang",
        "whack", "break", "breaking", "destruction", "destroy", "collision",
        "crush", "shatter", "debris", "rubble", "knock", "bash", "stomp",
        "drop", "thump", "clang", "dropping", "dropped", "slap", "bounce",
        "whump", "clonk", "wallop", "strike", "blow",
    ]),
    ("interfaz", "Interfaz y Tecnología", "🖱️", [
        "ui", "uiglitch", "interface", "click", "beep", "button", "menu",
        "notification", "digital", "glitch", "computer", "data", "hud",
        "error", "select", "confirm", "cancel", "toggle", "switch ui",
        "blip", "bleep", "keyboard", "typing", "mouse", "phone", "ringtone",
        "alarm", "alert", "scan", "load", "boot", "electric", "electronic",
        "static", "modem", "radio", "signal", "circuit",
    ]),
    ("humano", "Humano y Voz", "🗣️", [
        "voice", "vocal", "human", "crowd", "breath", "laugh", "scream",
        "cough", "whisper", "speech", "mouth", "grunt", "effort", "shout",
        "cheer", "applause", "clap", "talk", "chatter", "sigh", "cry",
        "baby", "child", "man", "woman", "male", "female", "announcer",
        "voiceover", "narration", "singing", "hum", "whistle", "kiss",
    ]),
    ("ambiente", "Ambientes y Naturaleza", "🌿", [
        "ambience", "ambient", "amb", "atmos", "atmosphere", "room tone",
        "roomtone", "wind", "forest", "city", "nature", "weather", "thunder",
        "storm", "ambisonic", "field recording", "background", "outdoor",
        "indoor", "park", "street", "market", "restaurant", "office",
        "airport", "station", "beach", "jungle", "desert", "mountain",
        "cave", "night", "morning", "fire", "campfire", "leaves", "snow",
        "ice", "ext", "int",
    ]),
    ("foley", "Foley y Objetos", "🎒", [
        "foley", "footstep", "footsteps", "walk", "run", "door", "cloth",
        "clothing", "fabric", "paper", "key", "keys", "handling", "drawer",
        "switch", "wood", "metal", "glass", "plastic", "box", "chair",
        "table", "book", "bag", "zip", "zipper", "coin", "bottle", "can",
        "cup", "plate", "cutlery", "rope", "chain", "lock", "hinge",
        "creak", "rustle", "scrape", "friction", "grab", "put down",
        "pickup", "pick up", "tool", "hammer", "saw", "machine",
        # variantes vistas escaparse al cajon de sastre
        "leather", "scrunch", "jacket", "cardboard", "chips", "poker",
        "domino", "shelf", "container", "brush", "grit", "scatter",
        "crumple", "crinkle", "velcro", "button press", "latch", "handle",
        "cutting", "chop", "snap", "rip", "tear", "squeak", "rattle",
        "jingle", "clatter", "shuffle", "sliding", "swivel", "typewriter",
    ]),
]

FALLBACK = ("varios", "Varios", "📦")

# Mapa id -> (etiqueta, emoji) incluyendo el cajon de sastre.
# El emoji se usa solo en la salida de terminal; la interfaz web usa los
# iconos SVG de ICONS, que comparten trazo y rejilla para verse coherentes.
CATEGORY_INFO = {cid: (label, emoji) for cid, label, emoji, _ in CATEGORIES}
CATEGORY_INFO[FALLBACK[0]] = (FALLBACK[1], FALLBACK[2])

ICONS = {
    "armas": "target",
    "vehiculos": "car",
    "agua": "droplet",
    "animales": "paw",
    "magia_scifi": "sparkles",
    "cinematico": "film",
    "whoosh": "wind",
    "impactos": "impact",
    "interfaz": "cursor",
    "humano": "mic",
    "ambiente": "tree",
    "foley": "box",
    "varios": "layers",
}

CATEGORY_ORDER = [c[0] for c in CATEGORIES] + [FALLBACK[0]]

# Emparejado por tramos segun longitud de la keyword:
#   >=5 letras -> subcadena libre, para pillar flexiones y compuestos
#                 ("rifle" en "AssaultRifle", "vocal" en "vocalizations").
#   <=4 letras -> limite de palabra estricto, porque si no "wind" casa con
#                 "window", "rain" con "train" y "amb" con "ambulance".
# Las keywords con espacio siempre van con limite: ya son especificas.
_COMPILED = []
for cid, label, emoji, kws in CATEGORIES:
    pats = []
    for kw in kws:
        if len(kw) >= 5 and " " not in kw:
            rx = re.compile(re.escape(kw))
        else:
            rx = re.compile(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])")
        pats.append((kw, rx))
    _COMPILED.append((cid, pats))


def normalize(text):
    """Minusculas sin acentos, separadores unificados a espacio."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    return re.sub(r"[_\-,./\\()\[\]]+", " ", text)


def classify(*parts):
    """Clasifica a partir de ruta/nombre/tags. Devuelve (id, etiqueta, emoji).

    Los `parts` van de menos a mas especifico (carpeta del pack primero, nombre
    de archivo al final). El ultimo pesa el triple: la carpeta del proveedor
    describe el pack entero y contamina archivos concretos, p.ej. un
    "Little Plastic Container.wav" dentro de un pack con "water" en el nombre.
    """
    fields = [normalize(p) for p in parts if p]
    if not fields:
        return FALLBACK
    weights = [1] * len(fields)
    weights[-1] = 3

    best, best_score = None, 0
    for cid, pats in _COMPILED:
        score = 0
        for kw, pat in pats:
            # Las keywords de varias palabras son mas especificas.
            base = 2 + kw.count(" ")
            for hay, w in zip(fields, weights):
                if pat.search(hay):
                    score += base * w
        if score > best_score:
            best, best_score = cid, score
    if best is None:
        return FALLBACK
    label, emoji = CATEGORY_INFO[best]
    return best, label, emoji


def extract_tags(*parts, limit=14):
    """Saca tags legibles de la ruta/nombre (la convencion UCS usa comas)."""
    stop = {
        "wav", "mp3", "ogg", "flac", "aif", "aiff", "the", "and", "for",
        "com", "sonniss", "gdc", "game", "audio", "bundle", "sound", "sounds",
        "pack", "library", "vol", "www", "kenney", "freesound", "of", "a",
    }
    words, seen = [], set()
    for p in parts:
        if not p:
            continue
        for w in re.split(r"[\s_\-,./\\()\[\]]+", normalize(p)):
            w = w.strip()
            if len(w) < 3 or w in stop or w.isdigit() or w in seen:
                continue
            seen.add(w)
            words.append(w)
            if len(words) >= limit:
                return words
    return words
