"""Pruebas locales con casos sintéticos; no requiere ticket ni API."""
from actualizar_radar_v3 import classify

CASOS = [
    ('Insumos rehabilitación APS universal', 'Electrodos y bandas para entrenamiento de pacientes', 'EXCLUIDA'),
    ('Insumos de actividad física convenio Más Salud', 'Implementos deportivos para actividad comunitaria', 'EXCLUIDA'),
    ('Coffee break para capacitación funcionarios de salud', 'Colaciones para curso', 'EXCLUIDA'),
    ('Jornada de esparcimiento y recreación', 'Actividad de discapacidad y salud comunitaria', 'EXCLUIDA'),
    ('Diplomado en enfermería oncológica', 'Curso de cuidados paliativos 100% asincrónico', 'A'),
    ('Diplomado online en TEA y neurodesarrollo', '15 cupos de formación online', 'A'),
    ('Formación intercultural en salud indígena', 'Curso para equipos de atención primaria', 'A'),
    ('Capacitación en autocuidado y bienestar laboral', 'Taller para equipos de trabajo', 'C'),
]
for titulo, descripcion, esperado in CASOS:
    actual = classify({'nombre':titulo, 'descripcion':descripcion, 'productos_solicitados':[]})['decision']
    assert actual == esperado, f'{titulo}: esperado {esperado}, recibido {actual}'
print(f'PRUEBAS CLASIFICADOR V3: {len(CASOS)}/{len(CASOS)} correctas')
