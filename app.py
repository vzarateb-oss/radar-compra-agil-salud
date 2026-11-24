from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials
import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title='Radar Compra Ágil Salud', page_icon='🏥', layout='wide')
BASE = Path(__file__).resolve().parent

@st.cache_data(ttl=300)
def cargar(nombre):
    rutas = [BASE / f'{nombre}.csv', BASE / 'data' / f'{nombre}.csv']
    for ruta in rutas:
        if ruta.is_file():
            try:
                df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding='utf-8-sig')
                return df, str(ruta.relative_to(BASE)), ''
            except Exception as e:
                return pd.DataFrame(), str(ruta.relative_to(BASE)), str(e)
    return pd.DataFrame(), '', 'No existe el archivo en la raíz ni en data/'


ZONA_CHILE = ZoneInfo("America/Santiago")
RANGOS_RADAR = ["RADAR_EN_VIVO!A1:L", "RADAR_PROXIMAS!A1:M", "RADAR_PAC!A1:K"]


@st.cache_data(ttl=60)
def cargar_radar_privado():
    config = st.secrets["google_sheets"]
    cuenta = Credentials.from_service_account_info(
        dict(config["service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    hoja = config["spreadsheet_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", hoja):
        raise ValueError("Identificador de planilla inválido")
    with AuthorizedSession(cuenta) as session:
        response = session.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{hoja}/values:batchGet",
            params={"ranges": RANGOS_RADAR, "valueRenderOption": "FORMATTED_VALUE"},
            timeout=15,
        )
        response.raise_for_status()
        rangos = response.json()["valueRanges"]
    if len(rangos) != len(RANGOS_RADAR):
        raise ValueError("La respuesta no incluye todas las vistas del Radar")
    return [rango.get("values", []) for rango in rangos]


def tabla_radar(filas):
    if len(filas) < 4:
        raise ValueError("Vista sin encabezado")
    columnas = filas[3]
    valores = [(fila + [""] * len(columnas))[:len(columnas)] for fila in filas[4:]]
    return pd.DataFrame(valores, columns=columnas)


def texto_celda(filas, indice):
    return filas[indice][0] if len(filas) > indice and filas[indice] else ""


def fecha_chile(texto):
    for formato in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(texto, formato).replace(tzinfo=ZONA_CHILE)
        except ValueError:
            pass
    return None


def plazo(cierre, ahora):
    fecha = fecha_chile(cierre)
    if fecha is None:
        return "⚪ Por verificar", "Sin hora de cierre"
    segundos = int(fecha.timestamp() - ahora.timestamp())
    if segundos <= 0:
        return "⚪ Cerrada por plazo", "Plazo cerrado"
    horas, minutos = divmod((segundos + 59) // 60, 60)
    nivel = "🔴 Hasta 24 h" if segundos <= 86400 else "🟠 Hasta 72 h" if segundos <= 259200 else "🟢 Vigente"
    return nivel, f"{horas} h {minutos:02d} min"


def mostrar_abiertas(filas, asincronicas=False):
    st.subheader("Online asincrónico" if asincronicas else "Abiertas ahora")
    estado = texto_celda(filas, 1)
    st.caption(estado or "Sin captura de la API")
    nota = texto_celda(filas, 2)
    if estado.startswith("Captura parcial") or nota.startswith(("Intento parcial", "Sin datos nuevos")):
        st.warning(nota or "Cobertura parcial de la consulta.")
    ahora = datetime.now(ZONA_CHILE)
    fecha_captura = re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", estado)
    captura = fecha_chile(fecha_captura.group()) if fecha_captura else None
    if captura and ahora.timestamp() - captura.timestamp() > timedelta(hours=2).total_seconds():
        st.warning("La captura tiene más de dos horas de antigüedad.")
    datos = tabla_radar(filas)
    if not {"Código", "Cierre", "Modalidad", "Semáforo", "Tiempo restante"} <= set(datos.columns):
        st.error("La vista en vivo no tiene las columnas requeridas.")
        return
    datos = datos[datos["Código"].ne("")].copy()
    if asincronicas:
        datos = datos[datos["Modalidad"].str.contains(r"\basincr", case=False, regex=True)]
    plazos = [plazo(cierre, ahora) for cierre in datos["Cierre"]]
    datos["Semáforo"] = [p[0] for p in plazos]
    datos["Tiempo restante"] = [p[1] for p in plazos]
    vigentes = datos["Semáforo"].isin(["🔴 Hasta 24 h", "🟠 Hasta 72 h", "🟢 Vigente"])
    captura_disponible = estado.startswith(("Última consulta completa", "Captura parcial"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Vigentes en la captura", int(vigentes.sum()) if captura_disponible else "—")
    c2.metric("Cierran en 24 h", int(datos["Semáforo"].eq("🔴 Hasta 24 h").sum()) if captura_disponible else "—")
    c3.metric("Por verificar", int(datos["Semáforo"].eq("⚪ Por verificar").sum()) if captura_disponible else "—")
    solo_vigentes = st.toggle("Mostrar solo vigentes", value=True)
    consulta = st.text_input("Buscar por código, curso u organismo").strip()
    if solo_vigentes:
        datos = datos[vigentes]
    if consulta:
        columnas = [c for c in ["Código", "Oportunidad", "Organismo"] if c in datos]
        filtro = datos[columnas].apply(lambda c: c.str.contains(consulta, case=False, regex=False)).any(axis=1)
        datos = datos[filtro]
    if datos.empty:
        st.info("La captura disponible no tiene compras que coincidan con estos filtros.")
    else:
        st.dataframe(datos, hide_index=True, use_container_width=True,
                     column_config={"Ficha": st.column_config.LinkColumn("Mercado Público", display_text="Abrir ficha")})


def mostrar_futuras(filas):
    st.subheader("Próximas oportunidades")
    st.caption(texto_celda(filas, 1))
    st.info(texto_celda(filas, 2))
    datos = tabla_radar(filas)
    if "Prioridad" in datos:
        prioridad = st.selectbox("Prioridad", ["Todas", *dict.fromkeys(datos["Prioridad"])])
        if prioridad != "Todas":
            datos = datos[datos["Prioridad"].eq(prioridad)]
    if "Ventana estimada" in datos:
        ventana = st.selectbox("Ventana estimada", ["Todas", *sorted(set(datos["Ventana estimada"]))])
        if ventana != "Todas":
            datos = datos[datos["Ventana estimada"].eq(ventana)]
    st.dataframe(datos, hide_index=True, use_container_width=True)


def mostrar_pac(filas):
    st.subheader("Plan Anual de Compras")
    st.caption(texto_celda(filas, 1))
    st.info(texto_celda(filas, 2))
    st.dataframe(tabla_radar(filas), hide_index=True, use_container_width=True,
                 column_config={"Fuente": st.column_config.LinkColumn("Fuente oficial", display_text="Abrir documento")})


def mostrar_base_inicial():
    archivos = ['clasificacion', 'adjudicaciones', 'ofertas', 'oportunidades']
    resultados = {nombre: cargar(nombre) for nombre in archivos}
    clas, adj, ofertas, opp = [resultados[n][0] for n in archivos]


    with st.sidebar.expander('Diagnóstico de archivos', expanded=clas.empty):
        for nombre, (df, ruta, error) in resultados.items():
            if error:
                st.warning(f'{nombre}.csv: {error}')
            else:
                st.success(f'{ruta}: {len(df)} filas')

    if clas.empty:
        st.error('No fue posible cargar la base de clasificación sanitaria.')
        st.info('Comprueba que clasificacion.csv tenga datos y esté junto a app.py o dentro de data/. Si el archivo está vacío, vuelve a subir el CSV original.')
        st.stop()

    columnas_clas = ['Codigo', 'Pertinencia sanitaria', 'Modalidad', 'Area tematica', 'Organismo comprador']
    faltantes = [c for c in columnas_clas if c not in clas.columns]
    if faltantes:
        st.error('La base de clasificación no tiene las columnas esperadas: ' + ', '.join(faltantes))
        st.write('Columnas encontradas:', list(clas.columns))
        st.stop()

    # Mostrar únicamente las oportunidades sanitarias clasificadas A/B/C.
    clas = clas[clas['Pertinencia sanitaria'].str.match(r'^\s*[ABC](?:\s*[-–:]|\s*$)', case=False, na=False)].copy()
    if clas.empty:
        st.warning('No hay registros sanitarios A/B/C en esta exportación.')
        st.stop()

    st.sidebar.header('Filtros')
    def filtro(df, columna, etiqueta):
        if columna not in df.columns:
            return df
        opciones = sorted(x for x in df[columna].dropna().unique().tolist() if x)
        elegidos = st.sidebar.multiselect(etiqueta, opciones, default=opciones)
        return df[df[columna].isin(elegidos)]

    clas = filtro(clas, 'Pertinencia sanitaria', 'Pertinencia')
    clas = filtro(clas, 'Modalidad', 'Modalidad')
    clas = filtro(clas, 'Area tematica', 'Área temática')
    consulta = st.sidebar.text_input('Buscar compra, curso u organismo')
    if consulta:
        columnas_busqueda = [c for c in ['Codigo', 'Nombre oportunidad', 'Organismo comprador'] if c in clas.columns]
        if columnas_busqueda:
            mascara = clas[columnas_busqueda].apply(
                lambda serie: serie.str.contains(consulta, case=False, regex=False, na=False)
            ).any(axis=1)
            clas = clas[mascara]

    codigos = set(clas['Codigo'].astype(str))
    def filtrar_relacionados(df):
        if df.empty:
            return df
        codigo = next((c for c in ['Codigo Compra Agil', 'Codigo', 'CodigoCotizacion'] if c in df.columns), None)
        return df[df[codigo].astype(str).isin(codigos)] if codigo else pd.DataFrame()

    adj_f = filtrar_relacionados(adj)
    of_f = filtrar_relacionados(ofertas)

    def suma_clp(serie):
        valores = pd.to_numeric(serie, errors='coerce').fillna(0)
        return float(valores.sum())

    def formato_clp(valor):
        return '$' + f'{valor:,.0f}'.replace(',', '.')

    tabs = st.tabs(['📊 Panorama', '🔎 Oportunidades', '🏛️ Compradores', '🏆 Competidores', '💻 Online asincrónico'])
    with tabs[0]:
        a, b, c, d = st.columns(4)
        a.metric('Oportunidades sanitarias', clas['Codigo'].nunique())
        b.metric('Compradores', clas['Organismo comprador'].replace('', pd.NA).nunique())
        if {'Moneda', 'Presupuesto'}.issubset(clas.columns):
            presupuesto = suma_clp(clas.loc[clas['Moneda'].str.upper().eq('CLP'), 'Presupuesto'])
            c.metric('Presupuestos CLP declarados', formato_clp(presupuesto))
        else:
            c.metric('Presupuestos CLP declarados', 'Sin datos')
        d.metric('Ofertas registradas', len(of_f))
        st.caption('Los presupuestos se calculan solo para CLP. Las ofertas no equivalen a adjudicaciones ni pagos.')
        izquierda, derecha = st.columns(2)
        with izquierda:
            st.subheader('Áreas temáticas')
            st.bar_chart(clas['Area tematica'].value_counts())
        with derecha:
            st.subheader('Modalidades')
            st.bar_chart(clas['Modalidad'].value_counts())
        st.subheader('Clasificación sanitaria')
        st.dataframe(clas['Pertinencia sanitaria'].value_counts().rename_axis('Clasificación').reset_index(name='Compras'), hide_index=True)

    with tabs[1]:
        st.subheader('Oportunidades sanitarias A, B y C')
        st.caption('La categoría C requiere revisión; no se presenta como capacitación clínica confirmada.')
        st.dataframe(clas, use_container_width=True, hide_index=True)
        st.download_button('Descargar oportunidades filtradas', clas.to_csv(index=False).encode('utf-8-sig'), 'radar_oportunidades_filtradas.csv', 'text/csv')

    with tabs[2]:
        st.subheader('Compradores por número de oportunidades')
        tabla = clas['Organismo comprador'].value_counts().rename_axis('Comprador').reset_index(name='Oportunidades')
        st.dataframe(tabla, hide_index=True, use_container_width=True)

    with tabs[3]:
        st.subheader('Ofertas registradas')
        if of_f.empty:
            st.info('No hay ofertas asociadas a las compras visibles con los filtros actuales.')
        else:
            x = of_f.copy()
            if 'Monto total oferta' in x.columns:
                x['Monto total oferta'] = pd.to_numeric(x['Monto total oferta'], errors='coerce')
            columnas = ['Codigo Compra Agil', 'Proveedor', 'Proveedor seleccionado', 'Monto total oferta', 'Moneda', 'Fecha cotizacion']
            st.dataframe(x[[c for c in columnas if c in x.columns]], hide_index=True, use_container_width=True)
            st.caption('Proveedor seleccionado no equivale a orden de compra emitida ni a pago confirmado.')
        st.subheader('Seguimiento de adjudicaciones / selección')
        if adj_f.empty:
            st.info('No hay registros de seguimiento para las compras visibles.')
        else:
            st.dataframe(adj_f, use_container_width=True, hide_index=True)

    with tabs[4]:
        st.subheader('Capacitación online asincrónica')
        asincronicas = clas[clas['Modalidad'].str.contains('asincr', case=False, na=False)]
        st.metric('Oportunidades con modalidad asincrónica registrada', asincronicas['Codigo'].nunique())
        st.dataframe(asincronicas, use_container_width=True, hide_index=True)
        st.caption('La modalidad proviene de la clasificación del Radar; verificar evidencia y adjuntos antes de cotizar.')



@st.fragment(run_every="60s")
def mostrar_radar(seccion):
    if st.button("Actualizar vista"):
        cargar_radar_privado.clear()
    try:
        abiertas, futuras, pac = cargar_radar_privado()
        if seccion == "Abiertas ahora":
            mostrar_abiertas(abiertas)
        elif seccion == "Online asincrónico":
            mostrar_abiertas(abiertas, asincronicas=True)
        elif seccion == "Próximas oportunidades":
            mostrar_futuras(futuras)
        else:
            mostrar_pac(pac)
    except (KeyError, FileNotFoundError):
        st.info("La conexión privada de Google Sheets está pendiente de configurar.")
    except Exception:
        st.warning("No fue posible leer el Radar privado. Revisa la cuenta de servicio y el permiso de lectura.")


st.title("Radar Compra Ágil Salud")
st.caption("Inteligencia comercial de capacitación sanitaria")
seccion = st.sidebar.radio(
    "Navegación",
    ["Abiertas ahora", "Online asincrónico", "Próximas oportunidades", "Plan Anual de Compras", "Base inicial"],
)
if seccion == "Base inicial":
    mostrar_base_inicial()
else:
    mostrar_radar(seccion)
