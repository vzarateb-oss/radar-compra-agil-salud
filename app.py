import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Radar Compra Ágil Salud", page_icon="🏥", layout="wide")
st.title("🏥 Radar Compra Ágil Salud")
st.caption("Inteligencia de mercado de capacitación sanitaria · Chile · Versión inicial")

DATA = Path(__file__).parent / "data" / "oportunidades_2026.csv"

@st.cache_data
def cargar_datos(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)

if not DATA.exists():
    st.info("La aplicación está publicada. Pendiente: conectar los registros reales de 2026 y programar la actualización automática mediante la API.")
    st.subheader("Módulos del Radar")
    for titulo, descripcion in [
        ("Panorama del mercado", "Oportunidades, presupuestos y tendencias"),
        ("Oportunidades vigentes", "Compras sanitarias clasificadas y priorizadas"),
        ("Compradores", "Organismos y demanda de capacitación"),
        ("Competidores", "Proveedores y adjudicaciones verificadas"),
        ("Capacitación asincrónica", "Oportunidades con evidencia explícita de modalidad"),
    ]:
        st.markdown(f"**{titulo}** — {descripcion}")
    st.stop()

df = cargar_datos(DATA)
if df.empty:
    st.warning("El archivo de datos existe, pero no contiene registros.")
    st.stop()

st.sidebar.header("Filtros")
if "Pertinencia sanitaria" in df.columns:
    opciones = sorted(df["Pertinencia sanitaria"].dropna().unique().tolist())
    seleccion = st.sidebar.multiselect("Pertinencia sanitaria", opciones, default=opciones)
    df = df[df["Pertinencia sanitaria"].isin(seleccion)]
if "Modalidad" in df.columns:
    opciones = sorted(df["Modalidad"].dropna().unique().tolist())
    seleccion = st.sidebar.multiselect("Modalidad", opciones, default=opciones)
    df = df[df["Modalidad"].isin(seleccion)]

tabs = st.tabs(["Panorama", "Oportunidades", "Compradores", "Competidores", "Online asincrónico"])
with tabs[0]:
    c1,c2,c3 = st.columns(3)
    c1.metric("Oportunidades", df["Codigo"].nunique() if "Codigo" in df else len(df))
    c2.metric("Organismos compradores", df["Organismo comprador"].nunique() if "Organismo comprador" in df else "Sin datos")
    c3.metric("Proveedores identificados", df["Proveedor"].replace("",pd.NA).nunique() if "Proveedor" in df else "Sin datos")
    if "Area tematica" in df:
        st.bar_chart(df["Area tematica"].value_counts())
with tabs[1]:
    st.dataframe(df, use_container_width=True, hide_index=True)
with tabs[2]:
    if "Organismo comprador" in df:
        st.dataframe(df["Organismo comprador"].value_counts().rename_axis("Comprador").reset_index(name="Oportunidades"), hide_index=True)
    else:
        st.info("Pendiente de integrar información de compradores.")
with tabs[3]:
    if "Proveedor" in df:
        st.dataframe(df[df["Proveedor"] != ""][["Proveedor"]].value_counts().reset_index(name="Registros"), hide_index=True)
    else:
        st.info("Pendiente de integrar proveedores y adjudicaciones verificadas.")
with tabs[4]:
    if "Modalidad" in df:
        asinc = df[df["Modalidad"].str.contains("asincr", case=False, na=False)]
        st.caption("Coincidencias textuales preliminares; la evidencia de modalidad se validará en la siguiente versión.")
        st.dataframe(asinc, use_container_width=True, hide_index=True)
    else:
        st.info("Pendiente de integrar modalidades.")
