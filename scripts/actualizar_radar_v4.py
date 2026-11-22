"""Radar Compra Ágil Salud V4 piloto: auditoría completa en staging, nunca modifica producción.
Clasificador heurístico provisional. No equivale a la versión Apps Script V3.8.1.
"""
import csv
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = 'https://api2.mercadopublico.cl'
TICKET = os.environ.get('MERCADOPUBLICO_TICKET', '').strip()
TERMINOS = ('capacitacion', 'curso', 'diplomado', 'formacion', 'educacion continua', 'entrenamiento')
PAGINAS = max(1, min(int(os.getenv('RADAR_PAGINAS', '2')), 5))
MAX_DETALLES = max(1, min(int(os.getenv('RADAR_DETALLES_MAX', '150')), 300))
SALIDA = Path('staging_radar_v4')
FORMACION = ('capacitaciones','capacitacion','curso','diplomado','formacion','taller','entrenamiento','certificacion','educacion continua','perfeccionamiento','instruccion','e-learning','elearning','simulacion clinica')
SALUD_FUERTE = ('enfermeria','farmacologia','farmacia','medicina','medico','medica','clinico','clinica','paciente','hospital','salud publica','odontologia','kinesiologia','obstetricia','matroneria','nutricion clinica','laboratorio clinico','urgencia','reanimacion','rcp','primeros auxilios','iaas','epidemiologia','salud mental','psiquiatria','psicologia clinica','imagenologia','radiologia','paramedico','tens','esterilizacion','hemodialisis','pabellon quirurgico','cuidados paliativos','fisioterapia','atencion primaria','aps','bioseguridad','vacunacion','inmunizacion','farmacovigilancia','neurodesarrollo','autismo','espectro autista','tea','informatica clinica','gestion asistencial','intercultural en salud','salud indigena','pueblos indigenas','mas ama','envejecimiento saludable','estimulacion cognitiva','promocion de salud','estilos de vida saludables')
SALUD_AMBIGUA = ('salud','sanitario','sanitaria','biologia','nutricion','psicologia','terapia','discapacidad','adulto mayor','cuidado','autocuidado','bienestar laboral')
NO_FORMATIVO = ('coffee break','coffe break','colaciones','colacion','catering','banqueteria','alimentacion','suministro de alimentos','galletas','vasos de servicio','servicio de traslado','servicio de transporte','arriendo de vehiculo','arriendo de sala','mantencion de','mantenimiento de','reparacion de','examenes de','prestacion de examenes','insumos medicos','equipamiento','medicamentos','material de oficina')
PRODUCTOS_NO_FORMATIVOS = ('suministro de alimentos','galletas','cafe instantaneo','te instantaneo','vasos de servicio','jugos y nectares','mantelillos','bandejas o fuentes')
ASINCRONIA = ('asincronic','autoinstruccional','auto instruccional','a su ritmo','on demand','bajo demanda')
AUTOGESTION = ('autogestionad', 'auto gestionad', 'autoguiad', 'autoaprendizaje')
ONLINE = ('online','en linea','virtual','e-learning','elearning','a distancia','remoto','plataforma virtual')
PRESENCIAL = ('presencial','en terreno','en aula')
CAMPOS = ['Codigo','Nombre oportunidad','Organismo comprador','RUT organismo comprador','Region','Estado','Fecha publicacion','Fecha cierre','Presupuesto CLP','Ofertas recibidas','Pertinencia sanitaria','Modalidad','Justificacion','Evidencia formativa','Evidencia sanitaria','Evidencia modalidad','Descripcion','Productos solicitados','Revisar adjuntos','Fecha extraccion UTC']
AUDIT = ['Codigo','Nombre oportunidad','Decision','Motivo','Evidencia formativa','Evidencia sanitaria','Evidencia exclusion','Modalidad','Evidencia modalidad','Productos solicitados','Descripcion','Detalle consultado','Objeto de compra','Evidencia objeto']

def norm(v):
    v = unicodedata.normalize('NFKD', str(v or '').lower())
    return re.sub(r'\s+', ' ', ''.join(c for c in v if not unicodedata.combining(c))).strip()

def hits(text, terms):
    return [x for x in terms if re.search(r'(?<!\w)' + re.escape(x) + r'(?!\w)', text)]

def api(session, path, params=None):
    last = None
    for n in range(5):
        try:
            r = session.get(BASE + path, params=params, timeout=(10, 35))
            r.raise_for_status()
            obj = r.json()
            if not isinstance(obj, dict) or obj.get('success') != 'OK':
                raise ValueError('Respuesta API sin success=OK')
            return obj.get('payload')
        except (requests.RequestException, ValueError) as e:
            last = e
            if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code in (400,401,403,404):
                break
            if n < 4:
                time.sleep(min(2 ** n, 12))
    status = (last.response.status_code if isinstance(last, requests.HTTPError) and last.response is not None else None)
    raise RuntimeError((f'HTTP {status}' if status else type(last).__name__) + ' en ' + path)

# Las reglas se inspiran en la lógica de exclusión por objeto de compra de
# Radar Apps Script V3.8.1, pero NO son una transcripción equivalente.
BIENES_TITULO = (
    'insumos', 'implementos', 'materiales', 'equipamiento', 'equipos de',
    'articulos de', 'suministro', 'adquisicion de', 'compra de', 'coffee break',
    'coffe break', 'colaciones', 'catering', 'banqueteria', 'alimentacion para',
    'servicio de alimentacion', 'arriendo de', 'traslado de', 'transporte de',
    'reparacion', 'mantencion', 'mantenimiento', 'examenes de', 'prestacion de examenes',
    'medicamentos', 'vestuario', 'implementacion deportiva', 'actividad fisica convenio',
    'jornada de esparcimiento', 'jornada recreativa', 'recreacion',
    'folletos', 'material publicitario', 'publicidad', 'articulos de escritorio',
    'pizarras', 'utiles de oficina', 'articulos de oficina',
)
BIENES_PRODUCTO = (
    'electrodo', 'bandas elasticas', 'banda elastica', 'pesas', 'colchonetas',
    'balones', 'pelotas', 'mancuernas', 'implementos deportivos', 'insumos',
    'coffee break', 'colaciones', 'galletas', 'vasos', 'cafe instantaneo',
    'alimentacion', 'equipamiento', 'materiales', 'suministros',
    'cucharas', 'tenedores', 'cubiertos', 'bandejas', 'folletos',
    'material publicitario', 'pizarras', 'perforadoras', 'papeleria',
)
SERVICIO_FORMATIVO = (
    'capacitaciones', 'servicio de capacitacion', 'capacitacion', 'curso', 'diplomado', 'formacion',
    'servicio de inscripcion a curso', 'inscripcion a curso', 'licencias/cupos',
    'cupos para diplomado', 'taller formativo', 'horas pedagogicas',
    'programa formativo', 'programa academico', 'relatoria',
    'sesiones formativas', 'capacitacion de funcionarios',
)
# "jornada" o "entrenamiento" aislados NO demuestran compra de capacitación.
CONTEXTO_NO_FORMATIVO = ('para capacitacion', 'para curso', 'durante capacitacion',
                         'en el marco de capacitacion', 'actividad de capacitacion')


def classify(d):
    title = norm(d.get('nombre'))
    description = norm(d.get('descripcion'))
    products = d.get('productos_solicitados') or []
    product_names = norm(' '.join(str(p.get('nombre','')) for p in products if isinstance(p,dict)))
    products_text = norm(' '.join(str(p.get('nombre','')) + ' ' + str(p.get('descripcion','')) for p in products if isinstance(p,dict)))
    primary = title + ' ' + description
    text = primary + ' ' + products_text
    f = hits(text, FORMACION)
    s = hits(text, SALUD_FUERTE)
    a = hits(text, SALUD_AMBIGUA)
    title_goods = hits(title, BIENES_TITULO)
    product_goods = hits(product_names, BIENES_PRODUCTO)
    strong_education = hits(title, SERVICIO_FORMATIVO) + hits(product_names, SERVICIO_FORMATIVO)
    # Evidencia del bien adquirido prevalece sobre palabras de contexto sanitario.
    goods_product_hits = hits(products_text, BIENES_PRODUCTO)
    educational_product = bool(hits(product_names, SERVICIO_FORMATIVO))
    educational_title = bool(hits(title, SERVICIO_FORMATIVO))
    dominant_goods = bool(product_goods or goods_product_hits) and not educational_product
    goods_title_strong = bool(title_goods) and not educational_title
    auxiliary = hits(title, NO_FORMATIVO)
    context_only = hits(description, CONTEXTO_NO_FORMATIVO)

    # Paso 1: objeto de la contratación. Los términos sanitarios NO anulan
    # la evidencia de adquisición de insumos o servicios auxiliares.
    if goods_title_strong:
        decision, reason, obj = 'EXCLUIDA', 'Título identifica compra de bienes, insumos o actividad no formativa', 'Bien/servicio no formativo'
    elif auxiliary and not strong_education:
        decision, reason, obj = 'EXCLUIDA', 'Servicio auxiliar no formativo', 'Bien/servicio no formativo'
    elif dominant_goods and not educational_product:
        decision, reason, obj = 'EXCLUIDA', 'Productos solicitados identifican bienes o materiales, aunque se mencione capacitación', 'Bien/servicio no formativo'
    elif not f or (not strong_education and context_only and not hits(title, ('capacitacion','diplomado','curso','formacion'))):
        decision, reason, obj = 'EXCLUIDA', 'No se acredita contratación de servicio formativo', 'Sin formación acreditada'
    elif not strong_education and not hits(description, ('horas pedagogicas','relator','programa formativo','curso','diplomado','capacitacion')):
        decision, reason, obj = 'EXCLUIDA', 'Mención formativa insuficiente para acreditar el objeto', 'Sin formación acreditada'
    else:
        obj = 'Servicio formativo'
        if s:
            decision, reason = 'A', 'Servicio formativo con contenido sanitario específico'
        elif a:
            decision, reason = 'C', 'Servicio formativo con pertinencia sanitaria ambigua: revisar'
        else:
            decision, reason = 'EXCLUIDA', 'Servicio formativo sin contenido sanitario acreditado'

    # Paso 2: modalidad: no inferir asincronía de "online" ni "a distancia".
    async_hits = [x for x in ASINCRONIA if x in primary]
    online_hits = hits(primary, ONLINE)
    autogestion = [x for x in AUTOGESTION if x in primary]
    presencial_hits = hits(primary, PRESENCIAL)
    neg_online = bool(re.search(r'no (?:se acepta|cotizar|admite|permite).*?(?:online|virtual|a distancia)',primary))
    if neg_online:
        modalidad = 'Presencial / online no admitido'
    elif async_hits and presencial_hits:
        modalidad = 'Mixta o contradictoria: revisar'
    elif async_hits:
        modalidad = 'Online asincrónica explícita' if online_hits else 'Asincrónica explícita'
    elif online_hits and presencial_hits:
        modalidad = 'Mixta / revisar'
    elif online_hits and autogestion:
        modalidad = 'Online autogestionada; asincronía no confirmada'
    elif online_hits:
        modalidad = 'Online / distancia; asincronía no confirmada'
    elif presencial_hits:
        modalidad = 'Presencial'
    else:
        modalidad = 'No determinada'
    return dict(decision=decision, reason=reason, form='; '.join(f[:5]),
                health='; '.join((s+a)[:7]),negative='; '.join((title_goods+product_goods+goods_product_hits+auxiliary)[:7]),
                mode=modalidad,mode_evidence='; '.join((async_hits+online_hits+autogestion+presencial_hits)[:6]),
                obj=obj,obj_evidence='; '.join((title_goods+product_goods+goods_product_hits+strong_education)[:8]))

def write_csv(name, rows, cols):
    with (SALIDA/name).open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
    if not TICKET:
        print('ERROR: secreto MERCADOPUBLICO_TICKET no configurado');return 1
    SALIDA.mkdir(exist_ok=True)
    s=requests.Session();s.headers.update({'ticket':TICKET,'Accept':'application/json'})
    found={};failures=[];listing_pages=0
    for term in TERMINOS:
        for page in range(1,PAGINAS+1):
            try:
                payload=api(s,'/v2/compra-agil',{'q':term,'tamano_pagina':10,'numero_pagina':page})
                if not isinstance(payload,dict) or not isinstance(payload.get('items'),list):raise ValueError('Listado sin items')
                items=payload['items'];listing_pages+=1
                for item in items:
                    if isinstance(item,dict) and item.get('codigo'):found.setdefault(str(item['codigo']),item)
                print(f'LISTADO OK: {term} página {page}, {len(items)} registros')
                pg=payload.get('paginacion') or {}
                if len(items)<10 or (isinstance(pg,dict) and pg.get('total_paginas') is not None and page>=int(pg['total_paginas'])):break
            except (RuntimeError,ValueError) as e:
                failures.append(f'Listado {term} página {page}: {e}');print(f'ADVERTENCIA: listado {term} página {page}');break
            time.sleep(.35)
    if not found:
        print('ERROR: ningún registro recuperado');return 1
    selected=list(found.items())[:MAX_DETALLES]
    accepted=[];audit=[];failed=0;raw_details=[]
    for i,(code,listing) in enumerate(selected,1):
        try:
            d=api(s,'/v2/compra-agil/'+requests.utils.quote(code,safe=''))
            if not isinstance(d,dict):raise ValueError('Detalle no es objeto')
            c=classify(d)
            raw_details.append({'codigo':code,'detalle':d})
            prod=' | '.join(str(p.get('nombre','')) for p in (d.get('productos_solicitados') or []) if isinstance(p,dict))
            audit.append({'Codigo':code,'Nombre oportunidad':d.get('nombre',''),'Decision':c['decision'],'Motivo':c['reason'],'Evidencia formativa':c['form'],'Evidencia sanitaria':c['health'],'Evidencia exclusion':c['negative'],'Modalidad':c['mode'],'Evidencia modalidad':c['mode_evidence'],'Productos solicitados':prod,'Descripcion':d.get('descripcion',''),'Detalle consultado':'SI','Objeto de compra':c['obj'],'Evidencia objeto':c['obj_evidence']})
            if c['decision'] in ('A','C'):
                inst=d.get('institucion') or {};dates=d.get('fechas') or {};budget=d.get('presupuesto') or {};summary=d.get('resumen') or {}
                accepted.append({'Codigo':code,'Nombre oportunidad':d.get('nombre',''),'Organismo comprador':inst.get('organismo_comprador',''),'RUT organismo comprador':inst.get('rut',''),'Region':inst.get('nombre_region',''),'Estado':(d.get('estado') or {}).get('glosa',''),'Fecha publicacion':dates.get('fecha_publicacion',''),'Fecha cierre':dates.get('fecha_cierre',''),'Presupuesto CLP':budget.get('monto_disponible_clp',''),'Ofertas recibidas':summary.get('total_ofertas_recibidas',''),'Pertinencia sanitaria':c['decision'],'Modalidad':c['mode'],'Justificacion':c['reason'],'Evidencia formativa':c['form'],'Evidencia sanitaria':c['health'],'Evidencia modalidad':c['mode_evidence'],'Descripcion':d.get('descripcion',''),'Productos solicitados':prod,'Revisar adjuntos':'SI: modalidad/alcance puede constar en adjuntos' if (d.get('documentos') or []) else 'NO','Fecha extraccion UTC':datetime.now(timezone.utc).isoformat()})
        except (RuntimeError,ValueError) as e:
            failed+=1;failures.append(f'Detalle {code}: {e}');audit.append({'Codigo':code,'Nombre oportunidad':listing.get('nombre',''),'Decision':'PENDIENTE','Motivo':str(e),'Detalle consultado':'NO','Objeto de compra':'No determinado','Evidencia objeto':''});print(f'ADVERTENCIA: detalle {i}/{len(selected)} {code}')
        time.sleep(.35)
    with (SALIDA/'detalles_crudos_v4.jsonl').open('w',encoding='utf-8') as raw_file:
        for item in raw_details:
            raw_file.write(json.dumps(item,ensure_ascii=False,default=str)+'\n')
    write_csv('clasificacion_v4.csv',accepted,CAMPOS)
    write_csv('auditoria_v4.csv',audit,AUDIT)
    counts={k:sum(x.get('Decision')==k for x in audit) for k in ('A','C','EXCLUIDA','PENDIENTE')}
    report={'ejecucion_completa':not failures and len(selected)==len(found),'paginas_listado_esperadas_maximo':len(TERMINOS)*PAGINAS,'fecha_utc':datetime.now(timezone.utc).isoformat(),'paginas_por_termino':PAGINAS,'paginas_listado_exitosas':listing_pages,'oportunidades_unicas_encontradas':len(found),'detalles_intentados':len(selected),'detalles_sin_procesar_por_limite':max(0,len(found)-len(selected)),'clasificacion':counts,'detalles_fallidos':failed,'fallos':failures,'advertencia':'Heurística V4 piloto provisional: requiere validación humana, auditoría de exclusiones y comparación con Apps Script V3.8.1. No procesa adjuntos, ofertas ni adjudicaciones. No modifica producción.'}
    (SALIDA/'reporte_v4.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESUMEN: '+json.dumps({k:v for k,v in report.items() if k not in ('fallos','advertencia')},ensure_ascii=False))
    print('ARCHIVOS: staging_radar_v4/clasificacion_v4.csv, auditoria_v4.csv, detalles_crudos_v4.jsonl, reporte_v4.json')
    print('No se modificaron CSV de producción ni Google Sheets.')
    if failures or len(selected)<len(found):
        print('ERROR: ejecución incompleta; NO apta para publicación. Revisar reporte_v4.json')
        return 1
    print('VALIDACION: ejecución completa para el alcance configurado; requiere revisión humana antes de publicar.')
    return 0

if __name__=='__main__':sys.exit(main())
