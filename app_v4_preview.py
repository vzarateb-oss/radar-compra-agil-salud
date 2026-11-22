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
st.caption("Competidores, ofertas, precios adjudicados y tendencias históricas se integrarán cuando se disponga de datos verificados. No se infieren adjudicaciones desde una oportunidad publicada.")
