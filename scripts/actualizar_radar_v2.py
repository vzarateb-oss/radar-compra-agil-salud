"""Radar Compra Ágil Salud V2: auditoría completa en staging, nunca modifica producción.
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
SALIDA = Path('staging_radar_v2')
FORMACION = ('capacitacion','curso','diplomado','formacion','taller','entrenamiento','certificacion','educacion continua','perfeccionamiento','instruccion','e-learning','elearning','simulacion clinica')
SALUD_FUERTE = ('enfermeria','farmacologia','farmacia','medicina','medico','medica','clinico','clinica','paciente','hospital','salud publica','odontologia','kinesiologia','obstetricia','matroneria','nutricion clinica','laboratorio clinico','urgencia','reanimacion','rcp','primeros auxilios','iaas','epidemiologia','salud mental','psiquiatria','psicologia clinica','imagenologia','radiologia','paramedico','tens','esterilizacion','hemodialisis','pabellon quirurgico','cuidados paliativos','fisioterapia','atencion primaria','aps','bioseguridad','vacunacion','inmunizacion','farmacovigilancia','neurodesarrollo','autismo','espectro autista','tea','informatica clinica','gestion asistencial','intercultural en salud','salud indigena','pueblos indigenas')
SALUD_AMBIGUA = ('salud','sanitario','sanitaria','biologia','nutricion','psicologia','terapia','discapacidad','adulto mayor','cuidado')
NO_FORMATIVO = ('coffee break','coffe break','colaciones','colacion','catering','banqueteria','alimentacion','suministro de alimentos','galletas','vasos de servicio','servicio de traslado','servicio de transporte','arriendo de vehiculo','arriendo de sala','mantencion de','mantenimiento de','reparacion de','examenes de','prestacion de examenes','insumos medicos','equipamiento','medicamentos','material de oficina')
PRODUCTOS_NO_FORMATIVOS = ('suministro de alimentos','galletas','cafe instantaneo','te instantaneo','vasos de servicio','jugos y nectares','mantelillos','bandejas o fuentes')
ASINCRONIA = ('asincronic','autoinstruccional','auto instruccional','a su ritmo','on demand','bajo demanda')
ONLINE = ('online','en linea','virtual','e-learning','elearning','a distancia','remoto','plataforma virtual')
PRESENCIAL = ('presencial','en terreno','en aula')
CAMPOS = ['Codigo','Nombre oportunidad','Organismo comprador','RUT organismo comprador','Region','Estado','Fecha publicacion','Fecha cierre','Presupuesto CLP','Ofertas recibidas','Pertinencia sanitaria','Modalidad','Justificacion','Evidencia formativa','Evidencia sanitaria','Evidencia modalidad','Descripcion','Productos solicitados','Revisar adjuntos','Fecha extraccion UTC']
AUDIT = ['Codigo','Nombre oportunidad','Decision','Motivo','Evidencia formativa','Evidencia sanitaria','Evidencia exclusion','Modalidad','Evidencia modalidad','Productos solicitados','Descripcion','Detalle consultado']

def norm(v):
    v = unicodedata.normalize('NFKD', str(v or '').lower())
    return re.sub(r'\s+', ' ', ''.join(c for c in v if not unicodedata.combining(c))).strip()

def hits(text, terms):
    return [x for x in terms if re.search(r'(?<!\w)' + re.escape(x) + r'(?!\w)', text)]

def api(session, path, params=None):
    last = None
    for n in range(3):
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
            if n < 2:
                time.sleep(n + 2)
    raise RuntimeError(type(last).__name__ + ' en ' + path)

def classify(d):
    title = norm(d.get('nombre'))
    description = norm(d.get('descripcion'))
    products = d.get('productos_solicitados') or []
    products_text = norm(' '.join(str(p.get('nombre','')) + ' ' + str(p.get('descripcion','')) for p in products if isinstance(p,dict)))
    text = title + ' ' + description + ' ' + products_text
    f = hits(text, FORMACION)
    s = hits(text, SALUD_FUERTE)
    a = hits(text, SALUD_AMBIGUA)
    negative = hits(title + ' ' + description, NO_FORMATIVO)
    product_negative = hits(products_text, PRODUCTOS_NO_FORMATIVOS)
    # Excluir suministros auxiliares aun si el comprador menciona un curso.
    if (negative and (product_negative or hits(title, NO_FORMATIVO))) and not hits(title, ('servicio de capacitacion','curso','diplomado','formacion')):
        decision, reason = 'EXCLUIDA', 'Compra accesoria/no formativa; capacitación solo contextual'
    elif not f:
        decision, reason = 'EXCLUIDA', 'Sin evidencia de servicio formativo'
    elif s:
        decision, reason = 'A', 'Capacitación con temática sanitaria específica'
    elif a:
        decision, reason = 'C', 'Capacitación posiblemente sanitaria; requiere revisión'
    else:
        decision, reason = 'EXCLUIDA', 'Formación sin evidencia sanitaria suficiente'
    # Solo evidencia explícita en título/descripción; no inferir desde categorías genéricas.
    primary = title + ' ' + description
    async_hits = [x for x in ASINCRONIA if x in primary]
    online_hits = hits(primary, ONLINE)
    presencial_hits = hits(primary, PRESENCIAL)
    if async_hits and presencial_hits:
        modalidad = 'Mixta o contradictoria: revisar'
    elif async_hits:
        modalidad = 'Asincrónica explícita' if not online_hits else 'Online asincrónica explícita'
    elif online_hits and presencial_hits:
        modalidad = 'Mixta / revisar'
    elif online_hits:
        modalidad = 'Online / distancia; asincronía no confirmada'
    elif presencial_hits:
        modalidad = 'Presencial'
    else:
        modalidad = 'No determinada'
    return dict(decision=decision, reason=reason, form='; '.join(f[:5]), health='; '.join((s+a)[:7]), negative='; '.join((negative+product_negative)[:7]), mode=modalidad, mode_evidence='; '.join((async_hits+online_hits+presencial_hits)[:6]))

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
                if len(items)<10 or (isinstance(pg,dict) and page>=int(pg.get('total_paginas') or page)):break
            except (RuntimeError,ValueError) as e:
                failures.append(f'Listado {term} página {page}: {e}');print(f'ADVERTENCIA: listado {term} página {page}');break
            time.sleep(.35)
    if not found:
        print('ERROR: ningún registro recuperado');return 1
    selected=list(found.items())[:MAX_DETALLES]
    accepted=[];audit=[];failed=0
    for i,(code,listing) in enumerate(selected,1):
        try:
            d=api(s,'/v2/compra-agil/'+requests.utils.quote(code,safe=''))
            if not isinstance(d,dict):raise ValueError('Detalle no es objeto')
            c=classify(d)
            prod=' | '.join(str(p.get('nombre','')) for p in (d.get('productos_solicitados') or []) if isinstance(p,dict))
            audit.append({'Codigo':code,'Nombre oportunidad':d.get('nombre',''),'Decision':c['decision'],'Motivo':c['reason'],'Evidencia formativa':c['form'],'Evidencia sanitaria':c['health'],'Evidencia exclusion':c['negative'],'Modalidad':c['mode'],'Evidencia modalidad':c['mode_evidence'],'Productos solicitados':prod,'Descripcion':d.get('descripcion',''),'Detalle consultado':'SI'})
            if c['decision'] in ('A','C'):
                inst=d.get('institucion') or {};dates=d.get('fechas') or {};budget=d.get('presupuesto') or {};summary=d.get('resumen') or {}
                accepted.append({'Codigo':code,'Nombre oportunidad':d.get('nombre',''),'Organismo comprador':inst.get('organismo_comprador',''),'RUT organismo comprador':inst.get('rut',''),'Region':inst.get('nombre_region',''),'Estado':(d.get('estado') or {}).get('glosa',''),'Fecha publicacion':dates.get('fecha_publicacion',''),'Fecha cierre':dates.get('fecha_cierre',''),'Presupuesto CLP':budget.get('monto_disponible_clp',''),'Ofertas recibidas':summary.get('total_ofertas_recibidas',''),'Pertinencia sanitaria':c['decision'],'Modalidad':c['mode'],'Justificacion':c['reason'],'Evidencia formativa':c['form'],'Evidencia sanitaria':c['health'],'Evidencia modalidad':c['mode_evidence'],'Descripcion':d.get('descripcion',''),'Productos solicitados':prod,'Revisar adjuntos':'SI: modalidad/alcance puede constar en adjuntos' if (d.get('documentos') or []) else 'NO','Fecha extraccion UTC':datetime.now(timezone.utc).isoformat()})
        except (RuntimeError,ValueError) as e:
            failed+=1;failures.append(f'Detalle {code}: {e}');audit.append({'Codigo':code,'Nombre oportunidad':listing.get('nombre',''),'Decision':'PENDIENTE','Motivo':str(e),'Detalle consultado':'NO'});print(f'ADVERTENCIA: detalle {i}/{len(selected)} {code}')
        time.sleep(.35)
    write_csv('clasificacion_v2.csv',accepted,CAMPOS)
    write_csv('auditoria_v2.csv',audit,AUDIT)
    counts={k:sum(x.get('Decision')==k for x in audit) for k in ('A','C','EXCLUIDA','PENDIENTE')}
    report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'paginas_por_termino':PAGINAS,'paginas_listado_exitosas':listing_pages,'oportunidades_unicas_encontradas':len(found),'detalles_intentados':len(selected),'detalles_sin_procesar_por_limite':max(0,len(found)-len(selected)),'clasificacion':counts,'detalles_fallidos':failed,'fallos':failures,'advertencia':'Heurística V2 provisional: requiere validación humana, auditoría de exclusiones y comparación con Apps Script V3.8.1. No procesa adjuntos, ofertas ni adjudicaciones. No modifica producción.'}
    (SALIDA/'reporte_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESUMEN: '+json.dumps({k:v for k,v in report.items() if k not in ('fallos','advertencia')},ensure_ascii=False))
    print('ARCHIVOS: staging_radar_v2/clasificacion_v2.csv, auditoria_v2.csv, reporte_v2.json')
    print('No se modificaron CSV de producción ni Google Sheets.')
    return 0

if __name__=='__main__':sys.exit(main())
