"""CSS de un nodo -> atributos de Spectra (lo que se puede editar después desde el panel de WordPress).

Cada función devuelve también qué propiedades CSS quedaron traducidas, para no copiarlas otra vez como CSS.
El orden en que se agregan los atributos es el orden del JSON del bloque: no cambiarlo sin necesidad.
"""
import os, re

from config import CARPETA_MEDIOS
from conversion.clasificar import mobile_hide_attrs
from lectura.estilos import split_outside_parens
from lectura.valores import four_sides, parse_border, parse_shadow, to_px

SIDES = ('top', 'right', 'bottom', 'left')
DEFAULT_HEADING_SIZES = {'h1': 32, 'h2': 24, 'h3': 19, 'h4': 16}
FONT_WEIGHT_NAMES = {'bold': '700', 'normal': '400', 'bolder': '800', 'lighter': '300'}


def container_attrs(node, root=False):
    """Fondo, padding, borde, radios, sombra, color de texto y ocultar en celular -> atributos de contenedor.
    root=True: sección de primer nivel (su padding lateral no se copia: lo pone el ancho del contenido).
    Devuelve (atributos, propiedades_traducidas, fondo_css). fondo_css: un fondo que Spectra no puede guardar
    como atributo y que quien llama escribe como CSS (o None)."""
    attrs, translated = {}, set()
    background_css = _add_background(node, attrs, translated)
    _add_padding(node, attrs, translated, root)
    _add_border(node, attrs, translated)
    _add_border_radius(node, attrs, translated)
    _add_shadow(node, attrs, translated)
    if 'color' in node.own_style:
        attrs['textColor'] = node.own_style['color']
        translated.add('color')
    attrs.update(mobile_hide_attrs(node))
    return attrs, translated, background_css


def _add_background(node, attrs, translated):
    """Color, degradado o foto de fondo -> atributos. Devuelve el fondo como CSS si Spectra no lo puede guardar."""
    background = (node.own_style.get('background') or node.own_style.get('background-color') or '').strip()
    if not background:
        return None
    background_css = None
    layers = [layer.strip() for layer in split_outside_parens(background, ',')]
    photos = [layer for layer in layers if 'url(' in layer]
    gradients = [layer for layer in layers if 'gradient(' in layer and 'url(' not in layer]
    is_photo_with_optional_gradient = len(photos) == 1 and len(gradients) <= 1 and len(layers) == len(gradients) + 1
    if is_photo_with_optional_gradient:
        # foto de fondo (+ degradado encima) con atributos nativos: se puede editar desde el panel de Spectra
        _add_background_photo(node, photos[0], gradients, attrs, translated)
    elif 'url(' in background:
        # combinación que Spectra no tiene: se copia como CSS exacto, con las fotos apuntando a Medios
        background_css = re.sub(r'url\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)',
                                lambda m: f'url({CARPETA_MEDIOS}{os.path.basename(m.group(1))})', background)
    elif re.fullmatch(r'(linear|radial)-gradient\(.*\)', background) and background.count('gradient(') == 1:
        attrs.update(backgroundType='gradient', gradientValue=background)
    elif 'gradient(' not in background and len(split_outside_parens(background, ' ')) == 1:
        attrs.update(backgroundType='color', backgroundColor=background)
    else:
        background_css = background
    translated |= {'background', 'background-color'}
    return background_css


def _add_background_photo(node, photo_layer, gradients, attrs, translated):
    """Capa 'url(...) center/cover fixed' (+ degradado encima) -> atributos de imagen de fondo y overlay."""
    url = re.search(r'url\(\s*[\'"]?([^\'")]+)', photo_layer).group(1)
    options = re.sub(r'url\([^)]*\)', '', photo_layer)
    attrs.update(backgroundType='image', backgroundImageDesktop={'url': CARPETA_MEDIOS + os.path.basename(url)})
    if 'cover' in options or 'contain' in options:
        attrs['backgroundSizeDesktop'] = 'cover' if 'cover' in options else 'contain'
    if 'center' in options:
        attrs['backgroundPositionDesktop'] = {'x': 0.5, 'y': 0.5}
    if 'fixed' in options:
        attrs['backgroundAttachmentDesktop'] = 'fixed'
        mobile_attachment = node.own_mobile_style.get('background-attachment')
        if mobile_attachment not in (None, 'fixed'):   # en celular el fondo fijo suele apagarse
            attrs['backgroundAttachmentMobile'] = mobile_attachment
            attrs['backgroundAttachmentTablet'] = mobile_attachment
        translated.add('background-attachment')
    if gradients:
        attrs.update(overlayType='gradient', gradientValue=gradients[0], overlayOpacity=1)


def _add_padding(node, attrs, translated, root):
    """padding y padding-<lado> (escritorio y celular) -> atributos <lado>Padding<Dispositivo>."""
    own, own_mobile = node.own_style, node.own_mobile_style
    padding = four_sides(own.get('padding'))
    if padding:
        desktop = [to_px(value) for value in padding]
        mobile = [to_px(value, True) for value in (four_sides(own_mobile.get('padding')) or padding)]
        top, right, bottom, left = 0, 1, 2, 3
        if desktop[top] is not None and desktop[bottom] is not None:
            attrs.update(topPaddingDesktop=desktop[top], bottomPaddingDesktop=desktop[bottom],
                         topPaddingMobile=mobile[top], bottomPaddingMobile=mobile[bottom])
            if not root and desktop[right] is not None and desktop[left] is not None:
                attrs.update(rightPaddingDesktop=desktop[right], leftPaddingDesktop=desktop[left],
                             rightPaddingMobile=mobile[right], leftPaddingMobile=mobile[left])
            translated.add('padding')
    for side in SIDES:
        if to_px(own.get(f'padding-{side}')) is not None:
            attrs[f'{side}PaddingDesktop'] = to_px(own[f'padding-{side}'])
            translated.add(f'padding-{side}')
    for side in SIDES:
        attrs.setdefault(f'{side}PaddingDesktop', 0)
        mobile_value = own_mobile.get(f'padding-{side}')
        changes_on_mobile = mobile_value is not None and mobile_value != own.get(f'padding-{side}')
        is_root_side = root and side in ('left', 'right')
        if changes_on_mobile and to_px(mobile_value, True) is not None and not is_root_side:
            attrs[f'{side}PaddingMobile'] = to_px(mobile_value, True)
            translated.add(f'padding-{side}')


def _add_border(node, attrs, translated):
    """border y border-<lado> -> anchos por lado, estilo y color. Spectra guarda un solo color: con colores
    distintos por lado el borde se deja como CSS."""
    own = node.own_style
    borders = {side.capitalize(): parse_border(own['border']) for side in SIDES} if 'border' in own else {}
    for side in SIDES:
        if f'border-{side}' in own:
            borders[side.capitalize()] = parse_border(own[f'border-{side}'])
    if not borders:
        return
    colors = {color for width, style, color in borders.values() if width and style != 'none' and color}
    if len(colors) > 1:
        return
    for side in ('Top', 'Right', 'Bottom', 'Left'):
        width, style, _ = borders.get(side, (0, 'none', None))
        attrs[f'containerBorder{side}Width'] = width if style != 'none' else 0
    styles = {style for width, style, _ in borders.values() if width and style != 'none'}
    attrs['containerBorderStyle'] = styles.pop() if len(styles) == 1 else 'solid'
    if colors:
        attrs['containerBorderColor'] = colors.pop()
    translated |= {'border', 'border-top', 'border-right', 'border-bottom', 'border-left'}


def _add_border_radius(node, attrs, translated):
    """border-radius (px o %) -> radio de cada esquina. Un % (círculo, píldora) se guarda como 999."""
    corners = four_sides(node.own_style.get('border-radius'))
    if corners and all(to_px(value) is not None or value.endswith('%') for value in corners):
        for corner, value in zip(('TopLeft', 'TopRight', 'BottomRight', 'BottomLeft'), corners):
            attrs[f'containerBorder{corner}Radius'] = 999 if value.endswith('%') else to_px(value)
        translated.add('border-radius')


def _add_shadow(node, attrs, translated):
    """box-shadow de una sola capa -> atributos de sombra. Varias capas se quedan como CSS."""
    shadow = parse_shadow(node.own_style.get('box-shadow'))
    if shadow and not shadow[5]:
        x, y, blur, spread, color, _ = shadow
        attrs.update(boxShadowColor=color, boxShadowHOffset=x, boxShadowVOffset=y, boxShadowBlur=blur, boxShadowSpread=spread)
        translated.add('box-shadow')


def first_font_family(font_family):
    """'"DM Sans", Arial, sans-serif' -> 'DM Sans' (la fuente que se le pide a Spectra)."""
    return split_outside_parens(font_family, ',')[0].strip().strip('"\'')


def heading_attrs(node, tag, google_fonts):
    """Tipografía del nodo -> atributos del título de Spectra (color, tamaño, fuente, peso, alineación, interlineado).
    Usa el estilo heredado (el texto toma la fuente de la página). Devuelve (atributos, propiedades_traducidas)."""
    style, attrs = node.style, {'headSpace': 0}
    if style.get('color'):
        attrs['headingColor'] = style['color']
    attrs['headFontSize'] = to_px(style.get('font-size')) or DEFAULT_HEADING_SIZES.get(tag, 16)
    mobile_size = to_px(node.mobile_style.get('font-size'), True)
    if mobile_size and mobile_size != attrs['headFontSize']:
        attrs['headFontSizeMobile'] = mobile_size
    if style.get('font-family'):
        family = first_font_family(style['font-family'])
        attrs['headFontFamily'] = family
        if family in google_fonts:
            attrs['headLoadGoogleFonts'] = True
    weight = style.get('font-weight') or ('700' if tag.startswith('h') else None)
    if weight:
        attrs['headFontWeight'] = FONT_WEIGHT_NAMES.get(weight, weight)
    if style.get('text-align') in ('center', 'right', 'left'):
        attrs['headingAlign'] = style['text-align']
    line_height = style.get('line-height', '')
    if re.fullmatch(r'[\d.]+', line_height):
        attrs.update(headLineHeightType='em', headLineHeight=float(line_height))
    elif to_px(line_height):
        attrs.update(headLineHeightType='px', headLineHeight=to_px(line_height))
    return attrs, {'color', 'font-size', 'font-family', 'font-weight', 'text-align', 'line-height'}
