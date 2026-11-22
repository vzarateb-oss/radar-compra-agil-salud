"""Audita la captura real V4 sin volver a consultar Mercado Publico.
Uso: python scripts/auditar_cache_v4.py <detalles_crudos.jsonl> <auditoria_original.csv> <directorio_salida>
"""
import collections
import csv
import json
import sys
from pathlib import Path
from actualizar_radar_v4 import classify

def run(raw_path, old_path, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    old={r["Codigo"]:r for r in csv.DictReader(open(old_path,encoding="utf-8-sig",newline=""))}
    new=[];changes=[];modes=[]
    for line in Path(raw_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():continue
        item=json.loads(line);code=item["codigo"];detail=item["detalle"]
        c=classify(detail);prior=old[code]
        row={"Codigo":code,"Nombre oportunidad":detail.get("nombre",""),"Decision anterior":prior["Decision"],"Decision nueva":c["decision"],"Modalidad anterior":prior["Modalidad"],"Modalidad nueva":c["mode"],"Motivo":c["reason"]}
        new.append(row)
        if row["Decision anterior"]!=row["Decision nueva"]:changes.append(row)
        if row["Modalidad anterior"]!=row["Modalidad nueva"]:modes.append(row)
    assert len(new)==len(old)==105,(len(new),len(old))
    by_code={r["Codigo"]:r for r in new}
    assert by_code["2378-294-COT26"]["Decision nueva"]=="EXCLUIDA","RSH no sanitario debe excluirse"
    assert by_code["1237328-323-COT26"]["Modalidad nueva"].startswith("Online autogestionada"),"Más AMA debe identificarse online autogestionada"
    for code in ("875646-2859-COT26","507428-555-COT26"):
        assert by_code[code]["Decision nueva"]=="A",code
    counts=dict(collections.Counter(r["Decision nueva"] for r in new))
    report={"origen":"captura API real del piloto 45021559147","registros":len(new),"clasificacion":counts,"cambios_decision":changes,"cambios_modalidad":modes,"advertencia":"Muestra limitada a 2 paginas por termino; requiere revision humana. No publica datos ni consulta API."}
    (output/"auditoria_offline_v4.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (output/"comparacion_offline_v4.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(new[0]));w.writeheader();w.writerows(new)
    print("AUDITORIA_OFFLINE_RESUMEN: "+json.dumps({k:v for k,v in report.items() if k not in ("cambios_decision","cambios_modalidad","advertencia")},ensure_ascii=False))
    print("CAMBIOS_DECISION: "+json.dumps(changes,ensure_ascii=False))
    print("CAMBIOS_MODALIDAD: "+json.dumps(modes,ensure_ascii=False))
    return report

if __name__=="__main__":
    if len(sys.argv)!=4:raise SystemExit("Uso: auditar_cache_v4.py detalles.jsonl auditoria.csv salida")
    run(*sys.argv[1:])
