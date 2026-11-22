"""Pruebas sin red para Radar V4. Ejecutar: python scripts/probar_clasificador_v4.py"""
from actualizar_radar_v4 import classify

def caso(titulo, producto, descripcion):
    return {"nombre": titulo, "descripcion": descripcion,
            "productos_solicitados": [{"nombre": producto, "descripcion": ""}]}

casos = [
 ("vasos Más AMA", caso("Adquisición de artículos Más AMA", "Vasos, cucharas, tenedores y bandejas", "Capacitación del programa Más AMA de salud"), "EXCLUIDA"),
 ("folletos Más AMA", caso("Compra para programa Más AMA", "Folletos y material publicitario", "Capacitación del programa Más AMA de salud"), "EXCLUIDA"),
 ("pizarras Más AMA", caso("Materiales Más AMA", "Pizarras, perforadoras y accesorios", "Capacitación del programa Más AMA de salud"), "EXCLUIDA"),
 ("rehabilitación insumos", caso("Insumos rehabilitación APS", "Electrodos y bandas elásticas", "Para capacitación en salud"), "EXCLUIDA"),
 ("coffee break", caso("Coffee break para capacitación de salud", "Café instantáneo y galletas", "Para curso de enfermería"), "EXCLUIDA"),
 ("formación Más AMA", caso("Capacitaciones programa Más AMA", "Servicio de capacitación en estimulación cognitiva", "Cinco capacitaciones para profesionales en envejecimiento saludable"), "A"),
 ("farmacia", caso("Auxiliar de farmacia farmacología", "Curso de farmacología", "Capacitación de auxiliar de farmacia"), "A"),
 ("enfermería", caso("Diplomado enfermería oncológica", "Curso cuidados paliativos", "100% asincrónico y online en enfermería"), "A"),
 ("TEA", caso("Diplomado online TEA neurodesarrollo", "Diplomado TEA", "Curso online neurodesarrollo"), "A"),
 ("simulación", caso("Curso simulación clínica", "Curso simulación clínica", "Capacitación clínica"), "A"),
 ("informática", caso("Diplomado informática clínica", "Diplomado informática clínica", "Programa formativo"), "A"),
 ("intercultural", caso("Formación intercultural en salud indígena", "Capacitación salud indígena", "Programa formativo"), "A"),
]
for nombre, item, esperado in casos:
    obtenido = classify(item)["decision"]
    assert obtenido == esperado, f"{nombre}: {obtenido} != {esperado}"
asincrono = classify(casos[7][1])["mode"].lower()
assert "asincrónica explícita" in asincrono, asincrono
online = classify(casos[8][1])["mode"].lower()
assert "asincronía no confirmada" in online, online
autogestion = classify(caso("Capacitaciones programa Más AMA", "Servicio de capacitación en estimulación cognitiva", "Curso online y autogestionado para profesionales de salud"))["mode"].lower()
assert "autogestionada" in autogestion and "no confirmada" in autogestion, autogestion
print(f"OK: {len(casos)} clasificaciones y 3 modalidades sin API")

# Simulaciones de red: no realizan llamadas a Mercado Público.
from unittest.mock import patch
import requests
from actualizar_radar_v4 import api

class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self.payload = payload if payload is not None else {"success": "OK", "payload": {"items": []}}
    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error
    def json(self):
        return self.payload

class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0
    def get(self, *args, **kwargs):
        self.calls += 1
        return next(self.responses)

with patch("actualizar_radar_v4.time.sleep", return_value=None):
    session = FakeSession([FakeResponse(504), FakeResponse(504), FakeResponse(200)])
    assert api(session, "/v2/compra-agil") == {"items": []}
    assert session.calls == 3, session.calls

    session = FakeSession([FakeResponse(401)])
    try:
        api(session, "/v2/compra-agil")
    except RuntimeError as exc:
        assert "HTTP 401" in str(exc)
    else:
        raise AssertionError("Se esperaba error HTTP 401")
    assert session.calls == 1, "Un error 401 no debe reintentarse"

print("OK: reintentos HTTP 504 y corte ante HTTP 401, sin red")

# Replay de detalles guardados: verifica que la reclasificación no use red.
import json
import tempfile
from pathlib import Path
from reclasificar_radar_v4 import replay

with tempfile.TemporaryDirectory() as carpeta:
    origen = Path(carpeta) / "detalles.jsonl"
    destino = Path(carpeta) / "resultado.csv"
    with origen.open("w", encoding="utf-8") as salida:
        for numero, (_, item, _) in enumerate(casos):
            salida.write(json.dumps({"codigo": str(numero), "detalle": item}, ensure_ascii=False) + "\\n")
    filas = replay(origen, destino)
    assert len(filas) == len(casos)
    assert destino.is_file()
    assert filas[0]["Decision"] == "EXCLUIDA"
    assert filas[5]["Decision"] == "A"
print("OK: replay sin API de detalles guardados")
