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
