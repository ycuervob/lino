"""Árbol del HTML: cada etiqueta es un Node que, después de leer el CSS, guarda sus estilos calculados."""
import re
from html.parser import HTMLParser

VOID_TAGS = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'wbr'}
INLINE_TAGS = {'a', 'abbr', 'b', 'br', 'code', 'em', 'i', 'mark', 'small', 'span', 'strong', 'sub', 'sup', 'time', 'u', 'wbr'}


class Node:
    """Una etiqueta del HTML.

    children: textos (str) y nodos hijos, en orden. child_nodes: solo los nodos.
    Los estilos los llena estilos.Stylesheet.compute():
      own_style / own_mobile_style: lo que las reglas CSS le dan a este nodo (escritorio / @media de celular).
      style / mobile_style: lo propio más lo heredado del padre (color, fuente...).
      states / mobile_states: {':hover': {...}, '::before': {...}}.
    """

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs or []), parent, []
        self.style = self.mobile_style = self.own_style = self.own_mobile_style = self.states = self.mobile_states = {}

    @property
    def classes(self):
        """Clases del atributo class, como lista."""
        return (self.attrs.get('class') or '').split()

    @property
    def child_nodes(self):
        """Solo los nodos hijos (sin los textos sueltos)."""
        return [child for child in self.children if isinstance(child, Node)]

    def text(self):
        """Todo el texto de adentro, con los espacios normalizados."""
        parts = (child if isinstance(child, str) else child.text() for child in self.children)
        return re.sub(r'\s+', ' ', ''.join(parts)).strip()


class TreeBuilder(HTMLParser):
    """Arma el árbol de Nodes mientras lee el HTML. La raíz queda en self.root."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node('#root')

    def handle_starttag(self, tag, attrs):
        """Abre un nodo hijo del actual (y entra en él, salvo que sea una etiqueta sin cierre como <img>)."""
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID_TAGS:
            self.current = node

    def handle_endtag(self, tag):
        """Cierra hasta el nodo abierto con esa etiqueta (tolera etiquetas que quedaron sin cerrar)."""
        node = self.current
        while node.tag != tag and node.parent:
            node = node.parent
        if node.parent:
            self.current = node.parent

    def handle_data(self, data):
        """Guarda el texto suelto dentro del nodo actual."""
        self.current.children.append(data)


def walk(node):
    """Todos los nodos descendientes, en orden de documento."""
    for child in node.child_nodes:
        yield child
        yield from walk(child)
