"""Diagnóstico de solo lectura de Compra Ágil.
Reutiliza los parámetros y encabezados de probar_api.py.
Imprime solamente claves y tipos, nunca valores de registros ni credenciales.
"""
import os
import sys
from urllib.parse import urlencode, quote
import requests

BASE = 'https://api2.mercadopublico.cl'
TICKET = os.getenv('MERCADOPUBLICO_TICKET', '').strip()


def tipo(valor):
    return type(valor).__name__


def esquema(objeto, nivel=0, max_nivel=3):
    if nivel > max_nivel:
        return
    prefijo = '  ' * nivel
    if isinstance(objeto, dict):
        for clave, valor in sorted(objeto.items()):
            print(f'{prefijo}- {clave}: {tipo(valor)}')
            if isinstance(valor, dict) and nivel < max_nivel:
                esquema(valor, nivel + 1, max_nivel)
            elif isinstance(valor, list):
                print(f'{prefijo}  elementos: {len(valor)}')
                if valor and isinstance(valor[0], dict) and nivel < max_nivel:
                    esquema(valor[0], nivel + 1, max_nivel)
    elif isinstance(objeto, list):
        print(f'{prefijo}elementos: {len(objeto)}')
        if objeto and isinstance(objeto[0], dict):
            esquema(objeto[0], nivel + 1, max_nivel)
    else:
        print(f'{prefijo}{tipo(objeto)}')


def solicitar(sesion, ruta, parametros=None):
    url = BASE + ruta
    if parametros:
        url += '?' + urlencode(parametros)
    respuesta = sesion.get(url, timeout=(10, 35))
    print(f'HTTP {respuesta.status_code} en {ruta}')
    respuesta.raise_for_status()
    data = respuesta.json()
    if not isinstance(data, dict) or data.get('success') != 'OK':
        raise ValueError('Respuesta sin success=OK')
    return data.get('payload')


def codigo_desde(item):
    # Solo se usa internamente para consultar el detalle; nunca se imprime.
    if not isinstance(item, dict):
        return None
    for clave in ('codigo', 'codigo_compra_agil', 'codigoCompraAgil', 'codigo_cotizacion'):
        valor = item.get(clave)
        if isinstance(valor, (str, int)) and str(valor).strip():
            return str(valor).strip()
    return None


def main():
    if not TICKET:
        print('ERROR: falta el secreto MERCADOPUBLICO_TICKET')
        return 1
    sesion = requests.Session()
    sesion.headers.update({'ticket': TICKET, 'Accept': 'application/json'})

    print('=== DIAGNOSTICO LISTADO: claves y tipos, SIN valores ===')
    try:
        payload = solicitar(sesion, '/v2/compra-agil', {
            'q': 'capacitacion', 'tamano_pagina': 10, 'numero_pagina': 1
        })
    except (requests.RequestException, ValueError) as exc:
        print(f'ERROR LISTADO: {type(exc).__name__}; no se muestran datos sensibles')
        return 1

    esquema(payload)
    items = payload.get('items') if isinstance(payload, dict) else None
    if not isinstance(items, list):
        print('ERROR: payload.items no es una lista')
        return 1
    print(f'Cantidad de items en pagina: {len(items)}')
    if not items:
        print('No hay items para diagnosticar detalle; listado OK')
        return 0

    codigo = next((c for item in items if (c := codigo_desde(item))), None)
    if not codigo:
        print('No se identifico un campo de codigo conocido; revisar claves del item antes de probar detalle')
        return 0

    print('=== DIAGNOSTICO DETALLE: claves y tipos, SIN valores ===')
    # Ruta candidata: confirmar contra el Apps Script si la API la rechaza.
    try:
        detalle = solicitar(sesion, '/v2/compra-agil/' + quote(codigo, safe=''))
        esquema(detalle)
        print('Detalle consultado correctamente')
    except (requests.RequestException, ValueError) as exc:
        print(f'AVISO DETALLE: {type(exc).__name__}; ruta candidata no validada')
        print('El listado funciona. Revisar ruta exacta del Apps Script antes de construir la ingesta.')

    print('Diagnostico de solo lectura finalizado; no se modificaron CSV ni repositorio')
    return 0


if __name__ == '__main__':
    sys.exit(main())
