"""Revisión del texto generado antes de pegarlo en WordPress."""
import json, re


def check(text):
    """Lista de errores: comentarios de bloque sin balancear, JSON de atributos inválido o <div> desbalanceados."""
    open_blocks, errors = [], []
    for match in re.finditer(r'<!-- (/?)wp:([a-z0-9/-]+)(?: (\{.*?\}))? (/?)-->', text):
        is_closing, name, attrs_json, self_closing = match.groups()
        if attrs_json:
            try:
                json.loads(attrs_json)
            except ValueError:
                errors.append(f'JSON inválido en {name}')
        if self_closing:
            continue
        if is_closing:
            if not open_blocks or open_blocks.pop() != name:
                errors.append(f'cierre inesperado de {name}')
        else:
            open_blocks.append(name)
    if open_blocks:
        errors.append(f'bloques sin cerrar: {open_blocks}')
    if text.count('<div') != text.count('</div>'):
        errors.append('divs desbalanceados')
    return errors
