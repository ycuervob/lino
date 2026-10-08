"""Convierte una página HTML + su CSS en bloques de Spectra para WordPress.

Uso:
    python3 lino pagina.html [otra.html ...] [--salida carpeta] [--css-aparte] [--prefijo xx-]

Escribe <pagina>.txt (se pega en el editor de código de WordPress) en la carpeta desde donde se ejecuta.
    --salida       carpeta donde guardar el resultado (se crea si no existe).
    --css-aparte   el CSS que Spectra no puede guardar como atributo va a <pagina>.css
                   (para "CSS adicional" del tema) en vez de un bloque <style> dentro de la página.
    --prefijo      prefijo de las clases originales copiadas a los bloques (por defecto "lino-").

Cómo decide:
  * Estilos: lee <link rel="stylesheet">, <style> y style="" (con var(--x); @media max-width = celular) y calcula
    el estilo de cada elemento (especificidad, herencia, :nth-child/:nth-of-type).
  * Estructura: cada hijo de <body>/<main> que sea <section> o tenga fondo/borde/padding propio es una sección a todo
    el ancho; display:grid/flex en fila => fila de columnas (anchos desde grid-template-columns); <a> con fondo o borde
    => botón; h1–h6/p => título/texto; ul/ol => lista; img => imagen; table => tabla; iframe y otros => bloque HTML.
  * Lo que Spectra guarda como atributo (fondo, color, padding, bordes, radios, sombra, tipografía, anchos, ocultar en
    celular) va al bloque. El resto (:hover, ::before, transiciones, clip-path, animaciones...) se escribe como CSS
    apuntando a la clase única de cada bloque (.uagb-block-XXXX).
"""
import os, random, re, sys, zlib
sys.dont_write_bytecode = True  # no crear __pycache__ en la carpeta

from config import avisos
from conversion.conversor import Converter
from salida import bloques as spectra
from salida.validar import check


def take_option(args, name, default):
    """Saca '--name valor' de args (si está) y devuelve el valor, o default."""
    if name not in args:
        return default
    index = args.index(name)
    value = args[index + 1]
    del args[index:index + 2]
    return value


def output_name(path):
    """'Mi Página.html' -> 'mi-p-gina' (nombre de los archivos de salida)."""
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    return re.sub(r'[^a-z0-9]+', '-', stem).strip('-')


def convert_file(path, output_dir, class_prefix, separate_css):
    """Convierte una página, escribe <nombre>.txt (y <nombre>.css con --css-aparte) e imprime el resumen y avisos."""
    random.seed(zlib.crc32(os.path.basename(path).encode()))   # mismos IDs en cada ejecución -> diffs limpios
    avisos.clear()
    converter = Converter(path, class_prefix)
    blocks = converter.blocks()
    css = converter.extra_css()
    name = output_name(path)
    if separate_css:
        open(os.path.join(output_dir, name + '.css'), 'w', encoding='utf-8').write(css + '\n')
    elif css:
        blocks.insert(0, spectra.html_block(f'<style>\n{css}\n</style>'))
    text = '\n\n'.join(blocks) + '\n'
    open(os.path.join(output_dir, name + '.txt'), 'w', encoding='utf-8').write(text)
    errors = check(text)
    print(f'{path} -> {os.path.join(output_dir, name)}.txt' + (f' + {name}.css' if separate_css else '') +
          f'  ({text.count("<!-- wp:")} bloques, {len(css.splitlines())} líneas de CSS)' + (f'  ERRORES: {errors}' if errors else ''))
    for warning in dict.fromkeys(avisos):
        print('   aviso:', warning)


def main():
    """Lee los argumentos de la terminal y convierte cada página."""
    args = sys.argv[1:]
    separate_css = '--css-aparte' in args
    class_prefix = take_option(args, '--prefijo', 'lino-')
    output_dir = take_option(args, '--salida', None)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = os.getcwd()   # por defecto, el resultado queda donde se ejecuta el comando
    files = [arg for arg in args if not arg.startswith('--')]
    if not files:
        sys.exit(__doc__)
    for path in files:
        convert_file(path, output_dir, class_prefix, separate_css)


if __name__ == '__main__':
    main()
