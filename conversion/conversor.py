"""Punto de entrada de la conversión: lee una página HTML + CSS y la entrega como bloques de Spectra.

El trabajo está repartido así:
  lectura/arbol.py           HTML -> árbol de nodos
  lectura/estilos.py         CSS -> estilo calculado de cada nodo
  lectura/valores.py         valores CSS -> números y piezas para Spectra
  conversion/clasificar.py   ¿qué es este nodo? (texto en línea, botón, fila, caja...)
  conversion/atributos.py    CSS -> atributos de Spectra
  conversion/textos.py       títulos, párrafos y HTML en línea
  conversion/elementos.py    imagen, botón, ícono, lista, tabla, HTML personalizado
  conversion/estructura.py   secciones, filas, cajas y el recorrido que decide qué bloque le toca a cada elemento
  salida/hoja_css.py         el CSS que Spectra no guarda como atributo
  salida/bloques.py          el marcado exacto de cada bloque
"""
import os, re

from conversion import estructura
from lectura.arbol import TreeBuilder
from lectura.estilos import Stylesheet
from salida.hoja_css import ExtraCss

# bloque de WordPress escrito tal cual en el HTML: <!-- wp:x {...} /--> o <!-- wp:x -->...<!-- /wp:x -->
WP_LITERAL_BLOCK = re.compile(r'<!--\s*wp:[\w/-]+(?:\s+\{.*?\})?\s*/-->'
                              r'|<!--\s*wp:([\w/-]+)(?:\s+\{.*?\})?\s*-->.*?<!--\s*/wp:\1\s*-->', re.S)


class Converter:
    """Una página en conversión. Las funciones de estructura.py, textos.py y elementos.py la reciben para usar:
    base_dir (carpeta del HTML, para leer imágenes), class_prefix, stylesheet (estilos calculados),
    css (hoja_css.ExtraCss de salida), wp_literals (bloques de WordPress del HTML) y root (árbol)."""

    def __init__(self, path, class_prefix):
        """Lee el HTML, aparta los bloques de WordPress literales, arma el árbol y calcula los estilos."""
        self.base_dir, self.class_prefix = os.path.dirname(path), class_prefix
        self.wp_literals = []

        def protect_literal(match):
            # el comentario no sobrevive al parser de HTML: se cambia por una etiqueta que lo señala
            self.wp_literals.append(match.group(0))
            return f'<wp-raw data-i="{len(self.wp_literals) - 1}"></wp-raw>'
        html = WP_LITERAL_BLOCK.sub(protect_literal, open(path, encoding='utf-8').read())
        builder = TreeBuilder()
        builder.feed(html)
        self.root = builder.root
        self.stylesheet = Stylesheet(self.root, self.base_dir)
        self.stylesheet.compute(self.root)
        self.css = ExtraCss(self.stylesheet, class_prefix, self.root)

    def class_names(self, node):
        """Clases originales del nodo con el prefijo (para copiarlas al bloque), o None si no tiene."""
        return ' '.join(self.class_prefix + name for name in node.classes) or None

    def blocks(self):
        """Toda la página como lista de bloques (texto listo para el editor de código de WordPress)."""
        return estructura.page(self)

    def extra_css(self):
        """El CSS que no cupo en atributos. Llamar después de blocks(): se junta mientras se convierten."""
        return self.css.render()
