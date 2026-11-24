from html import escape
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
    horas, minutos = divmod(segundos // 60, 60)
    restante = f"{horas} h {minutos:02d} min" if horas else f"{minutos} min" if minutos else "Menos de 1 min"
    nivel = "🔴 Hasta 24 h" if segundos <= 86400 else "🟠 Hasta 72 h" if segundos <= 259200 else "🟢 Vigente"
    return nivel, restante



NIVELES_VIGENTES = ["🔴 Hasta 24 h", "🟠 Hasta 72 h", "🟢 Vigente"]


def mostrar_cierres(datos):
    cierres = datos[datos["Semáforo"].isin(NIVELES_VIGENTES)].copy()
    if cierres.empty:
        return
    fechas = cierres["_cierre"].dt.strftime("%d/%m")
    conteos = fechas.value_counts(sort=False).rename_axis("Día de cierre").rename("Compras")
    st.markdown("#### Cierres por día")
    st.bar_chart(conteos, color="#188779")


def resumen_futuro(datos, mostrar_temas=False):
    estimadas = datos[datos["Ventana estimada"].str.fullmatch(r"\d{4}-Q[1-4]")]
    if estimadas.empty:
        st.info("Estas señales históricas no tienen una ventana estimada con los filtros actuales.")
        return
    recurrentes = estimadas[estimadas["Prioridad"].str.startswith("1 ·")]
    foco = recurrentes if not recurrentes.empty else estimadas
    por_ventana = foco["Ventana estimada"].value_counts().sort_index()
    ventana = por_ventana.idxmax()
    temas = foco.loc[foco["Ventana estimada"].eq(ventana), "Tema"]
    temas = temas[temas.ne("")]
    foco_texto = "asincrónicas recurrentes" if not recurrentes.empty else "históricas con ventana estimada"
    st.write(
        f"{len(foco)} señales {foco_texto}. La mayor concentración está en {ventana}, "
        f"con {por_ventana.loc[ventana]} señales. "
        + (f"Temas a seguir en esa ventana: {', '.join(temas.value_counts().head(3).index)}. " if not temas.empty else "")
        + "Las ventanas se estiman a partir del histórico y pueden cambiar."
    )
    if mostrar_temas:
        izquierda, derecha = st.columns(2)
        with izquierda:
            st.markdown("#### Señales por trimestre")
            st.bar_chart(estimadas["Ventana estimada"].value_counts().sort_index().rename("Señales"), color="#188779")
        with derecha:
            st.markdown("#### Temas con más señales")
            cuentas = estimadas.loc[estimadas["Tema"].ne(""), "Tema"].value_counts().head(6)
            if not cuentas.empty:
                st.bar_chart(cuentas.rename("Señales"), color="#4a7791")


def mostrar_tarjeta(compra):
    nivel = compra["Semáforo"]
    color = {"🔴 Hasta 24 h": "#a62736", "🟠 Hasta 72 h": "#955900", "🟢 Vigente": "#176141"}.get(nivel, "#53676b")
    etiqueta_plazo = "Quedan " + compra["Tiempo restante"] if nivel in NIVELES_VIGENTES else nivel[2:].strip()
    if compra["Tiempo restante"] == "Menos de 1 min":
        etiqueta_plazo = compra["Tiempo restante"]

    def dato(campo):
        return escape(str(compra.get(campo) or "Sin dato"))
    fechas = "".join(
        f"<div><small>{etiqueta}</small><strong>{dato(campo)}</strong></div>"
        for etiqueta, campo in [("Publicación", "Publicación"), ("Cierre · hora de Chile", "Cierre"),
                                ("Presupuesto", "Presupuesto")]
    )
    with st.container(border=True):
        st.markdown(
            f'<article class="radar-card" style="--urgencia:{color}">'
            f'<span class="radar-badge">{escape(etiqueta_plazo)}</span>'
            f'<small>{dato("Código")} · {dato("Pertinencia")}</small>'
            f'<h3>{dato("Oportunidad")}</h3><p>{dato("Organismo")} · {dato("Modalidad")}</p>'
            f'<div class="radar-dates">{fechas}</div></article>', unsafe_allow_html=True
        )
        if re.fullmatch(r"\d+-\d+-COT\d{2}", compra["Código"]):
            st.link_button("Ver ficha en Mercado Público",
                           "https://buscador.mercadopublico.cl/ficha?code=" + compra["Código"])


def mostrar_abiertas(filas, asincronicas=False, inicio=False, futuras=None):
    st.subheader("Próximos cierres" if inicio else "Online asincrónico" if asincronicas else "Abiertas ahora")
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
    vigentes = datos["Semáforo"].isin(NIVELES_VIGENTES)
    captura_disponible = estado.startswith(("Última consulta completa", "Captura parcial"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Vigentes en la captura", int(vigentes.sum()) if captura_disponible else "—")
    c2.metric("Cierran en 24 h", int(datos["Semáforo"].eq("🔴 Hasta 24 h").sum()) if captura_disponible else "—")
    c3.metric("Por verificar", int(datos["Semáforo"].eq("⚪ Por verificar").sum()) if captura_disponible else "—")
    if inicio:
        solo_vigentes, consulta, seleccion = True, "", "Todas"
    else:
        with st.container(border=True):
            buscar, estado_filtro, modalidad = st.columns([2, 1, 1])
            consulta = buscar.text_input("Buscar", placeholder="Código, curso u organismo").strip()
            solo_vigentes = estado_filtro.toggle("Solo vigentes", value=True)
            seleccion = modalidad.selectbox("Modalidad", ["Todas", *sorted(set(datos["Modalidad"]) - {""})])
    if seleccion != "Todas":
        datos = datos[datos["Modalidad"].eq(seleccion)]
    if solo_vigentes:
        datos = datos[vigentes]
    if consulta:
        columnas = [c for c in ["Código", "Oportunidad", "Organismo"] if c in datos]
        filtro = datos[columnas].apply(lambda c: c.str.contains(consulta, case=False, regex=False)).any(axis=1)
        datos = datos[filtro]
    datos = datos.assign(_cierre=pd.to_datetime(datos["Cierre"].map(fecha_chile))).sort_values("_cierre")
    activas = datos[datos["Semáforo"].isin(NIVELES_VIGENTES)]
    with st.container(border=True):
        st.markdown("#### Qué mirar ahora")
        if not captura_disponible:
            st.write("Todavía no hay una captura confirmada para evaluar las compras abiertas.")
        elif activas.empty:
            st.write("No hay cierres vigentes verificados para los filtros y la captura que estás viendo.")
        else:
            primera = activas.iloc[0]
            urgentes = int(activas["Semáforo"].eq("🔴 Hasta 24 h").sum())
            asincronas = int(activas["Modalidad"].str.contains(r"\basincr", case=False, regex=True).sum())
            st.write(
                f"{len(activas)} compras vigentes en la vista, {urgentes} dentro de las próximas 24 h "
                f"y {asincronas} identificadas como asincrónicas. "
                f"El primer cierre es {primera['Código']} a las {primera['Cierre']} (hora de Chile). "
                f"Tiempo restante: {primera['Tiempo restante']}."
            )
        if inicio and futuras is not None:
            st.markdown("#### Qué preparar")
            resumen_futuro(tabla_radar(futuras))
    mostrar_cierres(datos)
    if datos.empty:
        st.info("La captura disponible no tiene compras que coincidan con estos filtros.")
        return
    if inicio:
        visibles = datos.head(3)
    else:
        st.caption(f"{len(datos)} resultados · ordenados por cierre")
        paginas = (len(datos) + 9) // 10
        pagina = st.selectbox("Página", range(1, paginas + 1)) if paginas > 1 else 1
        visibles = datos.iloc[(pagina - 1) * 10:pagina * 10]
    for compra in visibles.to_dict("records"):
        mostrar_tarjeta(compra)


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
    with st.container(border=True):
        st.markdown("#### Lectura de las señales seleccionadas")
        resumen_futuro(datos, mostrar_temas=True)
    with st.expander("Ver señales y evidencia", expanded=False):
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
        if seccion == "Inicio":
            mostrar_abiertas(abiertas, inicio=True, futuras=futuras)
        elif seccion == "Abiertas ahora":
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


st.markdown("""
<style>
.radar-hero{background:#103c3a;color:white;border-radius:16px;padding:22px 26px;margin-bottom:16px}
.radar-hero h1{color:white;margin:2px 0;font-size:clamp(1.6rem,4vw,2.25rem)}
.radar-hero p{color:#b8e4da;margin:0}
.radar-card{border-left:4px solid var(--urgencia);padding:3px 0 3px 14px}
.radar-card h3{font-size:1.13rem;padding:4px 0;margin:3px 0}
.radar-card p{margin:0 0 10px}
.radar-badge{display:inline-block;border-radius:999px;padding:4px 9px;background:var(--urgencia);color:white;font-weight:700;margin:0 10px 4px 0}
.radar-dates{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.radar-dates strong,.radar-dates small{display:block}
[data-testid="stMetric"]{border:1px solid #bdcfcc;border-radius:12px;padding:12px}
@media(max-width:740px){.radar-dates{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
<header class="radar-hero"><p>Inteligencia comercial de capacitación sanitaria</p><h1>Radar Compra Ágil Salud</h1></header>
""", unsafe_allow_html=True)
seccion = st.sidebar.radio(
    "Navegación",
    ["Inicio", "Abiertas ahora", "Online asincrónico", "Próximas oportunidades", "Plan Anual de Compras", "Base inicial"],
)
if seccion == "Base inicial":
    mostrar_base_inicial()
else:
    mostrar_radar(seccion)
