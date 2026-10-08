"""Preguntas sobre un nodo para decidir qué bloque le toca: ¿es texto en línea, botón, fila, caja?"""
from config import PX_ESCRITORIO
from lectura.arbol import INLINE_TAGS, Node, walk
from lectura.valores import grid_columns, parse_border

# si un <a> tiene alguna de estas adentro, es una tarjeta enlazada y no un botón
BLOCK_TAGS_INSIDE_LINK = ('img', 'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol')
# propiedades que hacen que un contenedor sea una caja visible (no se aplana): fondo, borde, padding, scroll...
BOX_PROPS = ('background', 'background-color', 'border', 'border-left', 'border-top', 'border-right', 'border-bottom',
             'box-shadow', 'padding', 'border-radius', 'overflow', 'overflow-x', 'overflow-y', 'max-height')


def is_inline(item):
    """¿Va dentro de un texto? Textos sueltos y etiquetas en línea (span, a, strong...) que no se volvieron bloque."""
    if isinstance(item, str):
        return True
    return item.tag in INLINE_TAGS and item.style.get('display') not in ('block', 'flex', 'grid', 'list-item')


def is_button(item):
    """¿Es un <a> con fondo o borde y display de caja (inline-block, flex...)? Entonces es un botón de Spectra."""
    if not isinstance(item, Node) or item.tag != 'a':
        return False
    if any(descendant.tag in BLOCK_TAGS_INSIDE_LINK for descendant in walk(item)):
        return False
    style = item.style
    has_border = style.get('border') and parse_border(style['border'])[0] > 0
    has_background = style.get('background') or style.get('background-color')
    return bool(has_background or has_border) and style.get('display') in ('inline-block', 'block', 'inline-flex', 'flex')


def has_box(node):
    """¿Tiene fondo, borde, padding, sombra, scroll o estados (:hover...)? Entonces es un contenedor propio."""
    return bool(node.states) or any(prop in node.own_style for prop in BOX_PROPS)


def is_row(node):
    """¿Pone a sus hijos lado a lado? display:flex en fila, o grid con más de una columna."""
    style = node.style
    if style.get('display') in ('grid', 'inline-grid'):
        return len(grid_columns(style, PX_ESCRITORIO, len(node.child_nodes)) or [1]) > 1
    return style.get('display') in ('flex', 'inline-flex') and style.get('flex-direction', 'row').startswith('row')


def hidden_on_mobile(node):
    """¿El @media de celular lo oculta (display:none) cuando en escritorio sí se ve?"""
    return node.mobile_style.get('display') == 'none' and node.style.get('display') != 'none'


def mobile_hide_attrs(node):
    """Atributos de Spectra para ocultar el bloque en celular, si corresponde."""
    return {'UAGHideMob': True, 'UAGResponsiveConditions': True} if hidden_on_mobile(node) else {}
