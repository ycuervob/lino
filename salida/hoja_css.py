"""CSS de salida: lo que Spectra no puede guardar como atributo de bloque (:hover, ::before, transiciones,
alturas de fotos, scrolls, ajustes de celular...). Se escribe apuntando a la clase única de cada bloque."""
import os, re

from config import avisos
from lectura.arbol import Node, walk
from lectura.estilos import css_blocks, parse_declarations, resolve_vars, split_outside_parens
from lectura.valores import media_url, without_grid

# maquetación que Spectra resuelve con sus propios atributos (en contenedores no se copia como CSS)
LAYOUT_PROPS = {'display', 'grid-template-columns', 'grid-template-rows', 'grid-column', 'grid-row', 'gap', 'row-gap',
                'column-gap', 'flex', 'flex-direction', 'flex-wrap', 'flex-basis', 'flex-grow', 'flex-shrink',
                'align-items', 'justify-content', 'align-content', 'width', 'max-width', 'min-width', 'margin',
                'margin-top', 'margin-bottom', 'margin-left', 'margin-right', 'box-sizing', 'place-items'}
MARGIN_PROPS = {'margin', 'margin-top', 'margin-bottom'}
# cambios de celular que Spectra no guarda como atributo (p. ej. etiquetas que en celular se estiran y se redondean menos)
MOBILE_ONLY_CSS = {'flex-grow', 'gap', 'row-gap', 'column-gap', 'border-radius', 'flex-direction', 'align-items'}


class ExtraCss:
    """Junta reglas (selector, declaraciones, breakpoint) mientras se convierten los bloques y al final las escribe
    agrupadas, con !important, más los bloques @ que se copian tal cual."""

    def __init__(self, stylesheet, class_prefix, root):
        """stylesheet: estilos.Stylesheet de la página; class_prefix: prefijo de las clases copiadas; root: árbol."""
        self.stylesheet, self.class_prefix, self.root = stylesheet, class_prefix, root
        self.rules = []   # [(selector, declaraciones, breakpoint o None)]

    @property
    def mobile_breakpoint(self):
        """max-width del @media de celular de la página."""
        return self.stylesheet.mobile_breakpoint

    def add(self, selector, declarations, breakpoint=None):
        """Agrega una regla (si tiene declaraciones). breakpoint: va dentro de @media (max-width: breakpoint)."""
        if declarations:
            self.rules.append((selector, without_grid(dict(declarations)), breakpoint))

    def add_leftover(self, node, target, translated, layout=True):
        """CSS propio del nodo que no se tradujo a atributos, sus estados (:hover, ::before...) y lo que cambia en
        celular, todo apuntando a target.
        translated: propiedades que ya quedaron como atributo. layout=True: el bloque es un contenedor y su
        maquetación (display, flex, anchos, márgenes) la resuelve Spectra; con False solo se omiten los márgenes."""
        skipped = translated | (LAYOUT_PROPS if layout else MARGIN_PROPS)

        def untranslated(declarations):
            return {prop: value for prop, value in declarations.items() if prop not in skipped}

        own = node.own_style
        self.add(target, untranslated(own))
        if layout and own.get('display') == 'flex' and any(state in ('::before', '::after') for state in node.states):
            # título con raya (h2::after { flex: 1 }): sin el flex del título la raya mide 0 y no se ve
            self.add(target, {prop: own[prop] for prop in ('display', 'align-items', 'justify-content', 'gap') if prop in own})
        if layout and own.get('display') in ('inline-flex', 'inline-block'):
            # contenedor "en línea" (p. ej. un sello de fecha): Spectra lo estira al 100 %, debe medir lo que su contenido
            self.add(target, {'width': 'fit-content', 'max-width': '100%'})
        if layout and node.tag == 'div' and own.get('max-width', '').endswith('px') and (node.parent is None or node.parent.tag != 'section'):
            # bloque de texto angosto (p. ej. el texto de la portada al lado de una imagen): Spectra no tiene atributo
            self.add(target, {'max-width': own['max-width']})
        if layout and node.tag == 'div' and own.get('width', '').endswith('px') and node.parent is not None and node.parent.tag != 'section':
            # caja de ancho fijo (p. ej. una pestaña): Spectra no tiene atributo en px; en celular, su ancho propio si cambia
            self.add(target, {'width': own['width'], 'max-width': '100%'})
            mobile_width = node.own_mobile_style.get('width')
            if mobile_width and mobile_width != own['width']:
                self.add(target, {'width': f'{mobile_width} !important'}, self.mobile_breakpoint)
        if layout and own.get('flex-shrink') == '0':
            # Spectra no tiene atributo para esto: sin él, una lista con max-height aplasta y corta sus tarjetas
            self.add(target, {'flex-shrink': '0'})
        mobile_changes = {prop: value for prop, value in untranslated(node.own_mobile_style).items() if own.get(prop) != value}
        # en celular Spectra no tiene atributo para estas: si cambian respecto al escritorio, van como CSS
        mobile_changes.update({prop: value for prop, value in node.own_mobile_style.items()
                               if prop in MOBILE_ONLY_CSS and own.get(prop) != value})
        mobile_background = node.own_mobile_style.get('background')
        if 'background' in translated and mobile_background and mobile_background != own.get('background'):
            # el fondo de escritorio quedó como atributo; el de celular (p. ej. un degradado más oscuro) va como CSS
            mobile_changes['background'] = re.sub(r'url\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)',
                                                  lambda m: f'url({media_url(m.group(1))})',
                                                  mobile_background)
        self.add(target, mobile_changes, self.mobile_breakpoint)
        for states, breakpoint in ((node.states, None), (node.mobile_states, self.mobile_breakpoint)):
            for state, declarations in states.items():
                selector = ', '.join(part.strip() + state for part in target.split(','))
                # en ::before/::after todo cuenta (son piezas dibujadas solo con CSS)
                kept = {prop: value for prop, value in declarations.items()
                        if state.startswith('::') or prop not in LAYOUT_PROPS}
                self.add(selector, kept, breakpoint)

    def add_descendants(self, parent, target, only=None):
        """CSS de los descendientes que quedan dentro de un mismo bloque (enlaces en un texto, <li> de una lista,
        celdas de una tabla...), con selectores tipo 'target a:nth-of-type(2)'. only: hijos a recorrer."""
        def visit(children, parent_selector):
            for child in children:
                if not isinstance(child, Node):
                    continue
                keeps_display = parent_selector.endswith(('ul', 'ol', 'li'))
                declarations = {prop: value for prop, value in child.own_style.items() if prop != 'display' or keeps_display}
                siblings = child.parent.child_nodes if child.parent else [child]
                same_tag = [sibling for sibling in siblings if sibling.tag == child.tag]
                differs_from_siblings = any(sibling.own_style != child.own_style for sibling in same_tag)
                nth = f':nth-of-type({same_tag.index(child) + 1})' if differs_from_siblings else ''
                selector = f'{parent_selector} {child.tag}{nth}'
                if child.tag == 'span':   # un <span> con color sale como <mark> (y el tema le pone negrita)
                    self.add(f'{selector}, {parent_selector} mark{nth}',
                             {'font-weight': child.style.get('font-weight', '400'), **declarations})
                else:
                    self.add(selector, declarations)
                for state, state_declarations in child.states.items():
                    self.add(selector + state, state_declarations)
                visit(child.children, selector)
        visit(parent.children if only is None else only, target)

    def copy_at_block(self, header, body):
        """Copia un bloque @ (keyframes, supports, @media que no es de celular) con las clases prefijadas, para que
        apunte a las clases copiadas en los bloques. Los selectores sin clase ni id se limitan a la página."""
        if header.startswith('@keyframes'):
            return f'{header}{{{body.strip()}}}'
        parts = []
        for inner_header, inner_body in css_blocks(body):
            if inner_header.startswith('@'):
                parts.append(self.copy_at_block(inner_header, inner_body))
                continue
            selectors = []
            for selector in split_outside_parens(inner_header, ','):
                selector = re.sub(r'(?<![\w-])\.([a-zA-Z_][\w-]*)', lambda m: f'.{self.class_prefix}{m.group(1)}', selector.strip())
                is_global = re.match(r'(html|:root)\b', selector)
                is_scoped = selector.startswith(('.', '#'))
                selectors.append(selector if is_scoped or is_global else f'.{self.class_prefix}page {selector}')
            declarations = without_grid(parse_declarations(resolve_vars(inner_body, self.stylesheet.variables)))
            parts.append(f'{", ".join(selectors)}{{{";".join(f"{prop}:{value}" for prop, value in declarations.items())}}}')
        avisos.append(f'{header} copiado tal cual: revisa en WordPress que sus selectores apliquen')
        return f'{header}{{\n' + '\n'.join(parts) + '\n}'

    def render(self):
        """Texto CSS final: reglas con las mismas declaraciones se juntan en una sola (selectores separados por
        coma), primero escritorio y luego cada @media; al inicio el scroll-* de <html> y al final los bloques @."""
        selectors_by_rule = {}   # (breakpoint, declaraciones) -> [selectores], en orden de aparición
        for selector, declarations, breakpoint in self.rules:
            selectors = selectors_by_rule.setdefault((breakpoint, tuple(declarations.items())), [])
            if selector not in selectors:
                selectors.append(selector)
        lines = []

        # !important: este CSS es justo lo que Spectra no guarda como atributo, y su propio CSS (más específico)
        # lo pisaría: overflow y max-height de los scroll, alto y object-fit de las fotos, anchos flex...
        def important(value):
            return value if '!important' in value else f'{value} !important'

        breakpoints = [None] + sorted({breakpoint for breakpoint, _ in selectors_by_rule if breakpoint})
        for current in breakpoints:
            rules = [f'{", ".join(selectors)}{{{";".join(f"{prop}:{important(value)}" for prop, value in declarations)}}}'
                     for (breakpoint, declarations), selectors in selectors_by_rule.items() if breakpoint == current]
            if rules:
                lines.append('\n'.join(rules) if current is None
                             else f'@media (max-width:{current}px){{\n' + '\n'.join(rules) + '\n}')
        html_node = next((node for node in walk(self.root) if node.tag == 'html'), None)
        scroll = {prop: value for prop, value in (html_node.own_style if html_node else {}).items() if prop.startswith('scroll-')}
        if scroll:
            lines.insert(0, 'html{' + ';'.join(f'{prop}:{value}' for prop, value in scroll.items()) + '}')
        lines += [self.copy_at_block(header, body) for header, body in self.stylesheet.at_blocks]
        return '\n'.join(lines)
