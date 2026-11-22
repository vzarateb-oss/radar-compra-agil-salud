"""Diagnóstico seguro y de solo lectura del esquema de Compra Ágil.
No imprime tickets, valores de registros ni información de proveedores.
"""
import os
import sys
import time
from urllib.parse import quote
import requests

BASE = 'https://api2.mercadopublico.cl'
TICKET = os.environ.get('MERCADOPUBLICO_TICKET', '').strip()
TERMINO = 'capacitacion'
MAX_REINTENTOS = 3


def obtener(session, ruta, params=None):
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            r = session.get(BASE + ruta, params=params, timeout=(10, 35))
            if r.status_code in (429, 500, 502, 503, 504) and intento < MAX_REINTENTOS:
                print(f'HTTP {r.status_code}; reintento {intento}/{MAX_REINTENTOS}')
                time.sleep(2 ** intento)
                continue
            if not r.ok:
                print(f'HTTP {r.status_code} en {ruta} (sin mostrar contenido de respuesta)')
                return None
            data = r.json()
            if not isinstance(data, dict) or data.get('success') != 'OK':
                print('Respuesta JSON sin success=OK; no se imprimen datos')
                return None
            return data
        except (requests.Timeout, requests.ConnectionError):
            print(f'Error temporal de red, intento {intento}/{MAX_REINTENTOS}')
            if intento < MAX_REINTENTOS:
                time.sleep(2 ** intento)
        except ValueError:
            print('Respuesta no válida como JSON')
            return None
    return None


def esquema(obj, prefijo='', nivel=0):
    """Solo claves y tipos; nunca valores."""
    if nivel > 2:
        return
    if isinstance(obj, dict):
        for clave in sorted(obj, key=str):
            valor = obj[clave]
            nombre = f'{prefijo}.{clave}' if prefijo else str(clave)
            tipo = type(valor).__name__
            print(f'  {nombre}: {tipo}')
            if isinstance(valor, dict):
                esquema(valor, nombre, nivel + 1)
            elif isinstance(valor, list):
                print(f'  {nombre}[]: {type(valor[0]).__name__ if valor else "vacia"}')
                if valor and isinstance(valor[0], dict):
                    esquema(valor[0], nombre + '[]', nivel + 1)


def main():
    if not TICKET:
        print('Falta MERCADOPUBLICO_TICKET en GitHub Secrets')
        return 1
    s = requests.Session()
    s.headers.update({'ticket': TICKET, 'Accept': 'application/json'})
    print('=== DIAGNOSTICO LISTADO: claves y tipos, SIN valores ===')
    listado = obtener(s, '/v2/compra-agil', {'q': TERMINO, 'tamano_pagina': 5, 'numero_pagina': 1})
    if listado is None:
        print('No se pudo obtener listado; sin cambios en el repositorio')
        return 1
    payload = listado.get('payload')
    if not isinstance(payload, dict):
        print('payload no es un objeto; tipo:', type(payload).__name__)
        return 1
    print('Claves de payload:', ', '.join(sorted(payload)))
    items = payload.get('items')
    print('Tipo items:', type(items).__name__)
    print('Cantidad items en página:', len(items) if isinstance(items, list) else 'no disponible')
    if not isinstance(items, list) or not items:
        print('No hay items para diagnosticar; sin cambios en el repositorio')
        return 0
    esquema(items[0], 'items[0]')
    print('=== PAGINACION: claves y tipos ===')
    esquema(payload.get('paginacion'), 'paginacion')
    print('=== DETALLE: prueba de ruta con un codigo obtenido del listado ===')
    item = items[0]
    codigo = None
    if isinstance(item, dict):
        for clave in ('codigo', 'Codigo', 'codigo_cotizacion', 'codigoCotizacion'):
            if isinstance(item.get(clave), (str, int)) and str(item[clave]).strip():
                codigo = str(item[clave]).strip()
                print('Campo identificador encontrado:', clave)
                break
    if not codigo:
        print('No se identificó campo codigo. No se intenta detalle.')
        return 0
    # Esta ruta es una hipótesis para diagnosticar; el código exacto se confirmará
    # con la implementación del Radar si responde con 404.
    ruta = '/v2/compra-agil/' + quote(codigo, safe='')
    detalle = obtener(s, ruta)
    if detalle is None:
        print('Ruta de detalle no confirmada; se revisará el endpoint del Radar Apps Script.')
        return 0
    print('Claves principales detalle:', ', '.join(sorted(detalle)))
    esquema(detalle.get('payload'), 'detalle.payload')
    print('Diagnóstico finalizado: solo lectura, ningún CSV modificado.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
