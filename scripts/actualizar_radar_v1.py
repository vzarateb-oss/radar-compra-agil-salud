"""Radar Compra Ágil Salud: piloto de ingesta, clasificación y CSV en staging.
No modifica CSV existentes ni publica datos. Ticket solo desde variable de entorno.
"""
import csv
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = 'https://api2.mercadopublico.cl'
TICKET = os.getenv('MERCADOPUBLICO_TICKET', '').strip()
TERMINOS = ('capacitacion', 'curso', 'diplomado', 'formacion', 'educacion continua', 'entrenamiento')
PAGINAS_POR_TERMINO = max(1, min(int(os.getenv('RADAR_PAGINAS', '2')), 5))
DETALLES_MAX = max(1, min(int(os.getenv('RADAR_DETALLES_MAX', '80')), 150))
SALIDA = Path('staging_radar')

FORMACION = ('capacitacion', 'curso', 'diplomado', 'formacion', 'taller', 'entrenamiento', 'certificacion', 'educacion continua', 'perfeccionamiento', 'docencia', 'instruccion', 'e-learning', 'elearning')
SALUD_FUERTE = ('enfermeria', 'farmacologia', 'farmacia', 'medicina', 'medico', 'medica', 'clinico', 'clinica', 'paciente', 'hospital', 'salud publica', 'odontologia', 'kinesiologia', 'obstetricia', 'matroneria', 'nutricion clinica', 'laboratorio clinico', 'urgencia', 'reanimacion', 'rcp', 'primeros auxilios', 'infecciones asociadas', 'iaas', 'epidemiologia', 'salud mental', 'psiquiatria', 'psicologia clinica', 'imagenologia', 'radiologia', 'paramedico', 'tecnico en enfermeria', 'tens', 'esterilizacion', 'hemodialisis', 'pabellon quirurgico', 'cuidados paliativos', 'fisioterapia', 'atencion primaria', 'aps', 'bioseguridad', 'vacunacion', 'inmunizacion', 'farmacovigilancia')
SALUD_AMBIGUA = ('salud', 'sanitario', 'sanitaria', 'biologia', 'nutricion', 'psicologia', 'terapia', 'discapacidad', 'adulto mayor', 'cuidado')
NO_CAPACITACION = ('arriendo de', 'adquisicion de', 'compra de', 'suministro de', 'mantencion de', 'mantenimiento de', 'reparacion de', 'servicio de traslado', 'servicio de transporte', 'examenes de', 'prestacion de examenes', 'insumos', 'equipamiento', 'medicamentos', 'servicio de alimentacion')
ASINCRONICO = ('asincronico', 'asincronica', 'a su ritmo', 'autoinstruccional', 'auto instruccional', 'on demand', 'bajo demanda')
ONLINE = ('online', 'en linea', 'virtual', 'e-learning', 'elearning', 'remoto', 'plataforma virtual')
PRESENCIAL = ('presencial', 'en terreno', 'en aula')


def norm(value):
    value = unicodedata.normalize('NFKD', str(value or '').lower())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', value).strip()


def contains(text, terms):
    return [term for term in terms if re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text)]


def get(session, path, params=None):
    last = None
    for attempt in range(3):
        try:
            response = session.get(BASE + path, params=params, timeout=(10, 35))
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError('HTTP ' + str(response.status_code))
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get('success') != 'OK':
                raise ValueError('API sin success=OK')
            return data.get('payload')
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if isinstance(exc, requests.HTTPError) and getattr(exc.response, 'status_code', None) in (400, 401, 403, 404):
                break
            if attempt < 2:
                time.sleep(2 ** attempt + 1)
    raise RuntimeError(type(last).__name__ + ' en ' + path)


def classify(detail):
    products = detail.get('productos_solicitados') or []
    products_text = ' '.join(str(p.get('nombre', '')) + ' ' + str(p.get('descripcion', '')) for p in products if isinstance(p, dict))
    title = norm(detail.get('nombre'))
    body = norm(' '.join([detail.get('descripcion') or '', products_text]))
    text = title + ' ' + body
    education = contains(text, FORMACION)
    strong = contains(text, SALUD_FUERTE)
    ambiguous = contains(text, SALUD_AMBIGUA)
    negative = contains(title, NO_CAPACITACION)
    evidence = '; '.join((education[:3] + strong[:3] + ambiguous[:2]))
    if not education:
        return 'EXCLUIDA', 'No se identifica actividad formativa', evidence, 'No determinada'
    if negative and not contains(title, FORMACION):
        return 'EXCLUIDA', 'Título sugiere adquisición o servicio no formativo', evidence, 'No determinada'
    if strong:
        priority, reason = 'A', 'Capacitación y evidencia temática sanitaria específica'
    elif ambiguous:
        priority, reason = 'C', 'Posible capacitación sanitaria: requiere revisión humana'
    else:
        return 'EXCLUIDA', 'Sin evidencia temática sanitaria suficiente', evidence, 'No determinada'
    if contains(text, ASINCRONICO) and contains(text, ONLINE):
        mode = 'Online asincrónica explícita'
    elif contains(text, ASINCRONICO):
        mode = 'Asincrónica (canal por confirmar)'
    elif contains(text, ONLINE) and contains(text, PRESENCIAL):
        mode = 'Mixta / revisar'
    elif contains(text, ONLINE):
        mode = 'Online (sin confirmar asincronía)'
    elif contains(text, PRESENCIAL):
        mode = 'Presencial'
    else:
        mode = 'No determinada'
    return priority, reason, evidence, mode


def write_csv(filename, rows, fields):
    with (SALIDA / filename).open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not TICKET:
        print('ERROR: falta MERCADOPUBLICO_TICKET')
        return 1
    session = requests.Session()
    session.headers.update({'ticket': TICKET, 'Accept': 'application/json'})
    SALIDA.mkdir(exist_ok=True)
    found = {}
    failures = []
    for term in TERMINOS:
        for page in range(1, PAGINAS_POR_TERMINO + 1):
            try:
                payload = get(session, '/v2/compra-agil', {'q': term, 'tamano_pagina': 10, 'numero_pagina': page})
                if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
                    raise ValueError('Listado sin payload.items')
                items = payload['items']
                for item in items:
                    if isinstance(item, dict) and item.get('codigo'):
                        found.setdefault(str(item['codigo']), item)
                print(f'LISTADO OK: {term} página {page}, {len(items)} registros')
                if len(items) < 10:
                    break
                pagination = payload.get('paginacion') or {}
                if isinstance(pagination, dict) and page >= int(pagination.get('total_paginas') or page):
                    break
            except (RuntimeError, ValueError) as exc:
                failures.append(f'Listado {term} página {page}: {exc}')
                print(f'ADVERTENCIA: listado {term}, página {page}: {type(exc).__name__}')
                break
            time.sleep(.4)
    if not found:
        print('ERROR: no se recuperaron oportunidades. No se generan CSV.')
        return 1
    selected = list(found.items())[:DETALLES_MAX]
    rows, excluded, pending = [], 0, 0
    for i, (code, listing) in enumerate(selected, 1):
        try:
            detail = get(session, '/v2/compra-agil/' + requests.utils.quote(code, safe=''))
            if not isinstance(detail, dict):
                raise ValueError('Detalle sin objeto')
            priority, reason, evidence, mode = classify(detail)
            if priority == 'EXCLUIDA':
                excluded += 1
                continue
            inst = detail.get('institucion') or {}
            dates = detail.get('fechas') or {}
            budget = detail.get('presupuesto') or {}
            summary = detail.get('resumen') or {}
            rows.append({
                'Codigo': code, 'Nombre oportunidad': detail.get('nombre', ''),
                'Organismo comprador': inst.get('organismo_comprador', ''),
                'RUT organismo comprador': inst.get('rut', ''),
                'Region': inst.get('nombre_region', ''),
                'Estado': (detail.get('estado') or {}).get('glosa', ''),
                'Fecha publicacion': dates.get('fecha_publicacion', ''),
                'Fecha cierre': dates.get('fecha_cierre', ''),
                'Presupuesto CLP': budget.get('monto_disponible_clp', ''),
                'Ofertas recibidas': summary.get('total_ofertas_recibidas', ''),
                'Pertinencia sanitaria': priority, 'Modalidad': mode,
                'Justificacion': reason, 'Evidencia': evidence,
                'Descripcion': detail.get('descripcion', ''),
                'Productos solicitados': ' | '.join(str(p.get('nombre', '')) for p in (detail.get('productos_solicitados') or []) if isinstance(p, dict)),
                'Fecha extraccion UTC': datetime.now(timezone.utc).isoformat(),
            })
        except (RuntimeError, ValueError) as exc:
            pending += 1
            failures.append(f'Detalle {code}: {exc}')
            print(f'ADVERTENCIA: detalle {i}/{len(selected)} no disponible, código {code}')
        time.sleep(.4)
    fields = ['Codigo', 'Nombre oportunidad', 'Organismo comprador', 'RUT organismo comprador', 'Region', 'Estado', 'Fecha publicacion', 'Fecha cierre', 'Presupuesto CLP', 'Ofertas recibidas', 'Pertinencia sanitaria', 'Modalidad', 'Justificacion', 'Evidencia', 'Descripcion', 'Productos solicitados', 'Fecha extraccion UTC']
    write_csv('clasificacion_piloto.csv', rows, fields)
    report = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'terminos': list(TERMINOS), 'paginas_por_termino': PAGINAS_POR_TERMINO, 'oportunidades_unicas_encontradas': len(found), 'detalles_intentados': len(selected), 'clasificadas_sanitarias_A': sum(r['Pertinencia sanitaria'] == 'A' for r in rows), 'clasificadas_revision_C': sum(r['Pertinencia sanitaria'] == 'C' for r in rows), 'excluidas': excluded, 'detalles_fallidos': pending, 'fallos': failures, 'advertencia': 'Clasificación piloto conservadora, no equivale a validación humana ni reproduce íntegramente reglas Apps Script V3.8.1. No publica ni modifica CSV de producción.'}
    (SALIDA / 'reporte_piloto.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('RESUMEN: ' + json.dumps({k: v for k, v in report.items() if k not in ('fallos', 'advertencia', 'terminos')}, ensure_ascii=False))
    print('ARCHIVOS: staging_radar/clasificacion_piloto.csv, staging_radar/reporte_piloto.json')
    print('No se modificaron los CSV de producción.')
    return 0 if not failures else 0  # errores parciales registrados en reporte, no bloquean descarga de evidencia


if __name__ == '__main__':
    sys.exit(main())
