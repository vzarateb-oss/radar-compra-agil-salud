"""Prepara archivos V4 para un futuro dashboard, usando exclusivamente cache API.
No modifica CSV de produccion, no consulta API y no publica en Streamlit.
Uso: python scripts/preparar_dashboard_v4.py detalles_crudos.jsonl carpeta_salida
"""
import collections
import csv
import json
import sys
from pathlib import Path
from actualizar_radar_v4 import classify

COLS=["Codigo","Nombre oportunidad","Organismo comprador","RUT organismo comprador","Region","Estado","Fecha publicacion","Fecha cierre","Presupuesto CLP","Ofertas recibidas","Pertinencia sanitaria","Modalidad","Evidencia sanitaria","Justificacion","Descripcion","Productos solicitados","Revisar adjuntos"]
def save_csv(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLS,extrasaction="ignore");w.writeheader();w.writerows(rows)

def build(source,target):
    target=Path(target);target.mkdir(parents=True,exist_ok=True)
    groups={"A":[],"C":[],"EXCLUIDA":[],"PENDIENTE":[]}
    seen=set()
    for n,line in enumerate(Path(source).read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():continue
        entry=json.loads(line);code=str(entry["codigo"])
        if code in seen:raise ValueError("Codigo duplicado: "+code)
        seen.add(code);d=entry["detalle"];c=classify(d)
        inst=d.get("institucion") or {};dates=d.get("fechas") or {};budget=d.get("presupuesto") or {};summary=d.get("resumen") or {}
        products=d.get("productos_solicitados") or []
        row={"Codigo":code,"Nombre oportunidad":d.get("nombre",""),"Organismo comprador":inst.get("organismo_comprador",""),"RUT organismo comprador":inst.get("rut",""),"Region":inst.get("nombre_region",""),"Estado":(d.get("estado") or {}).get("glosa",""),"Fecha publicacion":dates.get("fecha_publicacion",""),"Fecha cierre":dates.get("fecha_cierre",""),"Presupuesto CLP":budget.get("monto_disponible_clp",""),"Ofertas recibidas":summary.get("total_ofertas_recibidas",""),"Pertinencia sanitaria":c["decision"],"Modalidad":c["mode"],"Evidencia sanitaria":c["health"],"Justificacion":c["reason"],"Descripcion":d.get("descripcion",""),"Productos solicitados":" | ".join(str(p.get("nombre","")) for p in products if isinstance(p,dict)),"Revisar adjuntos":"SI" if d.get("documentos") else "NO"}
        groups[c["decision"]].append(row)
    accepted=groups["A"];review=groups["C"]
    async_confirmed=[r for r in accepted if "asincrónica explícita" in r["Modalidad"].lower()]
    async_review=[r for r in accepted if "autogestionada" in r["Modalidad"].lower() or ("online" in r["Modalidad"].lower() and r not in async_confirmed)]
    save_csv(target/"oportunidades_sanitarias_v4.csv",accepted)
    save_csv(target/"revision_sanitaria_v4.csv",review)
    save_csv(target/"exclusiones_auditoria_v4.csv",groups["EXCLUIDA"])
    save_csv(target/"asincronicas_confirmadas_v4.csv",async_confirmed)
    save_csv(target/"online_pendiente_confirmacion_v4.csv",async_review)
    report={"registros_evaluados":len(seen),"sanitarias_A":len(accepted),"revision_C":len(review),"excluidas":len(groups["EXCLUIDA"]),"pendientes":len(groups["PENDIENTE"]),"asincronicas_confirmadas":len(async_confirmed),"online_o_autogestionadas_pendientes":len(async_review),"origen":"cache API piloto 45021559147","alcance":"dos paginas por termino; muestra no exhaustiva","estado":"STAGING; no apto para publicacion sin validacion humana"}
    (target/"resumen_dashboard_v4.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("STAGING_DASHBOARD_V4: "+json.dumps(report,ensure_ascii=False))
    return report

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("Uso: preparar_dashboard_v4.py detalles.jsonl carpeta_salida")
    build(sys.argv[1],sys.argv[2])
