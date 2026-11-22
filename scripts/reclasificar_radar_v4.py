"""Reclasifica capturas API guardadas, sin consultas de red ni secretos.

Uso: python scripts/reclasificar_radar_v4.py staging_radar_v4/detalles_crudos_v4.jsonl
Salida: staging_radar_v4/reclasificacion_offline_v4.csv
"""
import csv
import json
import sys
from pathlib import Path
from actualizar_radar_v4 import classify

COLUMNAS = ["Codigo", "Nombre oportunidad", "Decision", "Motivo", "Modalidad", "Evidencia modalidad", "Evidencia formativa", "Evidencia sanitaria", "Evidencia exclusion", "Objeto de compra"]

def replay(origen, destino=None):
    origen = Path(origen)
    if not origen.is_file():
        raise FileNotFoundError(origen)
    destino = Path(destino) if destino else origen.with_name("reclasificacion_offline_v4.csv")
    filas = []
    with origen.open(encoding="utf-8-sig") as entrada:
        for numero, linea in enumerate(entrada, 1):
            if not linea.strip():
                continue
            try:
                item = json.loads(linea)
                detalle = item["detalle"]
                if not isinstance(detalle, dict):
                    raise ValueError("detalle no es objeto")
                clas = classify(detalle)
                filas.append({
                    "Codigo": item.get("codigo", ""),
                    "Nombre oportunidad": detalle.get("nombre", ""),
                    "Decision": clas["decision"],
                    "Motivo": clas["reason"],
                    "Modalidad": clas["mode"],
                    "Evidencia modalidad": clas["mode_evidence"],
                    "Evidencia formativa": clas["form"],
                    "Evidencia sanitaria": clas["health"],
                    "Evidencia exclusion": clas["negative"],
                    "Objeto de compra": clas["obj"],
                })
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError(f"Línea {numero}: {exc}") from exc
    if not filas:
        raise ValueError("No hay detalles para reclasificar")
    with destino.open("w", encoding="utf-8-sig", newline="") as salida:
        escritor = csv.DictWriter(salida, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"Reclasificados sin API: {len(filas)}. Archivo: {destino}")
    return filas

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Uso: python scripts/reclasificar_radar_v4.py archivo.jsonl [salida.csv]")
    replay(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
