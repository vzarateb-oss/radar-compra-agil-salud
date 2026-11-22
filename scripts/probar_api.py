"""Prueba de conexión de solo lectura con la API Compra Ágil.
No cambia CSV, no publica datos, no expone el ticket.
"""
import json
import os
import sys
import time
from urllib.parse import urlencode
import requests

BASE = "https://api2.mercadopublico.cl"
TERMINOS = ("capacitacion", "curso", "diplomado", "formacion", "educacion continua", "entrenamiento")
TICKET = os.getenv("MERCADOPUBLICO_TICKET", "").strip()

def main():
    if not TICKET:
        print("ERROR: falta el secreto MERCADOPUBLICO_TICKET.")
        return 1
    sesion = requests.Session()
    sesion.headers.update({"ticket": TICKET, "Accept": "application/json"})
    resultados = {}
    errores = 0
    for termino in TERMINOS:
        url = BASE + "/v2/compra-agil?" + urlencode({
            "q": termino, "tamano_pagina": 10, "numero_pagina": 1
        })
        try:
            r = sesion.get(url, timeout=(10, 35))
            r.raise_for_status()
            data = r.json()
            if data.get("success") != "OK":
                raise ValueError("La API respondió sin success=OK")
            payload = data.get("payload")
            # No inferimos el esquema hasta examinarlo en la ejecución real.
            info = {"tipo_payload": type(payload).__name__}
            if isinstance(payload, dict):
                info["claves_payload"] = sorted(payload.keys())
            elif isinstance(payload, list):
                info["cantidad_elementos"] = len(payload)
            resultados[termino] = info
            print(f"OK: {termino} - {json.dumps(info, ensure_ascii=False)}")
        except (requests.RequestException, ValueError) as exc:
            errores += 1
            print(f"ERROR: {termino} - {type(exc).__name__} (HTTP/API/tiempo de espera)")
        time.sleep(1)
    print(f"RESUMEN: {len(TERMINOS)-errores}/{len(TERMINOS)} consultas correctas")
    print("Esta prueba NO modifica datos ni publica oportunidades.")
    return 0 if errores == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
