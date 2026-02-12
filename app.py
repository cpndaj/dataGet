import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="CPN Dante Jimenez DataInfo", page_icon="📈", layout="wide")

# Función para formatear números al estilo AR (1.234,56)
def fmt_ar(valor):
    if pd.isna(valor) or valor == "-": return "-"
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(valor)

# --- 2. FUNCIONES DE DATOS ---

@st.cache_data(ttl=600)
def cargar_divisas():
    api_url = "https://api.argentinadatos.com/v1/cotizaciones/dolares/"
    monedas = {'Dólar Billete': 'oficial', 'Dólar Blue': 'blue', 'Dólar Divisa': 'mayorista'}
    dfs = []
    for nombre, path in monedas.items():
        try:
            r = requests.get(api_url + path, timeout=8)
            if r.status_code == 200:
                temp = pd.DataFrame(r.json())
                temp = temp.rename(columns={'compra': f'{nombre} Compra', 'venta': f'{nombre} Venta'})
                temp['fecha'] = pd.to_datetime(temp['fecha'])
                dfs.append(temp[['fecha', f'{nombre} Compra', f'{nombre} Venta']])
        except: continue
    
    if not dfs: return pd.DataFrame()
    df_f = dfs[0]
    for i in range(1, len(dfs)): df_f = pd.merge(df_f, dfs[i], on='fecha', how='outer')
    return df_f.sort_values('fecha', ascending=False).reset_index(drop=True)

@st.cache_data(ttl=86400)
def obtener_inflacion():
    url = "https://api.argentinadatos.com/v1/finanzas/indices/inflacion"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            df = pd.DataFrame(res.json())
            df['fecha'] = pd.to_datetime(df['fecha'])
            df = df.sort_values('fecha')
            df['indice'] = (1 + df['valor']/100).cumprod()
            return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def obtener_tasas_bcra():
    # Usamos la API de ArgentinaDatos que devuelve el formato que mencionas
    url = "https://api.argentinadatos.com/v1/finanzas/tasas/plazoFijo"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            df = pd.DataFrame(data)
            
            # Adaptación al formato JSON que enviaste:
            # entidad -> Banco
            # tnaClientes -> Tasa (%)
            if 'entidad' in df.columns and 'tnaClientes' in df.columns:
                # Nos quedamos con los datos más recientes si hay duplicados
                if 'fecha' in df.columns:
                    df = df.sort_values('fecha', ascending=False)
                df = df.drop_duplicates(subset=['entidad'])
                
                # Seleccionamos y renombramos
                df = df[['entidad', 'tnaClientes']]
                df.columns = ['Banco', 'Tasa (%)']
                
                # Convertimos 0.25 a 25.0 (porcentaje)
                df['Tasa (%)'] = df['Tasa (%)'].astype(float) * 100
                
                return df.sort_values('Tasa (%)', ascending=False)
    except Exception as e:
        print(f"Error: {e}")
    return pd.DataFrame()

# --- 3. NAVEGACIÓN ---
st.sidebar.title("AWINQA Consultant")
opcion = st.sidebar.radio("Ir a:", ["📊 Cotizaciones", "🏦 Tasas Plazo Fijo", "📈 Inflación INDEC"])


# --- LÓGICA DE PÁGINAS ---
if opcion == "📊 Cotizaciones":
    st.title("💼 Dolar - Cotización (Banco Nación)")
    df = cargar_divisas()
    if not df.empty:
        st.subheader(f"Cotizaciones del Día ({datetime.now().strftime('%d/%m/%Y')})")
        row = df.iloc[0]
        cols = st.columns(3)
        data = [("Dólar BNA", "Dólar Billete"), ("Dólar Blue", "Dólar Blue"), ("Dólar Divisa", "Dólar Divisa")]
        for i, (lab, k) in enumerate(data):
            v, c = row.get(f'{k} Venta'), row.get(f'{k} Compra')
            cols[i].metric(lab, f"${fmt_ar(v)}", f"Compra: ${fmt_ar(c)}", delta_color="off")
        
        st.divider()
        st.subheader("Evolución últimos 30 días")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['fecha'].head(30), y=df['Dólar Billete Venta'].head(30), name="Oficial", mode='lines+markers'))
        fig.add_trace(go.Scatter(x=df['fecha'].head(30), y=df['Dólar Blue Venta'].head(30), name="Blue", mode='lines+markers'))
        fig.update_layout(xaxis=dict(showgrid=True, gridcolor='LightGray'), yaxis=dict(showgrid=True, gridcolor='LightGray'), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

elif opcion == "📈 Inflación INDEC":
    st.title("📈  Inflación (Indec)")
    df_i = obtener_inflacion()
    if not df_i.empty:
        df_i['año'] = df_i['fecha'].dt.year
        df_i['mes'] = df_i['fecha'].dt.month
        meses_nom = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic'}
        
        inf_12m = ((df_i.tail(12)['valor']/100 + 1).prod() - 1) * 100
        inf_2024 = ((df_i[df_i['año'] == 2024]['valor']/100 + 1).prod() - 1) * 100
        inf_2025 = ((df_i[df_i['año'] == 2025]['valor']/100 + 1).prod() - 1) * 100
        anio_actual = datetime.now().year
        inf_actual = ((df_i[df_i['año'] == anio_actual]['valor']/100 + 1).prod() - 1) * 100

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Últimos 12 Meses", f"{fmt_ar(inf_12m)}%")
        m2.metric(f"Acumulado {anio_actual}", f"{fmt_ar(inf_actual)}%")
        m3.metric("Anual 2025", f"{fmt_ar(inf_2025)}%")
        m4.metric("Anual 2024", f"{fmt_ar(inf_2024)}%")

        st.divider()
        st.markdown("### Comparativa Interanual por Mes")
        fig_line = go.Figure()
        for anio in [2024, 2025, 2026]:
            df_anio = df_i[df_i['año'] == anio]
            if not df_anio.empty:
                fig_line.add_trace(go.Scatter(
                    x=[meses_nom[m] for m in df_anio['mes']], 
                    y=df_anio['valor'], name=str(anio), mode='lines+markers+text',
                    text=df_anio['valor'].apply(lambda x: f"{fmt_ar(x)}%"), textposition="top center"
                ))
        fig_line.update_layout(xaxis=dict(showgrid=True, gridcolor='LightGray'), yaxis=dict(showgrid=True, gridcolor='LightGray'), height=450)
        st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("### Historial últimos 12 meses")
        df_12 = df_i.tail(12).copy()
        df_12['label'] = df_12['fecha'].dt.strftime('%m/%y')
        fig_bar = go.Figure(go.Bar(x=df_12['label'], y=df_12['valor'], text=df_12['valor'].apply(lambda x: f"{fmt_ar(x)}%"), textposition='auto', marker_color='#1E88E5'))
        fig_bar.update_layout(xaxis=dict(showgrid=True, gridcolor='LightGray'), yaxis=dict(showgrid=True, gridcolor='LightGray'))
        st.plotly_chart(fig_bar, use_container_width=True)

        st.divider()
        st.subheader("🧮 Calculadora de Actualización por Inflación")
        c1, c2, c3 = st.columns(3)
        monto_input = c1.number_input("Monto a actualizar ($)", value=1000.0, step=100.0, key="monto_inf")
        meses_opciones = df_i['fecha'].dt.strftime('%m/%Y').tolist()[::-1]
        f_origen_sel = c2.selectbox("Mes Origen", meses_opciones, index=len(meses_opciones)-1, key="sel_orig")
        f_destino_sel = c3.selectbox("Mes Destino", meses_opciones, index=0, key="sel_dest")

        idx_origen = df_i[df_i['fecha'].dt.strftime('%m/%Y') == f_origen_sel]['indice'].values[0]
        idx_destino = df_i[df_i['fecha'].dt.strftime('%m/%Y') == f_destino_sel]['indice'].values[0]
        monto_final = monto_input * (idx_destino / idx_origen)
        porcentaje_variacion = ((idx_destino / idx_origen) - 1) * 100
        
        st.success(f"### Monto Actualizado: AR$ {fmt_ar(monto_final)}")
        st.info(f"Variación entre periodos: **{fmt_ar(porcentaje_variacion)}%**")   


elif opcion == "🏦 Tasas Plazo Fijo":
    st.title("🏦 Plazo Fijo")
    st.subheader("Tasas vigentes por Banco")
    df_t = obtener_tasas_bcra()
    if not df_t.empty:
        df_t_show = df_t.copy()
        df_t_show['Tasa (%)'] = df_t_show['Tasa (%)'].apply(fmt_ar)
        st.dataframe(df_t_show, use_container_width=True, hide_index=True)

        st.title("🧮 Calculador de Rendimiento")
        df_t = obtener_tasas_bcra()
        if not df_t.empty:
            inv = st.number_input("Inversión ($)", value=100000.0)
            banco = st.selectbox("Banco", df_t['Banco'])
            tasa = df_t[df_t['Banco'] == banco]['Tasa (%)'].values[0]
            gan = (inv * (tasa/100) * 30) / 365
            st.metric(f"Ganancia en {banco}", f"AR$ {fmt_ar(gan)}", f"TNA: {fmt_ar(tasa)}%")
    else:
        st.warning("No se pudieron cargar las tasas. Intente nuevamente en unos instantes.")


# elif opcion == "🧮 Calculador PF":
    # st.title("🧮 Calculador de Rendimiento")
    # df_t = obtener_tasas_bcra()
    # if not df_t.empty:
    #     inv = st.number_input("Inversión ($)", value=100000.0)
    #     banco = st.selectbox("Banco", df_t['Banco'])
    #     tasa = df_t[df_t['Banco'] == banco]['Tasa (%)'].values[0]
    #     gan = (inv * (tasa/100) * 30) / 365
    #     st.metric(f"Ganancia en {banco}", f"AR$ {fmt_ar(gan)}", f"TNA: {fmt_ar(tasa)}%")


# --- LOGO ---
st.sidebar.markdown("<br>" * 10, unsafe_allow_html=True)
try:
    l_l, l_c, l_r = st.sidebar.columns([1.5, 1, 1.5])
    l_c.image("daj_wb.png", use_container_width=True)
except:
    st.sidebar.caption("CPN Dante Jimenez DataInfo")