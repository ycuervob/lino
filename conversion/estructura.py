"""Estructura de la página: decide qué bloque le toca a cada elemento y arma contenedores, filas y secciones.

Las funciones se llaman entre sí recursivamente (block -> box -> flow -> block...). Todas reciben el converter
(conversor.Converter) con lo de la página: estilos, CSS de salida, prefijo de clases y carpeta del HTML.
"""
import re

from config import ANCHO_CONTENIDO, ICONOS, OMITIR, PX_CELULAR, PX_ESCRITORIO, PX_TABLET, SECCION_SIN_PADDING
from conversion import elementos
from conversion.atributos import container_attrs
from conversion.clasificar import has_box, is_button, is_inline, is_row, mobile_hide_attrs
from conversion.textos import text_block
from lectura.arbol import walk
from lectura.valores import four_sides, gaps, grid_columns, percent_widths, to_px, wordpress_href
from salida import bloques as spectra

TEXT_TAGS = r'h[1-6]|p|blockquote|figcaption|dt|dd|address'
RAW_HTML_TAGS = ('iframe', 'video', 'audio', 'svg', 'canvas', 'form', 'pre', 'hr', 'dl', 'select', 'input', 'button')
ALIGN_ITEMS_VALUES = {'center': 'center', 'start': 'flex-start', 'end': 'flex-end', 'flex-start': 'flex-start',
                      'flex-end': 'flex-end'}
JUSTIFY_CONTENT_VALUES = {'space-between': 'space-between', 'space-around': 'space-around',
                          'space-evenly': 'space-evenly', 'center': 'center', 'flex-end': 'flex-end', 'end': 'flex-end'}


def block(converter, node):
    """Un elemento -> lista de bloques. Aquí se decide qué es cada cosa (en este orden): bloque literal de WordPress,
    texto, imagen, lista, tabla, HTML, botón, enlace de texto, menú de enlaces, fila, caja o contenedor que se aplana."""
    tag = node.tag
    if tag in OMITIR:
        return []
    if tag == 'wp-raw':     # bloque de WordPress escrito tal cual en el HTML (ver Converter.__init__)
        return [converter.wp_literals[int(node.attrs['data-i'])].strip()]
    if re.fullmatch(TEXT_TAGS, tag):
        return text_block(converter, node)
    if tag == 'img':
        return [elementos.image(converter, node)]
    if tag in ('ul', 'ol') and not is_row(node):
        return [elementos.bullet_list(converter, node)]
    if tag == 'table':
        return [elementos.table(converter, node)]
    if tag in RAW_HTML_TAGS:
        return [elementos.raw_html(converter, node)]
    if tag == 'a' and is_button(node):
        return [spectra.button_group([elementos.button(converter, node)])]
    if tag == 'a' and not is_row(node) and not _contains_image(node):
        return text_block(converter, node, [node])
    if is_row(node) and node.child_nodes and all(_is_text_link(child) for child in node.child_nodes):
        return text_block(converter, node, layout=True)   # menú de enlaces: un texto con display:flex
    if is_row(node):
        return [row(converter, node)]
    is_linked_card = tag == 'a' and node.attrs.get('href')
    if has_box(node) or node.attrs.get('id') or is_linked_card:
        return [box(converter, node)]
    return flow(converter, node)   # contenedor sin estilo propio: se aplana


def _contains_image(node):
    """¿Hay alguna <img> dentro del nodo?"""
    return any(descendant.tag == 'img' for descendant in walk(node))


def _is_text_link(node):
    """¿Es un <a> de solo texto (ni botón ni tarjeta con imagen)?"""
    return node.tag == 'a' and not is_button(node) and not _contains_image(node)


def flow(converter, node):
    """Contenido de un contenedor, en orden: lo en línea seguido se junta en un texto, los botones seguidos en un
    grupo de botones, y cada hijo de bloque se convierte con block()."""
    blocks, inline_run, pending_buttons = [], [], []

    def flush_inline_run():
        nonlocal inline_run
        meaningful = [item for item in inline_run if not (isinstance(item, str) and not item.strip())]
        is_lone_inline_block = (len(meaningful) == 1 and not isinstance(meaningful[0], str)
                                and meaningful[0].style.get('display') == 'inline-block')
        if is_lone_inline_block:
            blocks.extend(text_block(converter, meaningful[0]))   # p. ej. una etiqueta <time> con fondo propio
        elif meaningful:
            blocks.extend(text_block(converter, node, inline_run))
        inline_run = []

    def flush_buttons():
        nonlocal pending_buttons
        if pending_buttons:
            align = node.style.get('text-align')
            is_flex_column = (node.style.get('display') in ('flex', 'inline-flex')
                              and node.style.get('flex-direction', '').startswith('column'))
            if is_flex_column:   # columna flex centrada
                align = {'center': 'center', 'flex-end': 'right', 'end': 'right'}.get(node.style.get('align-items'), align)
            blocks.append(spectra.button_group(pending_buttons, align=align if align in ('left', 'center', 'right') else 'left',
                                               gap=gaps(node.style, 12)[1]))
        pending_buttons = []

    for child in node.children:
        is_node = not isinstance(child, str)
        if is_node and child.tag in OMITIR:
            continue
        if is_button(child):
            flush_inline_run()
            pending_buttons.append(elementos.button(converter, child))
        elif not is_node and not child.strip():
            if inline_run:   # un espacio entre dos cosas en línea se conserva; al inicio, no
                inline_run.append(child)
        elif is_node and child.tag == 'span' and _is_icon(child) and not any(str(item).strip() for item in inline_run):
            flush_buttons()
            blocks.append(elementos.icon(child))
        elif is_inline(child):
            flush_buttons()
            inline_run.append(child)
        else:
            flush_inline_run()
            flush_buttons()
            blocks.extend(block(converter, child))
    flush_inline_run()
    flush_buttons()
    return blocks


def _is_icon(span):
    """¿El <span> es un ícono (un emoji de config.ICONOS o data-icono="nombre")?"""
    return span.text() in ICONOS or bool(span.attrs.get('data-icono'))


def box(converter, node, block_id=None, **extra_attrs):
    """Contenedor de Spectra en columna para un nodo con caja propia (fondo, borde, padding, id, enlace...).
    extra_attrs: anchos de columna cuando la caja es una columna de una fila."""
    block_id = block_id or spectra.new_block_id()
    attrs, translated, background_css = container_attrs(node)
    attrs['rowGapDesktop'] = gaps(node.style, 12)[0]
    attrs.update(justifyContentDesktop='flex-start', alignItemsDesktop='stretch', **extra_attrs)
    own = node.own_style
    justify = own.get('justify-content')
    is_flex_column = own.get('display') == 'flex' and own.get('flex-direction', '').startswith('column')
    if is_flex_column and justify in ('center', 'flex-end', 'space-between', 'space-around', 'space-evenly'):
        attrs['justifyContentDesktop'] = justify   # columna con el contenido centrado (o repartido) en vertical
        translated.add('justify-content')
    if own.get('max-height') or own.get('overflow-y') in ('auto', 'scroll'):
        # lista con scroll vertical: si Spectra deja flex-wrap, al llenarse se reparte en columnas de lado
        attrs.update(wrapDesktop='nowrap', wrapTablet='nowrap', wrapMobile='nowrap')
        converter.css.add(f'.uagb-block-{block_id}', {'flex-wrap': 'nowrap'})
    _add_link(node, attrs)
    if background_css:
        converter.css.add(f'.uagb-block-{block_id}', {'background': background_css})
    converter.css.add_leftover(node, f'.uagb-block-{block_id}', translated)
    return spectra.container(flow(converter, node), block_id=block_id, anchor=node.attrs.get('id'),
                             class_name=converter.class_names(node), **attrs)


def _add_link(node, attrs):
    """Si el nodo es un <a href>, el contenedor entero queda enlazado (tarjeta clicable)."""
    if node.tag == 'a' and node.attrs.get('href'):
        attrs.update(htmlTag='a', htmlTagLink={'url': wordpress_href(node.attrs['href'])})


def row(converter, node):
    """Fila flex de Spectra con un contenedor por hijo.

    Con columnas (grid, o flex:1 en todos los hijos): anchos y hueco en %, para que anchos + huecos sumen 100 a
    cualquier tamaño y nada salte de línea antes de tiempo. Sin columnas: cada hijo mide lo que su contenido."""
    children = [child for child in node.child_nodes if child.tag not in OMITIR]
    style, mobile_style = node.style, node.mobile_style
    row_gap, column_gap = gaps(style)
    stacks_on_mobile = mobile_style.get('flex-direction', '').startswith('column') or mobile_style.get('display') == 'block'
    is_grid = style.get('display', '').endswith('grid')
    align = ALIGN_ITEMS_VALUES.get(style.get('align-items', 'stretch'), 'stretch')
    block_id = spectra.new_block_id()
    attrs, translated, background_css = container_attrs(node)
    attrs.update(directionDesktop='row', alignItemsDesktop=align, rowGapDesktop=row_gap)
    mobile_align = {**ALIGN_ITEMS_VALUES, 'stretch': 'stretch'}.get(mobile_style.get('align-items'))
    if mobile_align and mobile_align != align:   # alineación propia del @media de celular
        attrs['alignItemsMobile'] = mobile_align
    _add_link(node, attrs)   # fila enlazada (tarjeta horizontal clicable)
    if align == 'stretch':
        attrs['equalHeight'] = True

    has_columns = is_grid or (children and all(_grows(child) for child in children))
    if has_columns:
        columns = _row_with_columns(converter, node, children, block_id, attrs, is_grid, stacks_on_mobile, column_gap)
    else:
        columns = _row_sized_by_content(converter, node, children, block_id, attrs, stacks_on_mobile, mobile_align, column_gap)
    # el padding de cada columna va por dentro de su ancho (si no, anchos + padding pasan de 100)
    converter.css.add(f'.uagb-block-{block_id} > .wp-block-uagb-container', {'box-sizing': 'border-box'})
    if background_css:
        converter.css.add(f'.uagb-block-{block_id}', {'background': background_css})
    converter.css.add_leftover(node, f'.uagb-block-{block_id}', translated)
    return spectra.container(columns, block_id=block_id, anchor=node.attrs.get('id'),
                             class_name=converter.class_names(node), **attrs)


def _grows(child):
    """¿El hijo de una fila crece para llenar el espacio (flex: 1, flex-grow > 0)?"""
    flex_grow = (child.own_style.get('flex', '').split() or ['0'])[0]
    return flex_grow not in ('0', 'none', 'auto', 'initial') or float(child.own_style.get('flex-grow', 0) or 0) > 0


def _flex_ratio(child):
    """Proporción con la que crece un hijo de una fila ('flex: 2' -> '2')."""
    return (child.own_style.get('flex', '').split() or [child.own_style.get('flex-grow', '1')])[0]


def _row_column(converter, child, **widths):
    """Contenedor de una columna de la fila. Una imagen o una fila anidada se envuelven en un contenedor sin padding;
    cualquier otro hijo es una caja (box) con los anchos de la columna."""
    if child.tag == 'img' or is_row(child):
        inner_blocks = [elementos.image(converter, child)] if child.tag == 'img' else block(converter, child)
        column_id = spectra.new_block_id()
        if child.tag != 'img':   # la fila envuelta ocupa todo el alto de su columna (tarjetas de igual altura)
            converter.css.add(f'.uagb-block-{column_id} > .wp-block-uagb-container', {'flex': '1 1 auto', 'align-self': 'stretch'})
        hide_attrs = mobile_hide_attrs(child) if child.tag == 'img' else {}
        return column_id, spectra.container(inner_blocks, block_id=column_id, topPaddingDesktop=0, bottomPaddingDesktop=0,
                                            leftPaddingDesktop=0, rightPaddingDesktop=0, **widths, **hide_attrs)
    column_id = spectra.new_block_id()
    return column_id, box(converter, child, block_id=column_id, **widths)


def _row_with_columns(converter, node, children, block_id, attrs, is_grid, stacks_on_mobile, column_gap):
    """Fila con columnas de ancho fijo en % para escritorio, tablet y celular (desde grid-template-columns o desde
    las proporciones flex). Agrega a attrs el wrap y los huecos, y devuelve los bloques de las columnas."""
    style, mobile_style = node.style, node.mobile_style
    mobile_breakpoint = converter.css.mobile_breakpoint
    if is_grid:
        desktop = grid_columns(style, PX_ESCRITORIO, len(children))
        tablet_style = mobile_style if mobile_breakpoint >= 768 else style   # el @media de celular también cubre tablet
        tablet = grid_columns(tablet_style, PX_TABLET, len(children)) or desktop
        mobile = grid_columns(mobile_style, PX_CELULAR, len(children)) or desktop
    else:
        desktop = [f'{_flex_ratio(child)}fr' for child in children]
        tablet = mobile = ['1fr'] if stacks_on_mobile else desktop
    gap_percent = max(1, round(column_gap / PX_ESCRITORIO * 100))   # hueco en % del ancho de la fila
    desktop_widths = percent_widths(desktop, gap_percent, PX_ESCRITORIO)
    tablet_widths = percent_widths(tablet, gap_percent, PX_TABLET)
    mobile_widths = percent_widths(mobile, gap_percent, PX_CELULAR)
    columns = []
    for index, child in enumerate(children):
        # si hay más hijos que columnas, se repite el patrón (fila que salta de línea)
        desktop_width = desktop_widths[index % len(desktop_widths)]
        mobile_width = mobile_widths[index % len(mobile_widths)]
        column_id, column = _row_column(converter, child, widthDesktop=desktop_width,
                                        widthTablet=tablet_widths[index % len(tablet_widths)], widthMobile=mobile_width)
        columns.append(column)
        if mobile_width != desktop_width:   # ancho de celular también en CSS (por si Spectra no aplica widthMobile)
            converter.css.add(f'.uagb-block-{column_id}', {'width': f'{mobile_width}%', 'max-width': f'{mobile_width}%'},
                              mobile_breakpoint)
    if len(mobile) == 1:   # una sola columna en celular: apilar con CSS explícito
        converter.css.add(f'.uagb-block-{block_id}', {'flex-direction': 'column', 'flex-wrap': 'nowrap'}, mobile_breakpoint)
    attrs.update(wrapDesktop='wrap', wrapTablet='wrap', wrapMobile='wrap', justifyContentDesktop='flex-start',
                 columnGapDesktop=gap_percent, columnGapTablet=gap_percent, columnGapMobile=gap_percent, columnGapType='%',
                 directionMobile='column' if len(mobile) == 1 else 'row')
    return columns


def _row_sized_by_content(converter, node, children, block_id, attrs, stacks_on_mobile, mobile_align, column_gap):
    """Fila donde cada hijo mide lo que su contenido (con su flex propio). Agrega a attrs la dirección, el wrap y
    la alineación, y devuelve los bloques de las columnas."""
    mobile_breakpoint = converter.css.mobile_breakpoint
    style, mobile_style = node.style, node.mobile_style
    columns = []
    for child in children:
        column_id, column = _row_column(converter, child)
        converter.css.add(f'.uagb-block-{column_id}', {'width': 'auto !important', 'flex': child.own_style.get('flex', '0 1 auto')})
        mobile_flex = child.own_mobile_style.get('flex')
        if mobile_flex not in (None, child.own_style.get('flex')):   # flex propio del @media de celular
            converter.css.add(f'.uagb-block-{column_id}', {'flex': mobile_flex}, mobile_breakpoint)
        columns.append(column)
    justify = JUSTIFY_CONTENT_VALUES.get(style.get('justify-content'), 'flex-start')
    wrap = 'wrap' if style.get('flex-wrap') == 'wrap' else 'nowrap'
    # childrenWidthDesktop auto: cada hijo mide lo que su contenido (si no, Spectra les pone 100% y se apilan)
    attrs.update(directionMobile='column' if stacks_on_mobile else 'row', wrapDesktop=wrap, wrapMobile=wrap,
                 justifyContentDesktop=justify, columnGapDesktop=column_gap, childrenWidthDesktop='auto')
    if stacks_on_mobile:   # además del atributo de Spectra, CSS explícito: en celular la fila se apila sí o sí
        mobile_direction = mobile_style.get('flex-direction', '')
        converter.css.add(f'.uagb-block-{block_id}',
                          {'flex-direction': mobile_direction if mobile_direction.startswith('column') else 'column',
                           'align-items': mobile_align or 'stretch'}, mobile_breakpoint)
    return columns


def section(converter, node, loose_blocks=None):
    """Sección a todo el ancho con el contenido centrado (ANCHO_CONTENIDO %).

    loose_blocks=None: la sección es el nodo (su fondo, padding, id y clases).
    loose_blocks=[...]: bloques sueltos que no estaban en ninguna sección; node es su padre (body/main)."""
    block_id = spectra.new_block_id()
    if loose_blocks is None:
        attrs, translated, background_css = container_attrs(node, root=True)
        if background_css:
            converter.css.add(f'.uagb-block-{block_id}', {'background': background_css})
        converter.css.add_leftover(node, f'.uagb-block-{block_id}', translated)
        content = [row(converter, node)] if is_row(node) else flow(converter, node)
        class_name = ' '.join(name for name in (converter.class_names(node), converter.class_prefix + 'page') if name)
        anchor = node.attrs.get('id')
        if not attrs.get('topPaddingDesktop') and not attrs.get('bottomPaddingDesktop'):   # sin padding en el CSS
            attrs.update(topPaddingDesktop=SECCION_SIN_PADDING, bottomPaddingDesktop=SECCION_SIN_PADDING)
        if 'topPaddingMobile' not in attrs:
            attrs.update(topPaddingMobile=round(attrs['topPaddingDesktop'] * .7),
                         bottomPaddingMobile=round(attrs['bottomPaddingDesktop'] * .7))
    else:
        content = loose_blocks
        attrs = dict(topPaddingDesktop=50, bottomPaddingDesktop=70, topPaddingMobile=35, bottomPaddingMobile=50)
        class_name, anchor = converter.class_prefix + 'page', None
    attrs.update(leftPaddingDesktop=0, rightPaddingDesktop=0)
    # sección sin padding a los lados en el CSS (p. ej. publicaciones + ¿cómo vincularse?): contenido al 100%
    padding = four_sides(node.style.get('padding')) if node is not None else None
    is_full_width = bool(padding) and to_px(padding[1]) == 0 and to_px(padding[3]) == 0
    desktop_width, tablet_width, mobile_width = (100, 100, 100) if is_full_width else (ANCHO_CONTENIDO, 90, 92)
    inner = spectra.container(content, root=True, widthDesktop=desktop_width, widthTablet=tablet_width,
                              widthMobile=mobile_width, topPaddingDesktop=0, bottomPaddingDesktop=0,
                              leftPaddingDesktop=0, rightPaddingDesktop=0,
                              rowGapDesktop=gaps(node.style)[0] if node is not None else 20)
    return spectra.container([inner], block_id=block_id, root=True, full=True, anchor=anchor, class_name=class_name, **attrs)


def page(converter):
    """Toda la página -> lista de secciones. Cada hijo de <body>/<main> que sea <section> o tenga caja propia es una
    sección; los elementos sueltos entre secciones se juntan en una sección sin estilo. Un <main> (o un div sin
    caja que contiene secciones) se recorre por dentro."""
    body = next((node for node in walk(converter.root) if node.tag == 'body'), converter.root)
    sections = []

    def add_sections(parent):
        loose = []

        def flush_loose():
            nonlocal loose
            blocks = [converted for child in loose for converted in block(converter, child)]
            if blocks:
                sections.append(section(converter, parent, blocks))
            loose = []

        for child in parent.child_nodes:
            if child.tag in OMITIR:
                continue
            wraps_sections = (not has_box(child) and not child.attrs.get('id')
                              and any(grandchild.tag == 'section' for grandchild in child.child_nodes))
            if child.tag == 'main' or wraps_sections:
                flush_loose()
                add_sections(child)
            elif child.tag == 'section' or has_box(child):
                flush_loose()
                sections.append(section(converter, child))
            else:
                loose.append(child)
        flush_loose()
    add_sections(body)
    return sections
