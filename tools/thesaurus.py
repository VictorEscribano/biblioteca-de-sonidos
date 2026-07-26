#!/usr/bin/env python3
"""Tesauro ES-EN de dominio SFX y expansion de abreviaturas UCS.

La libreria esta integramente en ingles y con nomenclatura UCS abreviada
("FEETHors_Draft Horse Walk", "VEHWagn_Wood Cart"), asi que buscar "caballo"
o incluso "horse" se queda corto. La estrategia es expandir los DOCUMENTOS en
el indexado, no las consultas: al sonido de caballo se le anaden todos los
sinonimos del concepto en ambos idiomas, de modo que "caballo", "galope" y
"relincho" pasan a estar literalmente en su texto de busqueda.

Asi la consulta en tiempo real sigue siendo una comparacion de tokens barata.
"""
import re
import unicodedata

# Cada grupo son terminos intercambiables ES+EN. Si un sonido casa con
# cualquiera de ellos, se le anaden todos los demas.
CONCEPTS = [
    # --- animales ---
    # "snort"/"resoplido" quedan fuera a proposito: los cerdos tambien
    # resoplan y arrastraban sonidos de cerdo a las busquedas de caballo.
    ["horse", "caballo", "equino", "equine", "pony", "poni", "yegua", "mare",
     "stallion", "semental", "hoof", "hooves", "casco", "cascos", "gallop",
     "galope", "galopar", "trot", "trote", "neigh", "relincho", "whinny",
     "saddle", "montura", "hors"],
    ["dog", "perro", "can", "bark", "ladrido", "ladrar", "growl", "gruñido",
     "puppy", "cachorro", "whine", "gemido", "canine", "canino"],
    ["cat", "gato", "meow", "maullido", "maullar", "purr", "ronroneo",
     "feline", "felino", "hiss", "bufido"],
    ["bird", "pajaro", "ave", "chirp", "piar", "trino", "tweet", "sing",
     "canto", "wing", "ala", "aleteo", "flap", "seagull", "gaviota", "owl",
     "buho", "lechuza", "crow", "cuervo", "raven", "hawk", "halcon",
     "eagle", "aguila", "squawk", "graznido", "pigeon", "paloma"],
    ["cow", "vaca", "moo", "mugido", "cattle", "ganado", "bull", "toro"],
    ["pig", "cerdo", "puerco", "oink", "gruñir", "boar", "jabali"],
    ["sheep", "oveja", "bleat", "balido", "goat", "cabra", "lamb", "cordero"],
    ["chicken", "gallina", "pollo", "rooster", "gallo", "cluck", "cacareo"],
    ["wolf", "lobo", "howl", "aullido", "aullar"],
    ["bear", "oso", "roar", "rugido", "rugir"],
    ["lion", "leon", "tiger", "tigre", "big cat", "felino grande"],
    ["insect", "insecto", "bug", "bicho", "bee", "abeja", "buzz", "zumbido",
     "fly", "mosca", "cricket", "grillo", "mosquito", "wasp", "avispa"],
    ["frog", "rana", "sapo", "toad", "croak", "croar"],
    # "mouse"/"raton" van solo en el concepto de teclado: en una libreria de
    # SFX el raton de ordenador aparece muchisimo mas que el roedor.
    ["rat", "rata", "rodent", "roedor", "squeak", "chillido"],
    ["creature", "criatura", "monster", "monstruo", "beast", "bestia",
     "dragon", "zombie", "zombi", "goblin", "orc", "orco", "alien",
     "mutant", "mutante", "crea", "demon", "demonio"],

    # --- humano ---
    ["human", "humano", "person", "persona", "hmn", "voice", "voz", "vocal"],
    ["footstep", "footsteps", "paso", "pasos", "pisada", "pisadas", "walk",
     "andar", "caminar", "run", "correr", "carrera", "feet", "pie", "pies",
     "step", "boot", "bota", "botas", "shoe", "zapato", "sneaker"],
    ["laugh", "risa", "reir", "carcajada", "giggle", "chuckle", "laughter"],
    ["scream", "grito", "gritar", "shout", "yell", "chillar", "shriek"],
    ["breath", "respiracion", "respirar", "aliento", "breathe", "gasp",
     "jadeo", "pant", "sigh", "suspiro"],
    ["cough", "tos", "toser", "sneeze", "estornudo", "throat", "garganta"],
    ["crowd", "multitud", "gentio", "publico", "audience", "cheer", "vitor",
     "applause", "aplauso", "aplausos", "clap", "palmada", "chatter",
     "murmullo", "people", "gente"],
    ["whisper", "susurro", "susurrar", "murmur", "murmurar"],
    ["cry", "llanto", "llorar", "sob", "sollozo", "weep"],
    ["baby", "bebe", "child", "nino", "niño", "kid", "infant"],
    ["grunt", "gruñido", "effort", "esfuerzo", "exertion"],

    # --- impactos ---
    ["impact", "impacto", "hit", "golpe", "golpear", "strike", "impt"],
    ["punch", "puñetazo", "puñetazos", "slap", "bofetada", "smack", "whack"],
    ["crash", "choque", "estrellar", "collision", "colision", "wreck"],
    ["smash", "destrozar", "shatter", "romper", "break", "rotura",
     "destruction", "destruccion", "destroy", "destruir", "crush",
     "aplastar", "debris", "escombros", "rubble"],
    ["slam", "portazo", "golpazo", "bang", "estruendo", "thud", "golpe seco",
     "thump", "clang", "clonk"],
    ["drop", "caida", "caer", "soltar", "fall", "tirar", "dropping"],
    ["bounce", "rebote", "rebotar", "ricochet", "rebound"],

    # --- armas ---
    ["gun", "pistola", "arma", "gunshot", "disparo", "shot", "tiro",
     "firearm", "weapon", "weap", "rifle", "fusil", "shotgun", "escopeta",
     "revolver", "handgun", "machinegun", "ametralladora", "pistol"],
    ["reload", "recargar", "recarga", "ammo", "municion", "bullet", "bala",
     "magazine", "cargador", "cartridge", "casquillo", "shell"],
    ["explosion", "explosion", "explosivo", "explotar", "blast", "estallido",
     "boom", "detonation", "detonacion", "grenade", "granada", "bomb",
     "bomba", "tnt", "explo"],
    ["sword", "espada", "blade", "hoja", "filo", "knife", "cuchillo",
     "dagger", "daga", "slash", "tajo", "stab", "apuñalar", "melee",
     "cuerpo a cuerpo", "unsheath", "desenvainar"],
    ["arrow", "flecha", "bow", "arco", "crossbow", "ballesta", "archery"],
    ["combat", "combate", "battle", "batalla", "war", "guerra", "fight",
     "pelea", "lucha", "cannon", "cañon", "artillery", "artilleria"],
    ["armor", "armadura", "shield", "escudo", "chainmail", "cota de malla"],

    # --- vehiculos ---
    ["car", "coche", "auto", "automovil", "carro", "vehicle", "vehiculo",
     "veh", "sedan", "suv"],
    ["engine", "motor", "rev", "acelerar", "acelerador", "idle", "ralenti",
     "start", "arranque", "exhaust", "escape", "turbo"],
    ["brake", "freno", "frenar", "frenada", "tire", "tyre", "neumatico",
     "rueda", "wheel", "skid", "derrape", "screech", "chirrido"],
    ["truck", "camion", "lorry", "van", "furgoneta", "bus", "autobus"],
    ["motorcycle", "moto", "motocicleta", "bike", "bicicleta", "bicycle",
     "scooter", "vespa", "vehmoto", "harley"],
    ["train", "tren", "railway", "ferrocarril", "subway", "metro", "tram",
     "tranvia", "locomotive", "locomotora", "rail", "via"],
    ["plane", "avion", "aircraft", "aeronave", "jet", "reactor", "helicopter",
     "helicoptero", "propeller", "helice", "flight", "vuelo", "airplane"],
    ["boat", "barco", "bote", "ship", "buque", "nave", "sail", "vela",
     "motorboat", "lancha"],
    ["traffic", "trafico", "horn", "claxon", "bocina", "siren", "sirena"],

    # --- agua ---
    ["water", "agua", "liquid", "liquido", "wet", "mojado", "hydro"],
    ["splash", "chapoteo", "salpicadura", "salpicar", "splashing"],
    ["rain", "lluvia", "llover", "downpour", "aguacero", "drizzle",
     "llovizna", "storm", "tormenta", "thunder", "trueno"],
    ["ocean", "oceano", "mar", "sea", "wave", "ola", "olas", "surf",
     "beach", "playa", "shore", "orilla"],
    ["river", "rio", "stream", "arroyo", "creek", "waterfall", "cascata",
     "cascada", "catarata", "brook"],
    ["bubble", "burbuja", "burbujas", "gurgle", "borboteo", "boil", "hervir",
     "fizz", "efervescencia"],
    # "tap" fuera: como verbo de pulsar es mucho mas frecuente que como grifo.
    ["drip", "goteo", "gotear", "gota", "pour", "verter", "faucet", "grifo",
     "sink", "fregadero", "lavabo", "shower", "ducha", "toilet",
     "inodoro", "flush", "cisterna"],
    ["underwater", "submarino", "bajo el agua", "swim", "nadar", "dive",
     "buceo", "zambullida"],
    ["mud", "barro", "lodo", "slime", "limo", "baba", "sludge", "squelch"],

    # --- ambiente ---
    ["ambience", "ambiente", "ambiental", "atmosphere", "atmosfera", "amb",
     "atmos", "background", "fondo", "room tone", "tono de sala",
     "roomtone", "ambisonic"],
    ["wind", "viento", "brisa", "breeze", "gust", "rafaga", "gale"],
    ["forest", "bosque", "jungle", "selva", "tree", "arbol", "arboles",
     "leaves", "hojas", "foliage", "nature", "naturaleza", "woods"],
    ["city", "ciudad", "urban", "urbano", "street", "calle", "downtown",
     "traffic ambience", "town", "pueblo"],
    ["fire", "fuego", "llama", "flame", "campfire", "hoguera", "fogata",
     "burn", "quemar", "arder", "crackle", "crepitar", "bonfire"],
    ["snow", "nieve", "ice", "hielo", "frozen", "helado", "winter",
     "invierno", "freeze", "congelar"],
    ["cave", "cueva", "caverna", "tunnel", "tunel", "echo", "eco",
     "reverb", "reverberacion"],
    ["office", "oficina", "restaurant", "restaurante", "bar", "cafe",
     "market", "mercado", "shop", "tienda", "airport", "aeropuerto",
     "station", "estacion", "mall", "supermarket"],
    ["night", "noche", "nocturno", "morning", "mañana", "dawn", "amanecer",
     "evening", "atardecer", "dusk"],
    ["desert", "desierto", "mountain", "montaña", "field", "campo",
     "farm", "granja", "countryside", "rural"],

    # --- foley ---
    ["door", "puerta", "hinge", "bisagra", "creak", "crujido", "crujir",
     "knock", "llamar", "tocar", "lock", "cerradura", "latch", "pestillo",
     "handle", "manilla", "pomo"],
    ["paper", "papel", "page", "pagina", "book", "libro", "cardboard",
     "carton", "envelope", "sobre", "newspaper", "periodico", "rustle",
     "crujido de papel", "crumple", "arrugar", "tear", "rasgar", "rip"],
    ["cloth", "tela", "ropa", "clothing", "fabric", "tejido", "leather",
     "cuero", "jacket", "chaqueta", "zipper", "cremallera", "zip",
     "velcro", "scrunch", "swish"],
    # sin "plate" ni "dish": "plate" casa con placas metalicas (impactPlate)
    # y arrastraba impactos de metal a las busquedas de cristal.
    ["glass", "cristal", "vidrio", "bottle", "botella", "cup", "vaso",
     "taza", "plato", "ceramic", "ceramica", "clink", "glas"],
    ["metal", "metal", "metalico", "steel", "acero", "iron", "hierro",
     "chain", "cadena", "rattle", "traqueteo", "clank", "metl"],
    ["wood", "madera", "wooden", "plank", "tabla", "timber", "log", "tronco"],
    ["plastic", "plastico", "container", "recipiente", "envase", "box",
     "caja", "bag", "bolsa", "package", "paquete"],
    ["key", "llave", "llaves", "keys", "coin", "moneda", "monedas",
     "jingle", "tintineo", "change", "calderilla"],
    ["switch", "interruptor", "toggle", "lever", "palanca", "button press",
     "boton", "click mecanico"],
    ["tool", "herramienta", "hammer", "martillo", "saw", "sierra", "drill",
     "taladro", "screw", "tornillo", "nail", "clavo", "wrench", "llave inglesa"],
    ["furniture", "mueble", "chair", "silla", "table", "mesa", "drawer",
     "cajon", "desk", "escritorio", "shelf", "estante", "balda"],
    ["food", "comida", "eat", "comer", "chew", "masticar", "bite",
     "mordisco", "cook", "cocinar", "kitchen", "cocina", "cutlery",
     "cubiertos", "chop", "cortar", "sizzle", "chisporroteo"],
    ["foley", "foley", "handling", "manipular", "manipulacion", "grab",
     "agarrar", "pickup", "coger", "put down", "dejar", "set down"],

    # --- interfaz ---
    ["ui", "interfaz", "interface", "hud", "menu", "gui"],
    ["click", "clic", "pulsar", "tap", "press", "pulsacion", "button",
     "boton", "select", "seleccionar", "confirm", "confirmar", "cancel",
     "cancelar", "back", "atras"],
    ["beep", "pitido", "pip", "bleep", "blip", "tone", "tono", "chime",
     "campanilla", "ding"],
    ["notification", "notificacion", "aviso", "alert", "alerta", "alarm",
     "alarma", "warning", "advertencia", "error", "fallo", "success",
     "exito", "message", "mensaje"],
    ["digital", "digital", "electronic", "electronico", "computer",
     "ordenador", "computadora", "data", "datos", "tech", "tecnologia",
     "circuit", "circuito", "electric", "electrico"],
    ["glitch", "glitch", "fallo digital", "static", "estatica", "noise",
     "ruido", "distortion", "distorsion", "corrupt", "interference",
     "interferencia"],
    ["keyboard", "teclado", "typing", "teclear", "escribir", "mouse",
     "raton", "key press", "tecla"],
    ["phone", "telefono", "movil", "ringtone", "tono de llamada", "ring",
     "timbre", "dial", "call", "llamada", "vibrate", "vibracion"],
    # sin "boot" ni "arranque": chocaban con botas (pasos) y con motores.
    ["scan", "escaneo", "escanear", "load", "cargar", "process", "procesar",
     "upload", "download", "descarga", "startup", "shutdown"],
    ["radio", "radio", "signal", "señal", "transmission", "transmision",
     "modem", "morse", "walkie", "broadcast"],

    # --- whoosh ---
    ["whoosh", "woosh", "swoosh", "silbido", "zumbido de paso", "swish",
     "whizz", "whsh", "whip", "latigazo", "air movement"],
    ["transition", "transicion", "sweep", "barrido", "riser", "subida",
     "ascenso", "buildup", "downer", "bajada", "sweeper"],
    ["passby", "pass by", "paso", "flyby", "fly by", "sobrevuelo",
     "doppler", "acercamiento", "approach", "bypass"],

    # --- cinematico ---
    ["cinematic", "cinematico", "cine", "trailer", "epic", "epico",
     "dramatic", "dramatico", "film", "pelicula"],
    ["braam", "stinger", "golpe musical", "hit trailer", "orchestral hit",
     "brass hit", "stngr"],
    ["drone", "dron", "zumbido grave", "pad", "textura", "texture",
     "atmosphere dark", "dsgndron"],
    ["suspense", "suspense", "tension", "tenso", "tense", "dread",
     "inquietud", "ominous", "amenazante", "eerie", "inquietante",
     "creepy", "escalofriante", "horror", "terror", "scary", "miedo",
     "dark", "oscuro", "siniestro"],
    ["sub drop", "subdrop", "sub", "subgrave", "low end", "graves",
     "rumble", "retumbo", "retumbar"],

    # --- magia y scifi ---
    ["magic", "magia", "magico", "spell", "hechizo", "conjuro", "wizard",
     "mago", "enchant", "encantamiento", "arcane", "arcano", "mystical",
     "mistico", "fantasy", "fantasia", "potion", "pocion", "rune", "runa"],
    ["scifi", "sci-fi", "ciencia ficcion", "futuristic", "futurista",
     "cyber", "ciber", "cyberpunk", "space", "espacio", "spaceship",
     "nave espacial", "spacecraft", "starship"],
    ["laser", "laser", "beam", "rayo", "blaster", "phaser", "plasma",
     "energy", "energia", "charge", "carga", "zap"],
    ["robot", "robot", "robotico", "droid", "androide", "mech", "mecha",
     "servo", "machine", "maquina", "automaton", "automata"],
    ["teleport", "teletransporte", "portal", "warp", "dimension",
     "hologram", "holograma", "force field", "campo de fuerza", "shield"],
    ["powerup", "power up", "potenciador", "mejora", "levelup", "level up",
     "subir de nivel", "powerdown", "power down", "achievement", "logro",
     "coin", "reward", "recompensa", "win", "ganar", "lose", "perder"],
    ["sparkle", "brillo", "destello", "shimmer", "centelleo", "twinkle",
     "glitter", "magic sparkle"],

    # --- musical ---
    ["music", "musica", "musical", "melody", "melodia", "tune", "jingle",
     "loop", "bucle", "track", "pista", "song", "cancion"],
    # sin "caja": como envase es muchisimo mas comun que como tambor.
    ["drum", "tambor", "bateria", "percussion", "percusion", "beat",
     "ritmo", "kick", "bombo", "snare", "hihat", "cymbal", "platillo"],
    ["piano", "piano", "guitar", "guitarra", "violin", "violin", "string",
     "cuerda", "brass", "metales", "horn section", "synth", "sintetizador",
     "bass", "bajo", "organ", "organo", "bell", "campana"],
]

# Prefijos de la nomenclatura UCS (Universal Category System) que aparecen
# pegados al resto del nombre: "FEETHors", "VEHWagn", "DSGNStngr", "CREAHmn".
UCS_PREFIXES = {
    "amb": "ambience", "ambi": "ambience", "air": "air", "alrm": "alarm",
    "anml": "animal", "bell": "bell", "brth": "breath", "bull": "bullet",
    "cart": "cartoon", "chem": "chemical", "clth": "cloth", "comp": "computer",
    "crea": "creature", "crsh": "crash", "dest": "destruction",
    "dgtl": "digital", "door": "door", "dsgn": "design", "elec": "electricity",
    "expl": "explosion", "fght": "fight", "feet": "footsteps",
    "fire": "fire", "foly": "foley", "food": "food", "gore": "gore",
    "gun": "gun", "glas": "glass", "horn": "horn", "hors": "horse",
    "hmn": "human", "ice": "ice", "impt": "impact", "lasr": "laser",
    "liqd": "liquid", "mach": "machine", "magc": "magic", "metl": "metal",
    "mtor": "motor", "movt": "movement", "musc": "music", "papr": "paper",
    "plas": "plastic", "rain": "rain", "robt": "robot", "rock": "rock",
    "scif": "scifi", "sprt": "sport", "stng": "stinger", "stngr": "stinger",
    "swsh": "whoosh", "tool": "tool", "toon": "cartoon", "trns": "transition",
    "ui": "interface", "vehc": "vehicle", "veh": "vehicle",
    "vox": "voice", "watr": "water", "weap": "weapon", "whsh": "whoosh",
    "wind": "wind", "wood": "wood", "wagn": "wagon", "bird": "bird",
    "dron": "drone", "gltch": "glitch", "sci": "scifi",
}


def strip_accents(text):
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize(text):
    """Minusculas, sin acentos, separadores a espacio."""
    return re.sub(r"[^a-z0-9ñ]+", " ", strip_accents(text.lower())).strip()


def split_compounds(token):
    """Separa camelCase y prefijos UCS pegados: FEETHors -> feet hors."""
    out = []
    # camelCase / PascalCase antes de bajar a minusculas se pierde, asi que
    # esta funcion recibe el token ORIGINAL sin normalizar.
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", token)
    for p in parts:
        p = p.lower()
        out.append(p)
        # prefijo UCS pegado a mas texto: "feethors"
        for pref, full in UCS_PREFIXES.items():
            if p.startswith(pref) and len(p) > len(pref):
                out.append(pref)
                out.append(p[len(pref):])
                break
    return out


# Indice invertido termino -> indices de concepto, construido una sola vez.
_TERM2CONCEPTS = {}
for i, group in enumerate(CONCEPTS):
    for term in group:
        _TERM2CONCEPTS.setdefault(normalize(term), set()).add(i)


def expand(text):
    """Devuelve el conjunto de terminos extra que enriquecen este texto.

    Casa tanto palabras sueltas como bigramas ("power up", "sub drop") y
    prefijos UCS, y devuelve todos los sinonimos de los conceptos activados.
    """
    raw_tokens = re.findall(r"[A-Za-z0-9ñÑ]+", text)
    tokens = set()
    for t in raw_tokens:
        tokens.update(split_compounds(t))
    tokens.update(normalize(text).split())

    # bigramas, para conceptos de dos palabras
    flat = normalize(text).split()
    bigrams = {f"{a} {b}" for a, b in zip(flat, flat[1:])}

    hit_concepts = set()
    for tok in tokens | bigrams:
        hit_concepts.update(_TERM2CONCEPTS.get(tok, ()))
        # abreviatura UCS -> palabra completa -> concepto
        full = UCS_PREFIXES.get(tok)
        if full:
            hit_concepts.update(_TERM2CONCEPTS.get(full, ()))

    extra = set()
    for ci in hit_concepts:
        for term in CONCEPTS[ci]:
            extra.add(normalize(term))
    return extra, tokens


def searchable_text(expand_from, literal=""):
    """Texto de busqueda enriquecido para un sonido.

    Solo se expanden conceptos desde `expand_from` (nombre de archivo, tags y
    categoria). El nombre del pack va en `literal`: entra como texto buscable
    pero NO activa conceptos, porque los nombres de proveedor contaminan el
    pack entero. Un pack de "Digital Rain Lab" no son sonidos de lluvia, pero
    expandiendolo metia "agua", "water" y "liquido" en cada uno de sus
    archivos.
    """
    extra, tokens = expand(expand_from)
    words = set(normalize(expand_from).split()) | tokens | extra
    if literal:
        # tokens sueltos, sin pasar por el tesauro
        for t in re.findall(r"[A-Za-z0-9ñÑ]+", literal):
            words.update(split_compounds(t))
        words.update(normalize(literal).split())
    words = {w for w in words if len(w) > 1}
    return " ".join(sorted(words))
