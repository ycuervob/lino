"""Valores CSS -> números y piezas que entiende Spectra."""
import math, re, struct

from config import CARPETA_MEDIOS, ENLACES
from lectura.estilos import split_outside_parens


def to_px(value, mobile=False):
    """Longitud CSS -> px enteros ('1.5rem' -> 24). None si no es una longitud.
    clamp()/min()/max(): en escritorio se toma el valor mayor y en celular el menor."""
    if not value:
        return None
    value = value.strip()
    function = re.match(r'(clamp|min|max)\((.*)\)$', value)
    if function:
        args = [to_px(arg, mobile) for arg in split_outside_parens(function.group(2), ',')]
        args = [number for number in args if number is not None]
        if not args:
            return None
        if function.group(1) == 'clamp':
            return args[0] if mobile else args[-1]
        return min(args) if (function.group(1) == 'min') != mobile else max(args)
    number = re.fullmatch(r'(-?[\d.]+)(px|rem|em)?', value)
    if not number:
        return None
    return round(float(number.group(1)) * (16 if number.group(2) in ('rem', 'em') else 1))


def four_sides(value):
    """Atajo CSS de 1 a 4 valores -> [arriba, derecha, abajo, izquierda] ('4px 8px' -> 4px 8px 4px 8px)."""
    parts = split_outside_parens(value, ' ') if value else []
    if not parts:
        return None
    if len(parts) == 1:
        return parts * 4
    if len(parts) == 2:
        return [parts[0], parts[1], parts[0], parts[1]]
    return [parts[0], parts[1], parts[2], parts[1]] if len(parts) == 3 else parts[:4]


def parse_border(value):
    """'5px solid #53A826' -> (ancho, estilo, color). Sin ancho explícito se asume 1px."""
    if not value or value.strip() in ('0', 'none'):
        return 0, 'none', None
    width, style, color = None, 'solid', None
    for piece in split_outside_parens(value, ' '):
        piece = piece.strip()
        if width is None and to_px(piece) is not None:
            width = to_px(piece)
        elif piece in ('solid', 'dashed', 'dotted', 'double', 'none'):
            style = piece
        else:
            color = piece
    return (1 if width is None else width), style, color


def parse_shadow(value):
    """Primera capa de box-shadow -> (x, y, difuminado, expansión, color, hay_más_capas), o None si es none o inset."""
    layers = [layer.strip() for layer in split_outside_parens(value or '', ',') if layer.strip()]
    if not layers or layers[0] == 'none' or 'inset' in layers[0]:
        return None
    numbers, color = [], 'rgba(0,0,0,0.2)'
    for piece in split_outside_parens(layers[0], ' '):
        if to_px(piece) is not None:
            numbers.append(to_px(piece))
        else:
            color = piece.strip()
    numbers += [0] * (4 - len(numbers))
    return (*numbers[:4], color, len(layers) > 1)


def luminance(color):
    """Brillo de un color #rrggbb entre 0 (negro) y 1 (blanco). Otros formatos cuentan como claros (1)."""
    hex_match = re.match(r'#([0-9a-f]{6})', color or '', re.I)
    if not hex_match:
        return 1
    red, green, blue = (int(hex_match.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return .2126 * red + .7152 * green + .0722 * blue


def gaps(style, default=20):
    """(hueco entre filas, hueco entre columnas) en px a partir de gap / row-gap / column-gap."""
    gap = split_outside_parens(style.get('gap') or '', ' ')
    row_gap = to_px(style.get('row-gap')) or (to_px(gap[0]) if gap else None)
    column_gap = to_px(style.get('column-gap')) or (to_px(gap[-1]) if gap else None)
    return (default if row_gap is None else row_gap), (default if column_gap is None else column_gap)


def grid_columns(style, available_width, child_count):
    """grid-template-columns -> lista de columnas ('1fr', '260px'...), o None si no hay.
    repeat(auto-fill/auto-fit, minmax(...)) se resuelve con el ancho disponible."""
    template = style.get('grid-template-columns')
    if not template:
        return None
    column_gap = gaps(style, 0)[1]
    auto = re.fullmatch(r'repeat\(\s*(auto-fill|auto-fit)\s*,\s*minmax\(\s*([^,]+),[^)]*\)\s*\)', template.strip())
    if auto:
        min_width = to_px(auto.group(2)) or 200
        fitting = max(1, math.floor((available_width + column_gap) / (min_width + column_gap)))
        return ['1fr'] * (min(fitting, max(1, child_count)) if auto.group(1) == 'auto-fit' else fitting)
    columns = []
    for piece in split_outside_parens(template, ' '):
        repeat = re.fullmatch(r'repeat\(\s*(\d+)\s*,\s*(.+)\)', piece.strip())
        columns += [repeat.group(2).strip()] * int(repeat.group(1)) if repeat else [piece.strip()]
    return columns


def percent_widths(columns, gap_percent, available_width):
    """Columnas del CSS ('1fr', '260px'...) -> anchos en % que, sumados a los huecos en %, dan <= 100."""
    free = 100 - gap_percent * (len(columns) - 1)
    fixed = {i: (to_px(column) or 0) / available_width * 100
             for i, column in enumerate(columns) if not column.endswith('fr')}
    total_fr = sum(float(column[:-2]) for column in columns if column.endswith('fr')) or 1
    remaining = free - sum(fixed.values())
    widths = [fixed[i] if i in fixed else remaining * float(column[:-2]) / total_fr for i, column in enumerate(columns)]
    return [math.floor(width * 10) / 10 for width in widths]   # redondeo hacia abajo: nunca se pasa de 100


def image_size(path):
    """(ancho, alto) de un PNG o JPEG leyendo su cabecera; 1200x800 si no se puede leer."""
    try:
        data = open(path, 'rb').read()
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return struct.unpack('>II', data[16:24])
        pos = 2
        while pos < len(data):
            marker, length = data[pos + 1], struct.unpack('>H', data[pos + 2:pos + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):   # inicio de cuadro JPEG: ahí están alto y ancho
                height, width = struct.unpack('>HH', data[pos + 5:pos + 9])
                return width, height
            pos += 2 + length
    except (OSError, struct.error, IndexError):
        pass
    return 1200, 800


def without_grid(declarations):
    """Spectra nunca usa grid: display:grid -> flex (place-items -> align-items/justify-content) y se quitan las
    plantillas de grid. Modifica y devuelve el mismo diccionario."""
    if declarations.get('display', '').strip() in ('grid', 'inline-grid'):
        declarations['display'] = 'flex' if declarations['display'].strip() == 'grid' else 'inline-flex'
        place_items = declarations.pop('place-items', None)
        if place_items:
            declarations.setdefault('align-items', split_outside_parens(place_items, ' ')[0])
            declarations.setdefault('justify-content', split_outside_parens(place_items, ' ')[-1])
        for prop in ('grid-template-columns', 'grid-template-rows', 'grid-auto-flow'):
            declarations.pop(prop, None)
    return declarations


def wordpress_href(href):
    """Enlace del HTML local -> enlace en WordPress: imágenes locales a la carpeta de Medios (como el src) y
    los reemplazos de config.ENLACES (p. ej. la página de inicio)."""
    is_local_image = ':' not in href and not href.startswith('/') and \
        href.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
    if is_local_image:
        return CARPETA_MEDIOS + href.rsplit('/', 1)[-1]
    for local, on_wordpress in ENLACES.items():
        href = href.replace(local, on_wordpress)
    return href
