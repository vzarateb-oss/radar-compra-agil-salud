import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title='Radar Compra Ágil Salud',page_icon='🏥',layout='wide')
D=Path(__file__).parent
@st.cache_data
def cargar(nombre):
    p=D/f'{nombre}.csv'
    return pd.read_csv(p,dtype=str,keep_default_na=False,encoding='utf-8-sig') if p.exists() else pd.DataFrame()

clas=cargar('clasificacion'); adj=cargar('adjudicaciones'); ofertas=cargar('ofertas'); opp=cargar('oportunidades')
st.title('🏥 Radar Compra Ágil Salud')
st.caption('Mercado Público de Chile · Base inicial 2026 · Próxima fase: actualización automática por API')
if clas.empty:
    st.warning('No se encontró la base de clasificación sanitaria.');st.stop()

# La clasificación contiene también filas excluidas; el panel principal solo muestra A, B y C.
clas=clas[clas['Pertinencia sanitaria'].str.match(r'^[ABC]\s*-',case=False,na=False)].copy()
if clas.empty:
    st.warning('No hay registros sanitarios A/B/C en esta exportación.');st.stop()

st.sidebar.header('Filtros')
def filtro(df,col,etiqueta):
    if col not in df:return df
    opts=sorted(x for x in df[col].unique() if x)
    chosen=st.sidebar.multiselect(etiqueta,opts,default=opts)
    return df[df[col].isin(chosen)]
clas=filtro(clas,'Pertinencia sanitaria','Pertinencia')
clas=filtro(clas,'Modalidad','Modalidad')
clas=filtro(clas,'Area tematica','Área temática')
q=st.sidebar.text_input('Buscar compra, curso u organismo')
if q:
    cols=[x for x in ['Codigo','Nombre oportunidad','Organismo comprador'] if x in clas]
    clas=clas[clas[cols].apply(lambda s:s.str.contains(q,case=False,regex=False,na=False)).any(axis=1)]

codes=set(clas['Codigo'])
adj_f=adj[adj['Codigo Compra Agil'].isin(codes)] if not adj.empty else adj
of_f=ofertas[ofertas['Codigo Compra Agil'].isin(codes)] if not ofertas.empty else ofertas

def clp(s):
    n=pd.to_numeric(s,errors='coerce').fillna(0)
    return float(n.sum())

tabs=st.tabs(['📊 Panorama','🔎 Oportunidades','🏛️ Compradores','🏆 Competidores','💻 Online asincrónico'])
with tabs[0]:
    a,b,c,d=st.columns(4)
    a.metric('Oportunidades sanitarias',len(clas))
    b.metric('Compradores',clas['Organismo comprador'].nunique())
    c.metric('Presupuestos CLP declarados',f"${clp(clas.loc[clas['Moneda'].str.upper().eq('CLP'),'Presupuesto']):,.0f}".replace(',','.'))
    d.metric('Ofertas registradas',len(of_f))
    st.caption('Presupuestos solo en CLP; no se convierten otras monedas ni se interpretan ofertas como adjudicaciones.')
    l,r=st.columns(2)
    with l:
        st.subheader('Áreas temáticas');st.bar_chart(clas['Area tematica'].value_counts())
    with r:
        st.subheader('Modalidades');st.bar_chart(clas['Modalidad'].value_counts())
    st.subheader('Clasificación sanitaria');st.dataframe(clas['Pertinencia sanitaria'].value_counts().rename_axis('Clasificación').reset_index(name='Compras'),hide_index=True)
with tabs[1]:
    st.subheader('Oportunidades sanitarias A, B y C')
    st.caption('La categoría C requiere revisión; no se presenta como capacitación clínica confirmada.')
    st.dataframe(clas,use_container_width=True,hide_index=True)
    st.download_button('Descargar oportunidades filtradas',clas.to_csv(index=False).encode('utf-8-sig'),'radar_oportunidades_filtradas.csv','text/csv')
with tabs[2]:
    st.subheader('Compradores por número de oportunidades')
    st.dataframe(clas['Organismo comprador'].value_counts().rename_axis('Comprador').reset_index(name='Oportunidades'),hide_index=True,use_container_width=True)
with tabs[3]:
    st.subheader('Ofertas registradas')
    if of_f.empty:st.info('No hay ofertas asociadas a las compras visibles con los filtros actuales.')
    else:
        x=of_f.copy()
        x['Monto total oferta']=pd.to_numeric(x['Monto total oferta'],errors='coerce')
        cols=['Codigo Compra Agil','Proveedor','Proveedor seleccionado','Monto total oferta','Moneda','Fecha cotizacion']
        st.dataframe(x[[c for c in cols if c in x]],hide_index=True,use_container_width=True)
        st.caption('Proveedor seleccionado no equivale a orden de compra emitida ni a pago confirmado.')
    st.subheader('Seguimiento de adjudicaciones / selección')
    if adj_f.empty:st.info('No hay registros de seguimiento para las compras visibles.')
    else:st.dataframe(adj_f,use_container_width=True,hide_index=True)
with tabs[4]:
    st.subheader('Capacitación online asincrónica')
    async_df=clas[clas['Modalidad'].str.contains('asincr',case=False,na=False)]
    st.metric('Oportunidades con modalidad asincrónica registrada',len(async_df))
    st.dataframe(async_df,use_container_width=True,hide_index=True)
    st.caption('La modalidad proviene de la clasificación del Radar; verificar evidencia y adjuntos antes de cotizar.')
