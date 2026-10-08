# lino

*Lino* viene del griego λύω (*lýō*): resolver, desatar.

Convierte una página HTML + CSS en bloques de [Spectra](https://wpspectra.com/) (Gutenberg) para pegar en el **Editor de código** de WordPress.

Solo usa la librería estándar de Python 3; no hay nada que instalar.

## Uso

```bash
python3 lino pagina.html [otra.html ...] [--salida carpeta] [--css-aparte] [--prefijo xx-]
```

Por cada página escribe `<pagina>.txt` en la carpeta desde donde se ejecuta el comando (o en `--salida`).
Ese texto se pega completo en WordPress: menú ⋮ → **Editor de código**.

| Opción | Qué hace |
|---|---|
| `--salida carpeta` | Carpeta donde guardar los `.txt` (se crea si no existe). |
| `--css-aparte` | El CSS que Spectra no puede guardar como atributo va a `<pagina>.css`, para pegarlo una vez en *Apariencia → Personalizar → CSS adicional*, en vez de un bloque `<style>` dentro de cada página. |
| `--prefijo xx-` | Prefijo de las clases originales copiadas a los bloques (por defecto `lino-`). |

La terminal muestra cuántos bloques generó y los `aviso:` de lo que no pudo convertir (selectores no soportados, `@media` copiados tal cual, etiquetas pasadas como bloque HTML).

## Archivos

Se ejecuta pasándole a `python3` la carpeta del repo (`python3 lino …` desde afuera, `python3 . …` desde adentro, o con su ruta completa). Solo usa la librería estándar.

En la raíz quedan la línea de comandos y la configuración; el código está en tres carpetas, una por etapa:

| Archivo | Qué hace |
|---|---|
| `__main__.py` | La línea de comandos: lee argumentos, escribe `.txt`/`.css` e imprime avisos. |
| `config.py` | Lo que se ajusta a mano (ver *Configuración*). |
| **`lectura/`** | **Entrada: el HTML y el CSS.** |
| `lectura/arbol.py` | Lee el HTML y arma el árbol de nodos. |
| `lectura/estilos.py` | Lee el CSS, resuelve variables y selectores, y calcula el estilo de cada nodo. |
| `lectura/valores.py` | Convierte valores CSS (px, bordes, sombras, columnas de grid, enlaces) a lo que usa Spectra. |
| **`conversion/`** | **Decide qué bloque es cada cosa.** |
| `conversion/conversor.py` | Punto de entrada: lee la página, calcula estilos y entrega los bloques y el CSS. |
| `conversion/estructura.py` | Decide qué bloque corresponde a cada elemento y arma secciones, filas y contenedores. |
| `conversion/clasificar.py` | Responde qué es cada nodo: texto en línea, botón, fila o caja. |
| `conversion/atributos.py` | Traduce el CSS de un nodo a atributos de Spectra (fondo, padding, borde, radio, sombra, tipografía). |
| `conversion/textos.py` | Títulos, párrafos y el HTML en línea (negritas, enlaces, colores). |
| `conversion/elementos.py` | Imagen, botón, ícono, lista, tabla y bloque HTML. |
| **`salida/`** | **Lo que se escribe.** |
| `salida/bloques.py` | El marcado exacto de cada bloque (contenedor, título, imagen, botones, ícono, lista, tabla, HTML). Si WordPress marca un bloque como inválido, normalmente se corrige aquí. |
| `salida/hoja_css.py` | Junta el CSS que Spectra no guarda como atributo y lo escribe al final. |
| `salida/validar.py` | Revisa que el resultado tenga bloques balanceados y JSON válido. |

Los nombres en el código están en inglés; los comentarios, avisos y este README, en español. Cada función tiene un comentario que dice qué recibe y qué devuelve.

## Qué lee

- Hojas de estilo enlazadas con `<link rel="stylesheet" href="...">` (ruta relativa al HTML), bloques `<style>` y atributos `style=""`.
- Variables `var(--x)` definidas en `:root`.
- `@media (max-width: …)` como versión para celular.
- Especificidad, herencia y `:nth-child` / `:nth-of-type`.
- Nombres de fuentes de Google Fonts enlazadas (para que Spectra las cargue).

No lee: hojas remotas (`https://…`), `@import`, selectores de hermanos (`+`, `~`).

## Cómo decide

| En el HTML/CSS | En WordPress |
|---|---|
| Hijo de `<body>`/`<main>` que es `<section>` o tiene fondo/borde/padding | Sección a todo el ancho con el contenido centrado |
| `display: grid` o `display: flex` en fila | Contenedor flex en fila; anchos y huecos en % que suman 100 (nunca el diseño grid de Spectra) |
| `flex` sin `flex: 1` | Cada hijo mide lo que su contenido (`childrenWidthDesktop: auto`) |
| `<a>` con fondo o borde | Botón (con colores de `:hover`) |
| `<a href>` que envuelve una imagen y otros bloques | Contenedor enlazado de Spectra (toda la tarjeta es clicable) |
| `h1`–`h6`, `p` | Título avanzado de Spectra |
| `ul` / `ol` | Lista |
| `img` | Imagen de Spectra (ruta `/wp-content/uploads/<nombre>`) |
| `<a href="img/foto.jpg">` (enlace a una imagen local) | Enlace a `/wp-content/uploads/foto.jpg` |
| `table` | Tabla |
| `iframe`, `video`, `svg`, `form`… | Bloque HTML |
| `<span>` con un emoji de `ICONOS`, o `<span data-icono="book">` (nombre de Font Awesome; el `<svg>` de adentro es solo para ver la página) | Ícono de Spectra |
| Comentario `<!-- wp:bloque {...} /-->` | Se copia tal cual (bloques propios del sitio) |
| `footer` | Se omite (lo pone el tema) |

Lo que Spectra guarda como atributo (fondo, color, padding, bordes, radios, sombra, tipografía, anchos, ocultar en celular) va al bloque. Lo demás (`:hover`, `::before`, transiciones, `clip-path`, animaciones) se escribe como CSS apuntando a la clase única de cada bloque (`.uagb-block-XXXX`), con `!important` para que el CSS propio de Spectra no lo pise (por ejemplo `overflow` de un scroll o el alto de una foto).

## Configuración

En `config.py`:

- `OMITIR`: etiquetas que no se convierten.
- `ANCHO_CONTENIDO`: ancho (%) del contenido centrado en cada sección.
- `SECCION_SIN_PADDING`: margen (px) para secciones sin `padding` en su CSS.
- `ICONOS`: emoji → ícono de Font Awesome.
- `ENLACES`: rutas locales → rutas en WordPress (por ejemplo `index.html#` → `../#`).
- `CARPETA_MEDIOS`: ruta donde WordPress guarda las imágenes (`/wp-content/uploads/`).

## Imágenes

El conversor no puede saber el ID que WordPress le asigna a cada imagen, así que las referencia por nombre. Sube las imágenes a **Medios** con el mismo nombre de archivo. Si un bloque de imagen pide "Intentar recuperar", vuelve a elegir la imagen desde la biblioteca.
