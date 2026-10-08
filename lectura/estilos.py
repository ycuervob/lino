"""Lectura del CSS: reglas, variables, selectores y estilo calculado de cada nodo."""
import os, re

from config import avisos
from lectura.arbol import walk

# propiedades que un nodo hereda de su padre si no las define
INHERITED = {'color', 'font-family', 'font-size', 'font-weight', 'font-style', 'line-height', 'text-align',
             'letter-spacing', 'text-transform', 'list-style', 'list-style-type', 'white-space', 'word-spacing', 'visibility'}


# ---------- texto CSS ----------

def split_outside_parens(text, separator):
    """Divide text por separator sin cortar lo que está entre paréntesis: 'a, rgb(1,2,3)' -> ['a', ' rgb(1,2,3)'].
    Con separator ' ' descarta los pedazos vacíos (varios espacios seguidos)."""
    parts, depth, current = [], 0, ''
    for char in text:
        depth += (char == '(') - (char == ')')
        if char == separator and depth == 0:
            parts.append(current)
            current = ''
        else:
            current += char
    parts.append(current)
    return [part for part in parts if part.strip()] if separator == ' ' else parts


def parse_declarations(text):
    """'color: red; padding: 4px !important' -> {'color': 'red', 'padding': '4px'} (sin !important)."""
    declarations = {}
    for part in split_outside_parens(text, ';'):
        if ':' in part:
            prop, value = part.split(':', 1)
            declarations[prop.strip().lower()] = re.sub(r'\s*!important', '', value).strip()
    return declarations


def css_blocks(text):
    """'sel { ... } @media x { ... }' -> [(cabecera, cuerpo)] respetando llaves anidadas."""
    pos, blocks = 0, []
    while pos < len(text):
        open_brace = text.find('{', pos)
        if open_brace < 0:
            break
        header, depth, end = text[pos:open_brace].strip(), 1, open_brace + 1
        while end < len(text) and depth:
            depth += (text[end] == '{') - (text[end] == '}')
            end += 1
        blocks.append((header, text[open_brace + 1:end - 1]))
        pos = end
    return blocks


def parse_stylesheet(text):
    """Hoja de estilos completa -> (rules, at_blocks).

    rules: [(selector, declaraciones, breakpoint)] donde breakpoint es el max-width del @media de celular, o None.
    at_blocks: [(cabecera, cuerpo)] de los @ que no se traducen (keyframes, supports, media raros) y se copian.
    Un @media solo con min-width se toma como escritorio (lo normal es que repita lo de fuera del @media)."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    rules, at_blocks = [], []
    for header, body in css_blocks(text):
        if header.startswith('@media'):
            max_width, min_width = re.search(r'max-width\s*:\s*(\d+)', header), re.search(r'min-width', header)
            if max_width and not min_width and 'prefers' not in header:
                breakpoint = int(max_width.group(1))
                rules += [(selector, parse_declarations(decls), breakpoint) for selector, decls in css_blocks(body)]
            elif min_width and not max_width and 'prefers' not in header:
                rules += [(selector, parse_declarations(decls), None) for selector, decls in css_blocks(body)]
            else:
                at_blocks.append((header, body))
        elif header.startswith('@'):
            if not header.startswith(('@import', '@charset', '@font-face')):
                at_blocks.append((header, body))
        else:
            rules.append((header, parse_declarations(body), None))
    return rules, at_blocks


def resolve_vars(value, variables, depth=0):
    """Reemplaza var(--x, respaldo) por su valor (también variables que usan otras, hasta 5 niveles)."""
    if 'var(' not in value or depth > 5:
        return value
    value = re.sub(r'var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)',
                   lambda m: variables.get(m.group(1), (m.group(2) or '').strip()), value)
    return resolve_vars(value, variables, depth + 1)


# ---------- selectores ----------

# una parte de selector sin espacios: etiqueta opcional + .clases, #ids, [atributos] y :pseudos
COMPOUND_SELECTOR = re.compile(r'(?P<tag>[a-zA-Z][\w-]*|\*)?(?P<rest>(?:[.#][\w-]+|\[[^\]]*\]|::?[\w-]+(?:\([^)]*\))?)*)')
STRUCTURAL_PSEUDO = re.compile(r':(nth-child|nth-of-type|first-child|last-child|first-of-type|last-of-type)')


def parse_selector(selector):
    """'main > .tarjeta:hover' -> (parts, state) o (None, None) si no se soporta.

    parts: [(combinador, etiqueta, ids, clases, pseudos_estructurales)] de izquierda a derecha.
    state: lo que queda al final y no es estructural (':hover', '::before'...); va como CSS aparte.
    No se soportan + ni ~, ni pseudoclases como :not() en medio del selector."""
    pieces, combinator = [], ' '
    # lo que está entre paréntesis va entero con su parte: el + de :nth-child(2n+1) no es un combinador
    for symbol, compound in re.findall(r'\s*([>+~])\s*|\s+|((?:[^\s>+~(]|\([^)]*\))+)', selector.strip()):
        if symbol:
            combinator = symbol
        elif compound:
            pieces.append((combinator, compound))
            combinator = ' '
    if not pieces or any(comb in '+~' for comb, _ in pieces):
        return None, None
    parts, state = [], ''
    for index, (combinator, compound) in enumerate(pieces):
        match = COMPOUND_SELECTOR.fullmatch(compound)
        if not match:
            return None, None
        rest = match.group('rest')
        structural = []
        for pseudo in re.findall(r'(::?[\w-]+(?:\([^)]*\))?)', rest):
            if STRUCTURAL_PSEUDO.match(pseudo):
                structural.append(pseudo)
            elif index == len(pieces) - 1:
                state += pseudo
            else:
                return None, None
        parts.append((combinator, (match.group('tag') or '*').lower(), re.findall(r'#([\w-]+)', rest),
                      re.findall(r'\.([\w-]+)', rest), structural))
    return parts, state


def specificity(parts):
    """(ids, clases + pseudos, etiquetas): el orden en que se pisan las reglas."""
    return (sum(len(part[2]) for part in parts),
            sum(len(part[3]) + len(part[4]) for part in parts),
            sum(part[1] != '*' for part in parts))


def nth_matches(expression, position):
    """¿La posición (desde 1) cumple 'odd', 'even', '3' o 'an+b'? Las formas que no entiende dan False."""
    expression = expression.replace(' ', '')
    if expression in ('odd', 'even'):
        return position % 2 == (1 if expression == 'odd' else 0)
    if expression.isdigit():
        return position == int(expression)
    match = re.fullmatch(r'(-?\d*)n([+-]\d+)?', expression)
    if not match:
        return False
    step = {'': 1, '-': -1}.get(match.group(1))
    step = int(match.group(1)) if step is None else step
    offset = int(match.group(2) or 0)
    if not step:
        return position == offset
    return (position - offset) % step == 0 and (position - offset) // step >= 0


def matches_compound(node, tag, ids, classes, structural):
    """¿El nodo cumple una parte del selector (etiqueta, #id, .clases y :nth-child y similares)?"""
    if node.tag.startswith('#') or (tag != '*' and node.tag != tag):
        return False
    if any(node.attrs.get('id') != id_ for id_ in ids) or any(cls not in node.classes for cls in classes):
        return False
    if structural:
        siblings = node.parent.child_nodes if node.parent else [node]
        same_tag = [sibling for sibling in siblings if sibling.tag == node.tag]
        position, position_in_tag = siblings.index(node) + 1, same_tag.index(node) + 1
        for pseudo in structural:
            name, _, argument = pseudo[1:].partition('(')
            argument = argument.rstrip(')')
            ok = {'nth-child': lambda: nth_matches(argument, position),
                  'nth-of-type': lambda: nth_matches(argument, position_in_tag),
                  'first-child': lambda: position == 1,
                  'last-child': lambda: position == len(siblings),
                  'first-of-type': lambda: position_in_tag == 1,
                  'last-of-type': lambda: position_in_tag == len(same_tag)}[name]()
            if not ok:
                return False
    return True


def matches(node, parts, index=None):
    """¿El selector (ya leído con parse_selector) aplica a este nodo? Se compara de derecha a izquierda."""
    index = len(parts) - 1 if index is None else index
    combinator, tag, ids, classes, structural = parts[index]
    if not matches_compound(node, tag, ids, classes, structural):
        return False
    if index == 0:
        return True
    ancestor = node.parent
    if combinator == '>':
        return ancestor is not None and matches(ancestor, parts, index - 1)
    while ancestor is not None:
        if matches(ancestor, parts, index - 1):
            return True
        ancestor = ancestor.parent
    return False


# ---------- hoja de la página ----------

class Stylesheet:
    """Todo el CSS de una página, listo para calcular el estilo de cada nodo.

    google_fonts: familias enlazadas desde Google Fonts.
    variables: --variables de :root / html.
    mobile_breakpoint: max-width del @media de celular (el mayor que aparezca; 768 si no hay).
    at_blocks: @ que no se traducen y se copian tal cual al CSS de salida.
    rules: [(especificidad, orden, partes_selector, estado, declaraciones, breakpoint)] ordenadas por cascada."""

    def __init__(self, root, base_dir):
        """Junta las hojas enlazadas (rutas relativas a base_dir) y los <style>, y prepara las reglas."""
        css_text, self.google_fonts = '', set()
        for node in walk(root):
            if node.tag == 'link' and 'stylesheet' in (node.attrs.get('rel') or ''):
                href = node.attrs.get('href', '')
                if 'fonts.googleapis.com' in href:
                    self.google_fonts |= {family.split(':')[0].replace('+', ' ')
                                          for family in re.findall(r'family=([^&]+)', href)}
                elif not href.startswith(('http:', 'https:', '//')):
                    try:
                        css_text += open(os.path.join(base_dir, href), encoding='utf-8').read() + '\n'
                    except OSError:
                        avisos.append(f'no pude leer la hoja de estilos {href}')
            elif node.tag == 'style':
                css_text += node.text() + '\n'
        rules, self.at_blocks = parse_stylesheet(css_text)
        self.variables = {}
        for selector, declarations, breakpoint in rules:
            if selector.strip() in (':root', 'html') and breakpoint is None:
                self.variables.update({k: v for k, v in declarations.items() if k.startswith('--')})
        self.mobile_breakpoint = max([breakpoint for _, _, breakpoint in rules if breakpoint] or [768])
        self.rules = []
        for order, (selector, declarations, breakpoint) in enumerate(rules):
            declarations = {prop: resolve_vars(value, self.variables)
                            for prop, value in declarations.items() if not prop.startswith('--')}
            for single_selector in split_outside_parens(selector, ','):
                if single_selector.strip() in (':root', '*', '*::before', '*::after') or not declarations:
                    continue
                parts, state = parse_selector(single_selector)
                if parts is None:
                    avisos.append(f'selector no soportado, se ignora: {single_selector.strip()}')
                    continue
                self.rules.append((specificity(parts), order, parts, state, declarations, breakpoint))
        self.rules.sort(key=lambda rule: (rule[0], rule[1]))

    def compute(self, root):
        """Llena en cada nodo own_style, own_mobile_style, style, mobile_style, states y mobile_states
        (ver arbol.Node). El style="" en línea pisa a las reglas."""
        def visit(node, parent_style, parent_mobile_style):
            own, own_mobile, states, mobile_states = {}, {}, {}, {}
            for _, _, parts, state, declarations, breakpoint in self.rules:
                if not matches(node, parts):
                    continue
                if state:
                    (states if breakpoint is None else mobile_states).setdefault(state, {}).update(declarations)
                elif breakpoint is None:
                    own.update(declarations)
                    own_mobile.update(declarations)
                else:
                    own_mobile.update(declarations)
            inline = {prop: resolve_vars(value, self.variables)
                      for prop, value in parse_declarations(node.attrs.get('style', '')).items()}
            own.update(inline)
            own_mobile.update(inline)
            node.own_style, node.own_mobile_style, node.states, node.mobile_states = own, own_mobile, states, mobile_states
            node.style = {**{k: v for k, v in parent_style.items() if k in INHERITED}, **own}
            node.mobile_style = {**{k: v for k, v in parent_mobile_style.items() if k in INHERITED}, **own_mobile}
            for child in node.child_nodes:
                visit(child, node.style, node.mobile_style)
        for child in root.child_nodes:
            visit(child, {}, {})
