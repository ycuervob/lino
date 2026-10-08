"""Textos: el HTML en línea (negritas, enlaces, colores) y los bloques de título/párrafo de Spectra."""
import re
from html import escape

from conversion.atributos import heading_attrs
from conversion.clasificar import mobile_hide_attrs
from lectura.arbol import Node
from lectura.valores import wordpress_href
from salida import bloques as spectra

KEPT_INLINE_TAGS = ('strong', 'b', 'em', 'i', 'a', 'code', 'sub', 'sup')   # se conservan como etiqueta
RENAMED_INLINE_TAGS = {'b': 'strong', 'i': 'em'}


def inline_html(items, parent_color):
    """Textos y nodos en línea -> HTML para un título de Spectra. Se conservan negritas, cursivas, enlaces y <br>;
    de los demás (span, mark, time...) queda el texto, con color propio si es distinto al de su padre."""
    pieces = []
    for item in items:
        if isinstance(item, str):
            pieces.append(escape(re.sub(r'\s+', ' ', item), quote=False))
        elif item.tag == 'br':
            pieces.append('<br>')
        elif item.tag in KEPT_INLINE_TAGS:
            link_attrs = ''
            if item.tag == 'a':
                link_attrs = f' href="{escape(wordpress_href(item.attrs.get("href", "#")))}"'
                if item.attrs.get('target') == '_blank':
                    link_attrs += ' target="_blank" rel="noreferrer noopener"'
            tag = RENAMED_INLINE_TAGS.get(item.tag, item.tag)
            inner = inline_html(item.children, item.style.get('color') or parent_color)
            pieces.append(f'<{tag}{link_attrs}>{inner}</{tag}>')
        else:
            text = inline_html(item.children, item.style.get('color'))
            color = item.style.get('color')
            has_own_color = 'color' in item.own_style and color != parent_color
            pieces.append(spectra.colored_text(text, color) if has_own_color else text)
    return re.sub(r'\s*<br>\s*', '<br>', ''.join(pieces)).strip()


def text_block(converter, node, items=None, layout=False):
    """Título avanzado de Spectra para un h1–h6 o un párrafo.

    items=None: el bloque es el nodo mismo (su etiqueta, su clase y su CSS sobrante).
    items=[...]: textos sueltos dentro de node que se juntan en un párrafo (sin clase ni CSS propio de node).
    layout=True: node es una fila de enlaces (menú) que se escribe como un solo texto con su display:flex.
    Devuelve [] si no hay texto."""
    tag = node.tag if re.fullmatch(r'h[1-6]', node.tag) and items is None else 'p'
    content = inline_html(node.children if items is None else items, node.style.get('color'))
    if not content:
        return []
    block_id = spectra.new_block_id()
    attrs, translated = heading_attrs(node, tag, converter.stylesheet.google_fonts)
    target = f'.uagb-block-{block_id} .uagb-heading-text'
    if items is None:
        attrs.update(mobile_hide_attrs(node))
        # en textos, display (p. ej. inline-block de una etiqueta con borde) sí importa: se conserva
        keeps_display = node.own_style.get('display') in ('inline-block', 'inline-flex', 'block') and not layout
        converter.css.add_leftover(node, target, translated, layout=not layout)
        converter.css.add(target, {'display': node.own_style['display']} if keeps_display else {})
    child_nodes = [item for item in (node.children if items is None else items) if isinstance(item, Node)]
    converter.css.add_descendants(node, target, only=child_nodes)
    class_name = converter.class_names(node) if items is None else None
    return [spectra.heading(content, tag, block_id=block_id, class_name=class_name, **attrs)]
