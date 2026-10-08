"""Bloques sencillos que no contienen otros bloques: imagen, botón, ícono, lista, tabla y HTML personalizado."""
import os
from html import escape

from config import ICONOS, avisos
from conversion.atributos import first_font_family
from conversion.clasificar import mobile_hide_attrs
from conversion.textos import inline_html
from lectura.arbol import VOID_TAGS, walk
from lectura.valores import four_sides, image_size, luminance, parse_border, parse_shadow, to_px, wordpress_href
from salida import bloques as spectra

# etiquetas que se esperan como bloque HTML; con cualquier otra se avisa en la terminal
EXPECTED_HTML_TAGS = ('iframe', 'video', 'audio', 'svg', 'canvas', 'form', 'hr')


def image(converter, node):
    """<img> -> imagen de Spectra con su ancho, radio y sombra; el resto de su CSS (alto, object-fit...) va aparte."""
    src = node.attrs.get('src', '')
    natural_width, natural_height = image_size(os.path.join(converter.base_dir, src))
    block_id, attrs, translated, own = spectra.new_block_id(), mobile_hide_attrs(node), set(), node.own_style
    width_px = to_px(own.get('width'))
    if width_px:
        attrs.update(width=width_px, height=round(width_px * natural_height / natural_width))
        translated.add('width')
    radius = to_px(own.get('border-radius'))
    if radius is not None:
        attrs.update(imageBorderTopLeftRadius=radius, imageBorderTopRightRadius=radius,
                     imageBorderBottomLeftRadius=radius, imageBorderBottomRightRadius=radius, imageBorderStyle='none')
        translated.add('border-radius')
    shadow = parse_shadow(own.get('box-shadow'))
    if shadow and not shadow[5]:
        x, y, blur, spread, color, _ = shadow
        attrs.update(imageBoxShadowHOffset=x, imageBoxShadowVOffset=y, imageBoxShadowBlur=blur,
                     imageBoxShadowSpread=spread, imageBoxShadowColor=color)
        translated.add('box-shadow')
    parent_align = (node.parent.style if node.parent else {}).get('text-align')
    if parent_align in ('center', 'right'):   # imagen centrada por el text-align de su contenedor
        attrs['align'] = parent_align
    if own.get('align-self') == 'center':   # o por align-self en una columna flex
        attrs['align'] = 'center'
        translated.add('align-self')
    target = f'.uagb-block-{block_id} img'
    converter.css.add_leftover(node, target, translated)
    if own.get('width') and not width_px:   # 100%, auto...: si no, Spectra usa el ancho natural de la foto
        converter.css.add(target, {'width': own['width'], 'max-width': 'none'})
        if own['width'] == '100%':   # el bloque y su <figure> también, o la foto no llena la tarjeta
            converter.css.add(f'.uagb-block-{block_id}, .uagb-block-{block_id} .wp-block-uagb-image__figure',
                              {'width': '100%', 'max-width': '100%'})
    return spectra.image(os.path.basename(src), node.attrs.get('alt', ''), natural_width, natural_height,
                         block_id=block_id, class_name=converter.class_names(node), **attrs)


def button(converter, node):
    """<a> con fondo o borde -> botón de Spectra (colores normales y de :hover, borde, radio, padding, fuente)."""
    style, block_id = node.style, spectra.new_block_id()
    background = style.get('background') or style.get('background-color') or 'transparent'
    border_width, border_style, border_color = parse_border(style.get('border'))
    attrs = dict(color=style.get('color', '#000000'), background=background, transform='none', decoration='none',
                 btnBorderTopWidth=border_width, btnBorderLeftWidth=border_width, btnBorderRightWidth=border_width,
                 btnBorderBottomWidth=border_width, btnBorderStyle=border_style if border_width else 'none',
                 btnBorderColor=border_color or background)
    radius = to_px(style.get('border-radius'))
    if radius is not None:
        attrs.update(btnBorderTopLeftRadius=radius, btnBorderTopRightRadius=radius,
                     btnBorderBottomLeftRadius=radius, btnBorderBottomRightRadius=radius)
    padding = [to_px(value) for value in (four_sides(style.get('padding')) or [])]
    if padding and None not in padding:
        attrs.update(topPadding=padding[0], rightPadding=padding[1], bottomPadding=padding[2], leftPadding=padding[3])
    if style.get('font-family'):
        family = first_font_family(style['font-family'])
        attrs.update(fontFamily=family, loadGoogleFonts=family in converter.stylesheet.google_fonts)
    if style.get('font-weight'):
        attrs['fontWeight'] = {'bold': '700', 'normal': '400'}.get(style['font-weight'], style['font-weight'])
    if to_px(style.get('font-size')):
        attrs['size'] = to_px(style['font-size'])
    hover = node.states.get(':hover', {})
    hover_attrs = (('color', 'hColor'), ('background', 'hBackground'), ('background-color', 'hBackground'),
                   ('border-color', 'btnBorderHColor'))
    for prop, attr in hover_attrs:
        if hover.get(prop):
            attrs[attr] = hover[prop]
    if ':hover' in node.states:   # lo que ya quedó como atributo de :hover no se repite como CSS
        translated_hover = ('color', 'background', 'background-color', 'border-color')
        node.states = {**node.states, ':hover': {prop: value for prop, value in hover.items() if prop not in translated_hover}}
    converter.css.add_leftover(node, f'.uagb-block-{block_id} .uagb-buttons-repeater',
                               {'color', 'background', 'background-color', 'border', 'border-radius', 'padding',
                                'font-family', 'font-weight', 'font-size', 'text-decoration'})
    return spectra.button(escape(node.text(), quote=False), wordpress_href(node.attrs.get('href', '#')),
                          block_id=block_id, class_name=converter.class_names(node), **attrs)


def icon(span):
    """<span> con un emoji de config.ICONOS (o data-icono="nombre") -> ícono de Spectra.
    El ancho del span define el círculo/cuadro de fondo; el ícono queda centrado con padding."""
    style = span.style
    size = to_px(style.get('font-size')) or 24
    box_width = to_px(style.get('width'))
    padding = max(0, (box_width - size) // 2) if box_width else 0
    background = style.get('background') or style.get('background-color') or ''
    radius_value = style.get('border-radius', '0')
    radius = (box_width or size) // 2 if radius_value.endswith('%') else (to_px(radius_value) or 0)
    color = '#ffffff' if background and luminance(background) < .5 else style.get('color', '#000000')
    parent_align = (span.parent.style if span.parent else {}).get('text-align')
    return spectra.icon(span.attrs.get('data-icono') or ICONOS[span.text()], iconSize=size,
                        align=parent_align if parent_align in ('center', 'right') else 'left',
                        iconColor=color, iconBackgroundColor=background,
                        iconTopPadding=padding, iconRightPadding=padding, iconLeftPadding=padding,
                        iconBottomPadding=padding, iconPaddingLink=True,
                        iconBorderTopLeftRadius=radius, iconBorderTopRightRadius=radius,
                        iconBorderBottomLeftRadius=radius, iconBorderBottomRightRadius=radius, iconBorderStyle='none')


def bullet_list(converter, node):
    """<ul>/<ol> (con sublistas) -> lista nativa de WordPress con una clase propia para su CSS."""
    list_class = f'lst-{spectra.new_block_id()[:6]}'

    def items_of(list_node):
        items = []
        for li in (child for child in list_node.child_nodes if child.tag == 'li'):
            sublist_node = next((child for child in li.child_nodes if child.tag in ('ul', 'ol')), None)
            text = inline_html([child for child in li.children if child is not sublist_node], li.style.get('color'))
            sublist = ('<!-- wp:list -->\n<ul class="wp-block-list">' + '\n\n'.join(items_of(sublist_node))
                       + '</ul>\n<!-- /wp:list -->') if sublist_node else ''
            items.append(spectra.list_item(text, sublist))
        return items
    converter.css.add_leftover(node, f'ul.{list_class}, ol.{list_class}', set(), layout=False)
    sides = four_sides(node.own_style.get('margin'))
    if sides:   # el tema le pone margen izquierdo a las listas y en celular el texto se sale de su tarjeta
        converter.css.add(f'ul.{list_class}, ol.{list_class}', {'margin-left': sides[3], 'margin-right': sides[1]})
    if node.style.get('font-family'):   # la lista no hereda la fuente de la página: el tema pone la suya
        converter.css.add(f'.{list_class} li', {'font-family': node.style['font-family']})
    converter.css.add_descendants(node, f'.{list_class}')
    class_name = ' '.join(name for name in (list_class, converter.class_names(node)) if name)
    return spectra.list_block(items_of(node), class_name, ordered=node.tag == 'ol')


def table(converter, node):
    """<table> -> tabla nativa de WordPress (encabezados <th> y filas de <td>) con una clase propia para su CSS."""
    table_class = f'tbl-{spectra.new_block_id()[:6]}'
    header_cells = [inline_html(cell.children, None) for cell in walk(node) if cell.tag == 'th']
    rows = [[inline_html(cell.children, None) for cell in row.child_nodes if cell.tag == 'td']
            for row in walk(node) if row.tag == 'tr']
    converter.css.add_leftover(node, f'.{table_class} table', set(), layout=False)
    converter.css.add_descendants(node, f'.{table_class} table')
    return spectra.table(header_cells, [row for row in rows if row], table_class)


def raw_html(converter, node):
    """Cualquier otra etiqueta (iframe, video, svg, form...) -> bloque HTML personalizado, tal cual,
    con una clase propia para su CSS."""
    html_class = f'raw-{spectra.new_block_id()[:6]}'

    def serialize(item, is_outer=False):
        if isinstance(item, str):
            return escape(item, quote=False)
        attrs = dict(item.attrs)
        if is_outer:
            attrs['class'] = ((attrs.get('class') or '') + ' ' + html_class).strip()
        attrs_html = ''.join(f' {name}="{escape(value or "")}"' for name, value in attrs.items())
        if item.tag in VOID_TAGS:
            return f'<{item.tag}{attrs_html}>'
        return f'<{item.tag}{attrs_html}>{"".join(serialize(child) for child in item.children)}</{item.tag}>'
    converter.css.add_leftover(node, f'.{html_class}', set(), layout=False)
    converter.css.add_descendants(node, f'.{html_class}')
    if node.tag not in EXPECTED_HTML_TAGS:
        avisos.append(f'<{node.tag}> pasado como bloque HTML')
    return spectra.html_block(serialize(node, True))
