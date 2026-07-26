<div align="center">

# Biblioteca de Sonidos

**Tu propia librería de efectos de sonido en local, con buscador en español, para DaVinci Resolve y cualquier editor.**

Sin suscripciones. Sin subir nada a la nube. Todo con licencia comercial verificable.

[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-ffab3d.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.8+-4b8bbe.svg)
![Sin dependencias JS](https://img.shields.io/badge/frontend-sin%20dependencias-2ea44f.svg)

</div>

---

## Qué es

Las plataformas de efectos de sonido cuestan entre 10 y 30 € al mes, y en cuanto
dejas de pagar pierdes el derecho a usar lo que ya habías puesto en tus vídeos.

Esto es la alternativa: un script descarga miles de sonidos **gratuitos y de uso
comercial permanente**, los unifica en una sola librería con metadatos, y te da
una interfaz web local para buscarlos, escucharlos y llevártelos al editor.

Una instalación típica deja **~5.000 sonidos y 15 horas de audio en unos 20 GB**.

### Qué tiene

- **Buscador que entiende español** aunque los archivos estén en inglés. Buscas
  `caballo` y encuentra `Hoof_Gallop`, `Pony Whinny` y `FEETHors_Draft Horse`.
  Tolera prefijos (`caball`) y erratas (`caballlo`).
- **12 categorías** clasificadas automáticamente: impactos, whooshes, interfaz,
  ambientes, foley, voz, cinemático, armas, vehículos, magia y ciencia ficción,
  agua, animales.
- **Sonidos parecidos** por similitud vectorial: desde un galope te saca el resto
  de cascos y trotes aunque no compartan una sola palabra en el nombre.
- **Reproductor** con forma de onda, seek, bucle y atajos de teclado.
- **Favoritos** que se exportan a una carpeta lista para arrastrar al Media Pool
  de Resolve.
- **Licencias siempre a la vista**, filtrables, con `CREDITS.md` autogenerado
  para lo que exige atribución.
- **Añade tus propias librerías** desde la interfaz o por terminal.

---

## Instalación

Necesitas **Python 3.8+** y **ffmpeg**. En Debian/Ubuntu:

```bash
sudo apt install python3 ffmpeg git
```

Después:

```bash
git clone https://github.com/VictorEscribano/biblioteca-de-sonidos.git
cd biblioteca-de-sonidos
./install.sh
```

El instalador comprueba dependencias y espacio, descarga las librerías, indexa
todo e instala el lanzador de escritorio. Tarda entre 30 min y 2 h según tu
conexión: son ~20 GB.

```bash
./install.sh --budget-gb 5      # instalación ligera
./install.sh --skip-download    # solo indexar lo que ya tengas
./install.sh --no-desktop       # sin icono de escritorio
```

La descarga es **reanudable**: si la cortas con Ctrl-C, al relanzar sigue donde
iba.

---

## Uso

Abre el icono **Biblioteca de Sonidos**, o desde terminal:

```bash
./sonidos            # abre http://sfx.localhost:7777
./sonidos estado     # resumen de lo que tienes
./sonidos index      # reindexa tras añadir sonidos
./sonidos icono      # reinstala el lanzador de escritorio
```

| Acción | Cómo |
|---|---|
| Buscar | Escribe, o pulsa <kbd>/</kbd>. Español o inglés |
| Reproducir | Clic en la fila, o <kbd>espacio</kbd> |
| Navegar | <kbd>↑</kbd> <kbd>↓</kbd> entre resultados |
| Favorito | Estrella de la fila, o <kbd>F</kbd> |
| Ver parecidos | Icono de nodos de la fila |
| Copiar ruta | Icono de copiar de la fila |

### Llevar sonidos a DaVinci Resolve

**Toda la librería, siempre disponible:** en Resolve, panel *Media Storage*,
navega hasta `library/` y añádela a favoritos. La tendrás en todos los
proyectos sin reimportar.

**Una selección concreta:** marca favoritos, pulsa *Exportar favoritos* y
arrastra la carpeta resultante al Media Pool. Usa enlaces duros, así que no
duplica espacio en disco.

### Añadir tus propias librerías

Desde la interfaz, botón **«Añadir librería»**: indicas la ruta de una carpeta
o un `.zip` que ya tengas en el disco, el proveedor y la licencia. Aparecerá
como su propia sección en *Fuentes*.

Desde terminal:

```bash
./sonidos add ~/Downloads/mi-libreria.zip \
    --vendor "Nombre del estudio" \
    --license "Comercial royalty-free"
```

No copia nada: enlaza, así que no ocupa espacio extra.

---

## De dónde salen los sonidos

| Fuente | Licencia | Uso comercial | Atribución |
|---|---|---|---|
| [Sonniss GDC Bundles](https://sonniss.com/gameaudiogdc) | Royalty-free propia | Sí, ilimitado | No |
| [Kenney.nl](https://kenney.nl/assets/category:Audio) | CC0 | Sí | No |
| [Freesound](https://freesound.org) (opcional) | CC0 / CC-BY | Sí | Solo CC-BY |

Todo lo que instala `install.sh` es de **uso comercial sin atribución**. Si
añades Freesound, los CC-BY quedan listados en `CREDITS.md` con su autor y
enlace, y la interfaz muestra la licencia de cada sonido.

> [!IMPORTANT]
> La licencia de Sonniss **prohíbe expresamente** usar su audio para entrenar
> modelos de IA.

### Freesound (opcional)

Añade ~1.700 sonidos curados en calidad original. Necesitas credenciales
OAuth2 de <https://freesound.org/apiv2/apply>:

```bash
python3 tools/dl_freesound.py --setup
python3 tools/dl_freesound.py --run --budget-gb 5
./sonidos index
```

Respeta los límites de su API (60 peticiones/minuto, 2.000/día).

---

## Cómo funciona la búsqueda

Este fue el problema difícil. La librería está en inglés y con nomenclatura
[UCS](https://universalcategorysystem.com/) abreviada (`FEETHors_Draft Horse
Walk`, `VEHWagn_Wood Cart`), así que buscar `caballo` no daba nada y `horse`
solo encontraba 6 de los 15 sonidos equinos que había.

La estrategia es **expandir los documentos al indexar, no las consultas**:

1. `tools/thesaurus.py` define 109 conceptos con ~1.200 términos en español e
   inglés. Al indexar `Hoof 2_Rocks_Gallop-4-Step` se le añaden *caballo,
   horse, galope, relincho, casco, equino…*, de modo que la palabra que
   escribas ya está literalmente en su texto de búsqueda.
2. Los prefijos UCS se separan y traducen: `FEETHors` → `feet` + `hors` →
   pasos + caballo.
3. En consulta (`web/search.js`) hay tres pasadas de precisión decreciente:
   token exacto → prefijo → trigramas. El ranking es BM25, reforzado cuando la
   coincidencia cae en el nombre del archivo.
4. *Parecidos* usa similitud coseno en el espacio TF-IDF.

Sobre 5.137 sonidos: 8.281 términos, índice construido en ~150 ms y consultas
en ~0,2 ms. Todo en el navegador, sin servidor de búsqueda.

---

## Estructura

```
├── install.sh           instalador
├── sonidos              lanzador (abrir, index, estado, add, icono)
├── tools/
│   ├── categories.py    taxonomía y clasificador por palabras clave
│   ├── thesaurus.py     tesauro ES-EN y abreviaturas UCS
│   ├── build_index.py   dedupe, metadatos, clasificación, index.json
│   ├── serve.py         servidor local (Range, export, import)
│   ├── crawl_gamesounds.py / dl_gamesounds.py / dl_kenney.py / dl_freesound.py
│   ├── add_pack.py      añadir librerías propias
│   └── install_desktop.sh
└── web/                 interfaz: HTML + CSS + JS sin dependencias
```

Lo generado (`library/`, `_staging/`, `index.json`, `CREDITS.md`) no está en el
repositorio: el repo es solo la herramienta, el audio lo descarga cada quien.

### Decisiones de diseño

- **Enlaces duros en vez de copias.** `library/` y `exports/` comparten inodos
  con `_staging/`, así que la estructura por categorías no duplica los ~20 GB.
- **Deduplicado por tamaño + hash de los primeros 256 KB.** Hashear 20 GB
  enteros sería lentísimo y para duplicados exactos esto basta.
- **El servidor implementa peticiones `Range`**, que `http.server` no trae. Sin
  ellas el navegador no puede hacer seek: descarga el WAV entero antes de sonar.
- **La forma de onda se decodifica en el navegador** solo para archivos de menos
  de 10 MB; por encima se muestra una barra lisa.
- **El servidor escucha en las dos loopback.** `sfx.localhost` resuelve antes a
  `::1` que a `127.0.0.1`, y atendiendo solo IPv4 el navegador se come un
  rechazo de conexión antes de reintentar.

---

## Contribuir

Se agradecen especialmente:

**Términos para el tesauro.** Es lo que más mejora la herramienta y lo más fácil
de aportar. Si buscas algo y no lo encuentra, abre un issue con la consulta y el
sonido que esperabas, o añade el término en `tools/thesaurus.py`:

```python
["horse", "caballo", "equino", "pony", "hoof", "gallop", "relincho", ...],
```

Cada grupo son términos intercambiables en ambos idiomas. Dos trampas que
conviene conocer antes de tocarlo, ambas descubiertas probando con datos
reales y anotadas en el código:

- **Los sinónimos ambiguos arrastran ruido.** `snort` (resoplido) estaba en el
  concepto de caballo y sacaba cerdos; `plate` estaba en el de cristal por
  «plato» y sacaba placas metálicas.
- **Los nombres de proveedor contaminan.** Un pack de *"Digital Rain Lab"* metía
  «agua» y «lluvia» en todos sus archivos. Por eso el nombre del pack entra como
  texto literal y no activa conceptos.

**Fuentes nuevas.** Si conoces librerías gratuitas de uso comercial que se
puedan descargar por script, abre un issue. Ten en cuenta que muchas están tras
Cloudflare y devuelven 403 a `curl`.

**Categorías y palabras clave** en `tools/categories.py`, si ves clasificaciones
que fallan.

### Antes de enviar un PR

```bash
python3 -m py_compile tools/*.py     # sintaxis Python
node --check web/app.js              # sintaxis JS
python3 tools/build_index.py         # debe terminar con código 0
```

El proyecto no tiene dependencias más allá de `requests`, y la interfaz no usa
ningún framework. Mantengámoslo así.

> [!WARNING]
> No se aceptan aportaciones que incluyan audio con derechos, enlaces a
> librerías comerciales filtradas, ni formas de sortear los muros de pago.

---

## Licencia

Código bajo [MIT](LICENSE). **Los archivos de audio no están cubiertos por
ella**: cada sonido conserva la licencia de su proveedor original. Consulta el
`CREDITS.md` que se genera en cada indexado.
