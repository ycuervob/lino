"""Ajustes del conversor: qué se omite, anchos, íconos y rutas de WordPress."""

OMITIR = {'footer', 'script', 'style', 'link', 'meta', 'title', 'head', 'summary', 'noscript'}
ANCHO_CONTENIDO = 80      # % de ancho del contenido centrado dentro de cada sección
SECCION_SIN_PADDING = 40  # px arriba y abajo cuando una sección no define padding en su CSS
PX_ESCRITORIO, PX_TABLET, PX_CELULAR = 1000, 700, 343   # ancho útil para calcular cuántas columnas caben
ICONOS = {'🧬': 'dna', '🔬': 'microscope', '🤖': 'robot', '📊': 'chart-column', '📷': 'camera', '💻': 'laptop-code',
          '📍': 'location-dot', '📧': 'envelope', '📅': 'calendar', '🎓': 'graduation-cap', '👥': 'users',
          '🎯': 'bullseye', '🧪': 'flask', '🗓️': 'calendar-days', '🏛️': 'building-columns', '📩': 'envelope-open-text',
          '🚀': 'rocket', '🤝': 'handshake'}
ENLACES = {'pagina%20inicial.html#': '../#', 'pagina inicial.html#': '../#'}  # rutas locales -> rutas en WordPress
CARPETA_MEDIOS = '/wp-content/uploads/'  # dónde quedan las imágenes subidas; cambiar si WP vive en un subdirectorio
avisos = []  # lo que no se pudo convertir; lo imprime la terminal
