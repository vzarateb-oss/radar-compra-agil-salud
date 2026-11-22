"""Pruebas integradas V4 con respuestas simuladas, sin consultas reales a API."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import actualizar_radar_v4 as radar


def detalle(codigo):
    return {
        "codigo": codigo,
        "nombre": "Curso de enfermería clínica",
        "descripcion": "Capacitación para profesionales de salud",
        "productos_solicitados": [{"nombre": "Curso de enfermería", "descripcion": ""}],
        "institucion": {},
        "fechas": {},
        "presupuesto": {},
        "resumen": {},
    }


def ejecutar(simular_error=False):
    llamadas = []
    with tempfile.TemporaryDirectory() as carpeta:
        salida = Path(carpeta) / "staging"
        def respuesta(_sesion, ruta, params=None):
            if ruta == "/v2/compra-agil":
                termino = params["q"]
                pagina = params["numero_pagina"]
                llamadas.append((termino, pagina))
                if simular_error and termino == "curso" and pagina == 2:
                    raise RuntimeError("HTTP 504 en /v2/compra-agil")
                # Sin total_paginas: una página llena exige intentar la siguiente.
                if pagina == 1:
                    return {"items": [{"codigo": f"CAP-{i}"} for i in range(10)], "paginacion": {}}
                return {"items": [{"codigo": "CAP-10"}], "paginacion": {}}
            codigo = ruta.rsplit("/", 1)[-1]
            return detalle(codigo)
        with patch.object(radar, "TICKET", "simulado"), \
             patch.object(radar, "SALIDA", salida), \
             patch.object(radar, "PAGINAS", 2), \
             patch.object(radar, "MAX_DETALLES", 50), \
             patch.object(radar, "api", side_effect=respuesta), \
             patch.object(radar.time, "sleep", return_value=None):
            resultado = radar.main()
        reporte = json.loads((salida / "reporte_v4.json").read_text(encoding="utf-8"))
        assert (salida / "detalles_crudos_v4.jsonl").is_file()
        assert len((salida / "detalles_crudos_v4.jsonl").read_text(encoding="utf-8").splitlines()) == 11
        assert all((termino, 2) in llamadas for termino in radar.TERMINOS), llamadas
        assert reporte["oportunidades_unicas_encontradas"] == 11
        assert reporte["detalles_intentados"] == 11
        if simular_error:
            assert resultado == 1 and not reporte["ejecucion_completa"]
            assert any("HTTP 504" in error for error in reporte["fallos"])
        else:
            assert resultado == 0 and reporte["ejecucion_completa"]
        return resultado


ejecutar(False)
ejecutar(True)
print("OK: paginación sin total_paginas, deduplicación, caché y bloqueo ante HTTP 504")
