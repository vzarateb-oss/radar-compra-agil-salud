"""Vista previa aislada Radar V4. Ejecutar con:
streamlit run app_v4_preview.py
Solo lee CSV de staging; no reemplaza app.py ni datos historicos.
"""
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Radar Compra Ágil Salud | V4 desarrollo",page_icon="🏥",layout="wide")
ROOT=Path(__file__).resolve().parent
STAGING=ROOT/"staging_dashboard_v4"
st.title("🏥 Radar Compra Ágil Salud")
st.caption("V4 · Vista de desarrollo · Datos piloto API · No corresponde a la base histórica completa")
@st.cache_data(ttl=120)
def load(name):
    p=STAGING/name
    return pd.read_csv(p,dtype=str,keep_default_na=False,encoding="utf-8-sig") if p.exists() else pd.DataFrame()
a=load("oportunidades_sanitarias_v4.csv")
c=load("revision_sanitaria_v4.csv")
confirmed=load("asincronicas_confirmadas_v4.csv")
online=load("online_pendiente_confirmacion_v4.csv")
if a.empty and c.empty:
    st.warning("Todavía no se han incorporado los archivos de staging. La versión pública permanece sin cambios.")
    st.code("python scripts/preparar_dashboard_v4.py staging_radar_v4/detalles_crudos_v4.jsonl staging_dashboard_v4")
    st.stop()
assert not (set(confirmed.get("Codigo",[])) & set(online.get("Codigo",[]))),"Grupos de modalidad duplicados"
assert all("asincrónica explícita" in m.lower() for m in confirmed.get("Modalidad",[])),"Modalidad no confirmada entre las explícitas"
st.sidebar.header("Filtros de oportunidades")
df=a.copy()
if "Region" in df:
    regions=sorted(v for v in df["Region"].unique() if v)
    chosen=st.sidebar.multiselect("Región",regions,default=regions)
    df=df[df["Region"].isin(chosen)] if regions else df
q=st.sidebar.text_input("Buscar curso, código o comprador").strip()
if q:
    cols=[x for x in ["Codigo","Nombre oportunidad","Organismo comprador","Descripcion"] if x in df]
    df=df[df[cols].apply(lambda x:x.str.contains(q,case=False,regex=False,na=False)).any(axis=1)]
t1,t2,t3,t4,t5=st.tabs(["📊 Panorama","🔎 Oportunidades","💻 Online asincrónico","🏛️ Compradores","🔬 Revisión sanitaria"])
with t1:
    x,y,z,w=st.columns(4)
    x.metric("Sanitarias confirmadas A",len(df))
    y.metric("Compradores",df["Organismo comprador"].replace("",pd.NA).nunique() if not df.empty else 0)
    z.metric("Asincrónicas explícitas",len(confirmed))
    w.metric("Pendientes revisión C",len(c))
    st.info("Muestra piloto: dos páginas por término. No representa todo el mercado ni permite estimar cuotas de mercado.")
    if not df.empty:
        st.subheader("Modalidades detectadas")
        st.bar_chart(df["Modalidad"].value_counts())
with t2:
    st.subheader("Capacitaciones sanitarias A")
    st.dataframe(df,use_container_width=True,hide_index=True)
    st.download_button("Exportar selección",df.to_csv(index=False).encode("utf-8-sig"),"oportunidades_v4_preview.csv","text/csv")
with t3:
    st.subheader("Asincronía explícitamente confirmada en texto API")
    st.caption("No se considera confirmada una capacitación solo por ser online o autogestionada. Revisar adjuntos antes de ofertar.")
    st.dataframe(confirmed,use_container_width=True,hide_index=True)
    st.subheader("Online / autogestionadas con asincronía por verificar")
    st.dataframe(online,use_container_width=True,hide_index=True)
with t4:
    if df.empty:st.info("Sin compradores en el filtro actual.")
    else:
        st.dataframe(df["Organismo comprador"].value_counts().rename_axis("Organismo comprador").reset_index(name="Oportunidades"),hide_index=True,use_container_width=True)
with t5:
    st.caption("Categoría C no se mezcla con las capacitaciones sanitarias confirmadas.")
    st.dataframe(c,use_container_width=True,hide_index=True)
st.divider()
st.caption("El piloto API y el snapshot comercial histórico se muestran por separado; no se suman sus métricas.")

# Inteligencia comercial histórica: snapshot existente, no universo completo de 2026.
@st.cache_data(ttl=120)
def load_historical(name):
    p=ROOT/f"{name}.csv"
    return pd.read_csv(p,dtype=str,keep_default_na=False,encoding="utf-8-sig") if p.exists() else pd.DataFrame()

hist_clas=load_historical("clasificacion")
hist_adj=load_historical("adjudicaciones")
hist_of=load_historical("ofertas")

def money_column(frame, column):
    if column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column],errors="coerce")

def format_clp(number):
    return "$"+f"{number:,.0f}".replace(",", ".")

st.header("📈 Inteligencia comercial · Snapshot histórico")
st.caption("Sección separada del piloto V4. Archivos históricos disponibles en GitHub; cobertura parcial, no corresponde a todas las compras de 2026.")
tab_comp,tab_prices,tab_selection,tab_coverage=st.tabs(
    ["🏢 Competidores y ofertas","💰 Precios observados","🏆 Selecciones y OC","📋 Cobertura y calidad"]
)
with tab_comp:
    st.subheader("Proveedores que presentaron ofertas")
    if hist_of.empty or "Proveedor" not in hist_of:
        st.info("No hay ofertas históricas disponibles.")
    else:
        provider_counts=(hist_of[hist_of["Proveedor"].str.strip().ne("")]
            .groupby(["Proveedor","RUT proveedor"],dropna=False)
            .agg(Ofertas=("Proveedor","size"),
                 Compras=("Codigo Compra Agil","nunique"))
            .reset_index().sort_values(["Ofertas","Proveedor"],ascending=[False,True]))
        st.dataframe(provider_counts,use_container_width=True,hide_index=True)
        st.caption("Participaciones registradas, no cuota de mercado ni número de adjudicaciones.")
        st.subheader("Detalle de ofertas")
        columns=[c for c in ["Codigo Compra Agil","Proveedor","RUT proveedor","Proveedor seleccionado",
                             "Monto total oferta","Moneda","Fecha cotizacion"] if c in hist_of]
        st.dataframe(hist_of[columns],use_container_width=True,hide_index=True)
with tab_prices:
    st.subheader("Montos de ofertas registrados")
    if hist_of.empty or "Monto total oferta" not in hist_of:
        st.info("No hay montos de ofertas disponibles.")
    else:
        prices=hist_of.copy()
        prices["Monto numérico"]=money_column(prices,"Monto total oferta")
        prices=prices[prices["Moneda"].str.upper().eq("CLP") & prices["Monto numérico"].notna()]
        if prices.empty:
            st.info("No hay montos CLP comparables.")
        else:
            c1,c2,c3=st.columns(3)
            c1.metric("Ofertas CLP",len(prices))
            c2.metric("Mediana de oferta",format_clp(prices["Monto numérico"].median()))
            c3.metric("Rango observado",format_clp(prices["Monto numérico"].min())+" – "+format_clp(prices["Monto numérico"].max()))
            st.dataframe(prices[[c for c in ["Codigo Compra Agil","Proveedor","Monto numérico","Moneda","Proveedor seleccionado"] if c in prices]],use_container_width=True,hide_index=True)
            st.warning("Estos son valores de ofertas, no precios efectivamente pagados. La muestra es pequeña y no permite inferir precios de mercado.")
with tab_selection:
    st.subheader("Seguimiento de proveedores seleccionados")
    if hist_adj.empty:
        st.info("No hay registros de seguimiento de selección.")
    else:
        st.metric("Registros de seguimiento",len(hist_adj))
        columns=[c for c in ["Codigo Compra Agil","Nombre oportunidad","Proveedor seleccionado / adjudicatario",
                             "RUT proveedor","Estado seguimiento","Codigo publico OC","Oferta seleccionada total","Monto OC","Moneda"] if c in hist_adj]
        st.dataframe(hist_adj[columns],use_container_width=True,hide_index=True)
        confirmed_oc=hist_adj["Codigo publico OC"].astype(str).str.strip().ne("") if "Codigo publico OC" in hist_adj else pd.Series(False,index=hist_adj.index)
        st.metric("Registros con código público de OC",int(confirmed_oc.sum()))
        st.caption("La selección de proveedor no acredita emisión de OC, recepción del servicio ni pago. El código público de OC es un indicador de seguimiento, no prueba de pago.")
with tab_coverage:
    st.subheader("Fuentes y alcance")
    stats=pd.DataFrame([
        {"Fuente":"Piloto V4 API","Registros":105,"Uso":"Clasificación de oportunidades; muestra limitada"},
        {"Fuente":"Clasificación histórica","Registros":len(hist_clas),"Uso":"Clasificaciones originales A/B/C; no mezclar sin deduplicar"},
        {"Fuente":"Ofertas históricas","Registros":len(hist_of),"Uso":"Ofertas y participantes registrados"},
        {"Fuente":"Seguimiento de selección","Registros":len(hist_adj),"Uso":"Proveedor seleccionado y estado de OC"}
    ])
    st.dataframe(stats,use_container_width=True,hide_index=True)
    st.info("Los datos provienen de dos capturas con coberturas distintas. No se suman como un censo anual ni se interpretan como tendencias temporales representativas.")
    if not hist_clas.empty and "Codigo" in hist_clas:
        overlap=set(hist_clas["Codigo"]) & set(a["Codigo"])
        st.write(f"Compras repetidas entre clasificación histórica y oportunidades A del piloto: **{len(overlap)}**.")
st.divider()
st.caption("Próxima fase: ampliar cobertura de 2026, validar fechas y asociar cada oferta y OC a su oportunidad sanitaria antes de calcular tendencias o rankings de adjudicación.")
