
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
