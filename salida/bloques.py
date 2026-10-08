"""Marcado exacto de bloques Gutenberg/Spectra (uagb), copiado de lo que guarda WordPress.

Solo piezas: no decide colores ni tamaños. Los atributos de Spectra (camelCase) los pasa quien llama como **attrs.
Si WordPress marca un bloque como inválido, normalmente se corrige aquí.
"""
import json, random

from config import CARPETA_MEDIOS


def new_block_id():
    """ID de 8 cifras hexadecimales para block_id (y la clase .uagb-block-<id>)."""
    return '%08x' % random.getrandbits(32)


def to_json(attrs):
    """Atributos -> JSON compacto como lo escapa WordPress dentro de un comentario de bloque."""
    text = json.dumps(attrs, ensure_ascii=False, separators=(',', ':'))
    return text.replace('--', '\\u002d\\u002d').replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def colored_text(text, color):
    """Texto con color en línea (el formato nativo de RichText: un <mark> de fondo transparente)."""
    return f'<mark style="background-color:rgba(0, 0, 0, 0);color:{color}" class="has-inline-color">{text}</mark>'


def container(children, block_id=None, root=False, full=False, anchor=None, class_name=None, **attrs):
    """Contenedor de Spectra con los bloques hijos ya armados.
    root: contenedor de primer nivel; full: además a todo el ancho (alignfull). anchor: id="" del HTML."""
    block_id = block_id or new_block_id()
    block_attrs = {"block_id": block_id}
    if root:
        block_attrs["contentWidth" if not full else "innerContentWidth"] = "default" if not full else "alignfull"
    block_attrs.update(attrs)
    if root:
        block_attrs.update(variationSelected=True, isBlockRootParent=True)
    if 'widthDesktop' in attrs:
        block_attrs["widthSetByUser"] = True
    if class_name:
        block_attrs["className"] = class_name
    if anchor:
        block_attrs["anchor"] = anchor
    hide_classes = ''.join(f' uag-hide-{device}' for device, attr in
                           (('desktop', 'UAGHideDesktop'), ('tab', 'UAGHideTab'), ('mob', 'UAGHideMob')) if attrs.get(attr))
    layout = f' uagb-layout-{attrs["layout"]}' if attrs.get('layout') else ''
    html_class = 'wp-block-uagb-container' + layout + (f' {class_name}' if class_name else '') + hide_classes + f' uagb-block-{block_id}'
    if root:
        html_class += (' alignfull' if full else ' default') + ' uagb-is-root-container'
    id_attr = f'id="{anchor}" ' if anchor else ''
    # contenedor enlazado (htmlTag "a"): Spectra guarda el enlace como un <a> vacío al final
    link = attrs.get('htmlTagLink', {}).get('url') if attrs.get('htmlTag') == 'a' else None
    overlay = f'<a class="spectra-container-link-overlay" rel="noopener" href="{link}"> </a>' if link else ''
    return (f'<!-- wp:uagb/container {to_json(block_attrs)} -->\n<div {id_attr}class="{html_class}">'
            + '\n\n'.join(children) + overlay + '</div>\n<!-- /wp:uagb/container -->')


def heading(text, tag='h2', block_id=None, class_name=None, **attrs):
    """Título avanzado de Spectra (también se usa para párrafos con tag='p'). text ya viene como HTML en línea."""
    block_id = block_id or new_block_id()
    block_attrs = {"block_id": block_id, "classMigrate": True, "headingDescToggle": False}
    if tag != 'h2':
        block_attrs["headingTag"] = tag
    block_attrs.update(attrs)
    if class_name:
        block_attrs["className"] = class_name
    html_class = f'wp-block-uagb-advanced-heading uagb-block-{block_id}' + (f' {class_name}' if class_name else '')
    return (f'<!-- wp:uagb/advanced-heading {to_json(block_attrs)} -->\n'
            f'<div class="{html_class}"><{tag} class="uagb-heading-text">{text}</{tag}></div>\n'
            '<!-- /wp:uagb/advanced-heading -->')


def icon(name, block_id=None, **attrs):
    """Ícono de Spectra (nombre de Font Awesome). Es un bloque sin contenido: WordPress lo dibuja."""
    return f'<!-- wp:uagb/icon {to_json({"icon": name, "block_id": block_id or new_block_id(), **attrs})} /-->'


def image(file_name, alt, natural_width, natural_height, block_id=None, class_name=None, **attrs):
    """Imagen de Spectra que apunta a la carpeta de Medios por nombre de archivo (WordPress no da el ID de antemano).
    attrs puede traer width/height: el tamaño con que se muestra (si no, el natural)."""
    block_id = block_id or new_block_id()
    url = CARPETA_MEDIOS + file_name
    block_attrs = {"block_id": block_id, "url": url, "urlTablet": url, "urlMobile": url, "alt": alt,
                   "linkDestination": "none", "title": file_name.rsplit('.', 1)[0], "naturalWidth": natural_width,
                   "naturalHeight": natural_height, "sizeSlug": "full", "sizeSlugTablet": "full", "sizeSlugMobile": "full"}
    block_attrs.update(attrs)
    if class_name:
        block_attrs["className"] = class_name
    hide_class = ' uag-hide-mob' if attrs.get('UAGHideMob') else ''
    html_class = (f'wp-block-uagb-image{hide_class} uagb-block-{block_id} wp-block-uagb-image--layout-default '
                  f'wp-block-uagb-image--effect-static wp-block-uagb-image--align-{attrs.get("align", "none")}'
                  ) + (f' {class_name}' if class_name else '')
    shown_width, shown_height = attrs.get('width', natural_width), attrs.get('height', natural_height)
    return (f'<!-- wp:uagb/image {to_json(block_attrs)} -->\n<div class="{html_class}"><figure class="wp-block-uagb-image__figure">'
            f'<img srcset="{url} ,{url} 780w, {url} 360w" sizes="(max-width: 480px) 150px" src="{url}" alt="{alt}" '
            f'width="{shown_width}" height="{shown_height}" title="{block_attrs["title"]}" loading="lazy" role="img"/>'
            '</figure></div>\n<!-- /wp:uagb/image -->')


def button(label, link, block_id=None, class_name=None, **attrs):
    """Un botón de Spectra. Va siempre dentro de button_group()."""
    block_id = block_id or new_block_id()
    block_attrs = {"block_id": block_id, "label": label, "link": link, **attrs}
    if class_name:
        block_attrs["className"] = class_name
    return (f'<!-- wp:uagb/buttons-child {to_json(block_attrs)} -->\n'
            f'<div class="wp-block-uagb-buttons-child uagb-buttons__outer-wrap uagb-block-{block_id} wp-block-button'
            + (f' {class_name}' if class_name else '') + '">'
            f'<div class="uagb-button__wrapper"><a class="uagb-buttons-repeater wp-block-button__link" aria-label="" '
            f'href="{link}" rel="follow noopener" target="_self" role="button"><div class="uagb-button__link">{label}</div></a></div></div>\n'
            '<!-- /wp:uagb/buttons-child -->')


def button_group(buttons, align="left", gap=12):
    """Grupo de botones de Spectra con los botones (button()) ya armados."""
    block_id = new_block_id()
    block_attrs = {"block_id": block_id, "classMigrate": True, "childMigrate": True, "align": align, "gap": gap}
    return (f'<!-- wp:uagb/buttons {to_json(block_attrs)} -->\n<div class="wp-block-uagb-buttons uagb-buttons__outer-wrap uagb-btn__default-btn '
            f'uagb-btn-tablet__default-btn uagb-btn-mobile__default-btn uagb-block-{block_id}"><div class="uagb-buttons__wrap uagb-buttons-layout-wrap ">'
            + '\n\n'.join(buttons) + '</div></div>\n<!-- /wp:uagb/buttons -->')


def list_item(text, sublist=None):
    """Un <li> de la lista nativa de WordPress, con su sublista (ya armada) si la tiene."""
    return f'<!-- wp:list-item -->\n<li>{text}{sublist or ""}</li>\n<!-- /wp:list-item -->'


def list_block(items, class_name, ordered=False):
    """Lista nativa de WordPress. items: el HTML de cada <li> ya armado con list_item()."""
    tag, block_attrs = ('ol', {"ordered": True, "className": class_name}) if ordered else ('ul', {"className": class_name})
    return (f'<!-- wp:list {to_json(block_attrs)} -->\n<{tag} class="wp-block-list {class_name}">' + '\n\n'.join(items)
            + f'</{tag}>\n<!-- /wp:list -->')


def table(header_cells, rows, class_name):
    """Tabla nativa de WordPress. header_cells: textos del <thead> (puede estar vacío); rows: listas de celdas."""
    header_html = ''.join(f'<th>{cell}</th>' for cell in header_cells)
    body_html = ''.join('<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows)
    thead = f'<thead><tr>{header_html}</tr></thead>' if header_cells else ''
    return (f'<!-- wp:table {to_json({"hasFixedLayout": False, "className": class_name})} -->\n'
            f'<figure class="wp-block-table {class_name}"><table>{thead}<tbody>{body_html}</tbody></table></figure>\n<!-- /wp:table -->')


def html_block(raw_html):
    """Bloque "HTML personalizado": el HTML va tal cual."""
    return f'<!-- wp:html -->\n{raw_html.strip()}\n<!-- /wp:html -->'
