"""Pruebas locales sin API ni ticket para clasificador V3.1.1."""
from actualizar_radar_v311 import classify

def d(title, product, description='Capacitación del programa Más AMA de salud'):
    return {'nombre':title,'descripcion':description,'productos_solicitados':[{'nombre':product,'descripcion':''}]}

cases = [
    ('4433-173-COT26',d('Adquisición de artículos Más AMA','Vasos, cucharas, tenedores y bandejas'),'EXCLUIDA'),
    ('4433-171-COT26',d('Compra para programa Más AMA','Folletos y material publicitario'),'EXCLUIDA'),
    ('4433-170-COT26',d('Materiales Más AMA','Pizarras, perforadoras y accesorios'),'EXCLUIDA'),
    ('2832-412-COT26',d('Insumos rehabilitación APS','Electrodos y bandas elásticas'),'EXCLUIDA'),
    ('5350-624-COT26',d('Implementos actividad física Más Salud','Mancuernas y colchonetas'),'EXCLUIDA'),
    ('3679-212-COT26',d('Coffee break para capacitación de salud','Café instantáneo y galletas'),'EXCLUIDA'),
    ('1237328-323-COT26',d('Capacitaciones programa Más AMA','Servicio de capacitación en estimulación cognitiva','Cinco capacitaciones para profesionales en envejecimiento saludable'),'A'),
    ('2735-1457-COT26',d('Diplomado en salud mental','Diplomado salud mental','Programa formativo de salud mental'),'A'),
    ('3980-59-COT26',d('Auxiliar de farmacia farmacología','Curso de farmacología','Capacitación de auxiliar de farmacia'),'A'),
    ('1057448-381-COT26',d('Diplomado enfermería oncológica','Curso cuidados paliativos','100% asincrónico y online en enfermería'),'A'),
    ('3019-801-COT26',d('Diplomado online TEA neurodesarrollo','Diplomado TEA','Curso online neurodesarrollo'),'A'),
    ('806208-118-COT26',d('Curso simulación clínica','Curso simulación clínica','Capacitación clínica'),'A'),
    ('2735-1438-COT26',d('Diplomado informática clínica','Diplomado informática clínica','Programa formativo'),'A'),
    ('2710-875-COT26',d('Formación intercultural en salud indígena','Capacitación salud indígena','Programa formativo'),'A'),
]
for code, item, expected in cases:
    got=classify(item)['decision']
    assert got==expected, f'{code}: esperado {expected}, obtenido {got}'
print(f'PRUEBAS OK: {len(cases)} casos de clasificación')
assert 'asincrónica explícita' in classify(cases[9][1])['mode'].lower()
assert 'asincronía no confirmada' in classify(cases[10][1])['mode'].lower()
print('PRUEBAS OK: 2 casos de modalidad')
