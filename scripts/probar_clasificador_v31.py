"""Pruebas de regresión locales: sin API ni credenciales."""
from actualizar_radar_v31 import classify

CASOS = [
    ('Insumos rehabilitación APS universal', 'Electrodos y bandas para entrenamiento de pacientes', 'EXCLUIDA'),
    ('Insumos de actividad física convenio Más Salud', 'Implementos deportivos para actividad comunitaria', 'EXCLUIDA'),
    ('Coffee break para capacitación funcionarios de salud', 'Colaciones para curso', 'EXCLUIDA'),
    ('Colaciones para curso de salvavidas', 'Alimentos para participantes', 'EXCLUIDA'),
    ('Jornada de esparcimiento y recreación', 'Actividad de discapacidad y salud comunitaria', 'EXCLUIDA'),
    ('Diplomado en salud mental', 'Capacitación para profesionales de salud', 'A'),
    ('Auxiliar de farmacia mención farmacología', 'Curso de formación en farmacia', 'A'),
    ('Diplomado en enfermería oncológica', 'Curso de cuidados paliativos 100% asincrónico', 'A'),
    ('Diplomado online en TEA y neurodesarrollo', '15 cupos de formación online', 'A'),
    ('Curso de simulación clínica', 'Capacitación clínica para profesionales', 'A'),
    ('Diplomado en informática clínica', 'Formación en sistemas de información clínica', 'A'),
    ('Formación intercultural en salud indígena', 'Curso para equipos de atención primaria', 'A'),
    ('Capacitaciones de estimulación cognitiva y estilos de vida saludables programa Más AMA', 'Cinco capacitaciones online autogestionadas en promoción de salud', 'A'),
    ('Capacitación en autocuidado y bienestar laboral', 'Taller para equipos de trabajo', 'C'),
]
for titulo, descripcion, esperado in CASOS:
    actual = classify({'nombre':titulo, 'descripcion':descripcion, 'productos_solicitados':[]})['decision']
    assert actual == esperado, f'{titulo}: esperado {esperado}, recibido {actual}'
assert 'asincrónica' in classify({'nombre':'Diplomado en enfermería oncológica','descripcion':'Curso 100% asincrónico','productos_solicitados':[]})['mode'].lower()
assert 'no confirmada' in classify({'nombre':'Diplomado online en TEA','descripcion':'Formación online en neurodesarrollo','productos_solicitados':[]})['mode'].lower()
print(f'PRUEBAS V3.1: {len(CASOS)} casos de clasificación + 2 pruebas de modalidad OK')
