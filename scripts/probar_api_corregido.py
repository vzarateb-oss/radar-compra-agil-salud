"""Diagnóstico de conexión de solo lectura con la API Compra Ágil.

No modifica archivos del repositorio ni revela credenciales.
Los fallos transitorios se reintentan y se informan individualmente.
"""
import os
import sys
import time
from urllib.parse import urlencode

import requests

BASE = "https://api2.mercadopublico.cl"
TERMINOS = (
    "capacitacion", "curso", "diplomado", "formacion",
    "educacion continua", "entrenamiento",
)
TICKET = os.environ.get("MERCADOPUBLICO_TICKET", "").strip()
MAX_INTENTOS = 3


def probar_termino(sesion, termino):
    url = BASE + "/v2/compra-agil?" + urlencode({
        "q": termino, "tamano_pagina": 10, "numero_pagina": 1,
    })
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            respuesta = sesion.get(url, timeout=(10, 35))
            respuesta.raise_for_status()
            datos = respuesta.json()
            if datos.get("success") != "OK":
                raise ValueError("Respuesta API sin success=OK")
            payload = datos.get("payload")
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise ValueError("Estructura inesperada de payload.items")
            return True, f"items={len(payload['items'])}, paginacion={'paginacion' in payload}"
        except requests.HTTPError as error:
            codigo = error.response.status_code if error.response is not None else "desconocido"
            motivo = f"HTTP {codigo}"
            # No repetir errores de credenciales o parámetros inválidos.
            reintentar = codigo in (408, 429, 500, 502, 503, 504)
        except (requests.Timeout, requests.ConnectionError) as error:
            motivo = type(error).__name__
            reintentar = True
        except (requests.RequestException, ValueError) as error:
            motivo = type(error).__name__
            reintentar = False
        if intento >= MAX_INTENTOS or not reintentar:
            return False, f"{motivo}, intentos={intento}"
        espera = min(2 ** intento, 8)
        print(f"REINTENTO: {termino}, motivo={motivo}, espera={espera}s", flush=True)
        time.sleep(espera)
    return False, "Error inesperado"


def main():
    if not TICKET:
        print("ERROR: falta MERCADOPUBLICO_TICKET en los secretos de GitHub.")
        return 1
    sesion = requests.Session()
    sesion.headers.update({"ticket": TICKET, "Accept": "application/json"})
    correctas = 0
    fallidas = []
    for termino in TERMINOS:
        ok, detalle = probar_termino(sesion, termino)
        if ok:
            correctas += 1
            print(f"OK: {termino} - {detalle}", flush=True)
        else:
            fallidas.append(termino)
            print(f"ERROR: {termino} - {detalle}", flush=True)
        time.sleep(1)
    print(f"RESUMEN: {correctas}/{len(TERMINOS)} consultas correctas", flush=True)
    if fallidas:
        print("CONSULTAS PENDIENTES: " + ", ".join(fallidas), flush=True)
    print("Prueba de solo lectura: NO modifica CSV ni actualiza el dashboard.", flush=True)
    # La ejecución queda marcada como parcial si al menos una consulta funcionó.
    # Solo se considera fallo total cuando ninguna consulta fue exitosa.
    return 0 if correctas > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
