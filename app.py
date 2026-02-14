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
    # APIs para Dólares, Euro y Real
    urls = {
        'Dólar Oficial': "https://api.argentinadatos.com/v1/cotizaciones/dolares/oficial",
        'Dólar Blue': "https://api.argentinadatos.com/v1/cotizaciones/dolares/blue",
        'Euro': "https://api.argentinadatos.com/v1/cotizaciones/monedas/eur",
        'Real': "https://api.argentinadatos.com/v1/cotizaciones/monedas/brl"
    }
    dfs = []
    for nombre, url in urls.items():
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                temp = pd.DataFrame(r.json())
                temp = temp.rename(columns={'compra': f'{nombre} Compra', 'venta': f'{nombre} Venta'})
                temp['fecha'] = pd.to_datetime(temp['fecha'])
                dfs.append(temp[['fecha', f'{nombre} Compra', f'{nombre} Venta']])
        except: continue
    
    if not dfs: return pd.DataFrame()
    df_f = dfs[0]
    for i in range(1, len(dfs)): 
        df_f = pd.merge(df_f, dfs[i], on='fecha', how='outer')
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
    url = "https://api.argentinadatos.com/v1/finanzas/tasas/plazoFijo"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            df = pd.DataFrame(data)
            if 'entidad' in df.columns and 'tnaClientes' in df.columns:
                if 'fecha' in df.columns:
                    df = df.sort_values('fecha', ascending=False)
                df = df.drop_duplicates(subset=['entidad'])
                df = df[['entidad', 'tnaClientes']]
                df.columns = ['Banco', 'Tasa (%)']
                df['Tasa (%)'] = df['Tasa (%)'].astype(float) * 100
                return df.sort_values('Tasa (%)', ascending=False)
    except Exception as e:
        print(f"Error: {e}")
    return pd.DataFrame()

# --- 3. NAVEGACIÓN ---
st.sidebar.title(":green[DataInfo]", text_alignment="center") 

opcion = st.sidebar.radio(
    "Ir a:", 
    ["📊 Moneda", "📈 Inflación", "🏦 Plazo Fijo",],
)

# --- LÓGICA DE PÁGINAS ---
if opcion == "📊 Moneda":
    st.title("💼 Cotizaciones - Divisas")
    st.divider()
    df = cargar_divisas()
    if not df.empty:
        # A. VALORES EN TIEMPO REAL
        st.subheader(f"Cotizaciones del Día ({datetime.now().strftime('%d/%m/%Y')})")
        row_hoy = df.iloc[0]
        cols = st.columns(4)
        monedas_display = [("Dólar Oficial", "Dólar Oficial"), ("Dólar Blue", "Dólar Blue"), ("Euro", "Euro"), ("Real", "Real")]
        
        for i, (lab, k) in enumerate(monedas_display):
            v, c = row_hoy.get(f'{k} Venta'), row_hoy.get(f'{k} Compra')
            cols[i].metric(f"🟢 {lab}", f"${fmt_ar(v)}", f"Compra: ${fmt_ar(c)}", delta_color="off")
        
        st.divider()
        
        # B. CIERRE DÍA ANTERIOR
        if len(df) > 1:
            row_ayer = df.iloc[1]
            st.caption(f"Cierre Día Anterior: {row_ayer['fecha'].strftime('%d/%m/%Y')}")
            cols_ayer = st.columns(4)
            for i, (lab, k) in enumerate(monedas_display):
                v, c = row_ayer.get(f'{k} Venta'), row_ayer.get(f'{k} Compra')
                cols_ayer[i].metric(f"⚪ {lab}", f"${fmt_ar(v)}", f"Compra: ${fmt_ar(c)}", delta_color="off")
        
        st.divider()

        # C. GRÁFICOS
        st.subheader("Evolución últimos 30 días (Dólar)")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['fecha'].head(30), y=df['Dólar Oficial Venta'].head(30), name="Oficial", mode='lines+markers'))
        fig.add_trace(go.Scatter(x=df['fecha'].head(30), y=df['Dólar Blue Venta'].head(30), name="Blue", mode='lines+markers'))
        fig.update_layout(xaxis=dict(showgrid=True, gridcolor='LightGray'), yaxis=dict(showgrid=True, gridcolor='LightGray'), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # D. TABLA AL FINAL
        st.subheader("Histórico de Cotizaciones")
        df_tabla = df.copy()
        df_tabla['fecha'] = df_tabla['fecha'].dt.strftime('%d/%m/%Y')
        for col in df_tabla.columns:
            if col != 'fecha':
                df_tabla[col] = df_tabla[col].apply(fmt_ar)
        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

elif opcion == "📈 Inflación":
    st.title("📈  Inflación (INDEC)")
    st.divider()
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
        f_origen_sel = c2.selectbox("Mes Origen", meses_opciones, index=11, key="sel_orig")
        f_destino_sel = c3.selectbox("Mes Destino", meses_opciones, index=0, key="sel_dest")

        idx_origen = df_i[df_i['fecha'].dt.strftime('%m/%Y') == f_origen_sel]['indice'].values[0]
        idx_destino = df_i[df_i['fecha'].dt.strftime('%m/%Y') == f_destino_sel]['indice'].values[0]
        monto_final = monto_input * (idx_destino / idx_origen)
        porcentaje_variacion = ((idx_destino / idx_origen) - 1) * 100
        
        st.success(f"### Monto Actualizado: AR$ {fmt_ar(monto_final)}")
        st.info(f"Variación entre periodos: **{fmt_ar(porcentaje_variacion)}%**")   

elif opcion == "🏦 Plazo Fijo":
    st.title("🏦 Tasas Plazo Fijo (BCRA)")
    st.subheader("Tasas vigentes por Banco")
    st.divider()
    df_t = obtener_tasas_bcra()
    if not df_t.empty:
        df_t_show = df_t.copy()
        df_t_show['Tasa (%)'] = df_t_show['Tasa (%)'].apply(fmt_ar)
        st.dataframe(df_t_show, use_container_width=True, hide_index=True)

        st.title("🧮 Calculador de Rendimiento")
        inv = st.number_input("Inversión ($)", value=100000.0)
        banco = st.selectbox("Banco", df_t['Banco'])
        tasa = df_t[df_t['Banco'] == banco]['Tasa (%)'].values[0]
        gan = (inv * (tasa/100) * 30) / 365
        st.metric(f"Ganancia en {banco}", f"AR$ {fmt_ar(gan)}", f"TNA: {fmt_ar(tasa)}%")
    else:
        st.warning("No se pudieron cargar las tasas. Intente nuevamente en unos instantes.")

# --- LOGO ---
st.sidebar.markdown("<br>" * 11, unsafe_allow_html=True)
try:
    l_l, l_c, l_r = st.sidebar.columns([1.5, .7, 1.5])
    l_c.image("daj_wb.png", use_container_width=True)
    l_l1, l_c1, l_r1 = st.sidebar.columns([.5, 1.1, .5])
    l_c1.image("awinqa_wb.png", use_container_width=True)

    email_l, email_c, email_r = st.sidebar.columns([.4, 3, .4])
    email_c.text("cpn@dantejimenez.com.ar")
    mob_l, mob_c, mob_r = st.sidebar.columns([1, 2.5, 1])
    mob_c.text("+54 9 381 546 3785")
except:
    st.sidebar.caption("CPN Dante Jimenez DataInfo")