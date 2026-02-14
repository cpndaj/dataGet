import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="CPN Dante Jimenez - DataInfo", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .cuadro-unico {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        text-align: center;
        margin-bottom: 20px;
    }
    .titulo-cuadro { font-size: 0.9rem; color: #64748b; text-transform: uppercase; font-weight: bold; margin-bottom: 10px; }
    .seccion-venta { margin-bottom: 15px; }
    .label-venta { font-size: 0.8rem; color: #2563eb; font-weight: bold; }
    .val-venta { font-size: 2.2rem; font-weight: 800; color: #1e293b; line-height: 1; }
    .seccion-compra { background-color: #f1f5f9; padding: 8px; border-radius: 8px; margin-bottom: 8px; }
    .label-compra { font-size: 0.75rem; color: #475569; }
    .val-compra { font-size: 1.2rem; font-weight: 600; color: #334155; }
    .seccion-promedio { padding: 5px; }
    .label-promedio { font-size: 0.75rem; color: #94a3b8; }
    .val-promedio { font-size: 1.1rem; font-weight: 500; color: #64748b; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

def fmt_ar(valor):
    try:
        num = float(valor)
        return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

# --- 2. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def cargar_datos_completos():
    data = {
        "divisas": pd.DataFrame(),
        "inflacion": pd.DataFrame(),
        "tasas": pd.DataFrame([{"Banco": "Promedio Sistema", "TNA": 35.0}])
    }
    try:
        r = requests.get("https://api.argentinadatos.com/v1/cotizaciones/dolares", timeout=10)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            df['fecha'] = pd.to_datetime(df['fecha'])
            df_v = df.pivot_table(index='fecha', columns='casa', values='venta', aggfunc='last')
            df_c = df.pivot_table(index='fecha', columns='casa', values='compra', aggfunc='last')
            df_v.columns = [f"{c.lower()}_venta" for c in df_v.columns]
            df_c.columns = [f"{c.lower()}_compra" for c in df_c.columns]
            data["divisas"] = pd.concat([df_v, df_c], axis=1).sort_index(ascending=False).reset_index()
        
        for m in ['eur', 'brl']:
            re = requests.get(f"https://api.argentinadatos.com/v1/cotizaciones/monedas/{m}", timeout=10)
            if re.status_code == 200:
                data[f"moneda_{m}"] = pd.DataFrame(re.json()).sort_values('fecha', ascending=False).head(1)

        r_i = requests.get("https://api.argentinadatos.com/v1/finanzas/indices/inflacion", timeout=10)
        if r_i.status_code == 200:
            data["inflacion"] = pd.DataFrame(r_i.json())
        
        r_t = requests.get("https://api.argentinadatos.com/v1/finanzas/tasas/plazoFijo", timeout=10)
        if r_t.status_code == 200:
            df_t = pd.DataFrame(r_t.json())
            if not df_t.empty:
                df_t = df_t.sort_values('fecha').drop_duplicates('entidad', keep='last')
                df_t = df_t[['entidad', 'tasa']].rename(columns={'entidad': 'Banco', 'tasa': 'TNA'})
                data["tasas"] = df_t
    except: pass
    return data

def safe_get(df, col):
    if df is not None and not df.empty and col in df.columns:
        val = df[col].dropna()
        if not val.empty: return val.iloc[0]
    return 0.0

datos = cargar_datos_completos()
df_d, df_i, df_t = datos["divisas"], datos["inflacion"], datos["tasas"]

# --- 3. NAVEGACIÓN ---
with st.sidebar:
    st.title("💎 Estudio Jimenez")
    menu = st.radio("Herramientas", 
        ["🏠 Inicio", "📈 Mercado Cambiario", "💳 Dólar Tarjeta", "🔄 Interés Compuesto", "🧮 Comparador PF vs Inflación"])

# --- HOJA: INICIO ---
if menu == "🏠 Inicio":
    st.title("🚀 Indicadores Económicos")

    def render_tarjeta_vertical(titulo, v, c):
        p = (v + c) / 2 if (v + c) > 0 else 0.0
        st.markdown(f"""
            <div class="cuadro-unico">
                <div class="titulo-cuadro">{titulo}</div>
                <div class="seccion-venta">
                    <div class="label-venta">VALOR DE VENTA</div>
                    <div class="val-venta">${fmt_ar(v)}</div>
                </div>
                <div class="seccion-compra">
                    <div class="label-compra">Valor de Compra</div>
                    <div class="val-compra">${fmt_ar(c)}</div>
                </div>
                <div class="seccion-promedio">
                    <div class="label-promedio">Promedio</div>
                    <div class="val-promedio">${fmt_ar(p)}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Divisas
    st.subheader("💵 Cotizaciones Dólar")
    col1, col2, col3 = st.columns(3)
    with col1: render_tarjeta_vertical("Dólar Oficial", safe_get(df_d, 'oficial_venta'), safe_get(df_d, 'oficial_compra'))
    with col2: render_tarjeta_vertical("Dólar Blue", safe_get(df_d, 'blue_venta'), safe_get(df_d, 'blue_compra'))
    with col3: render_tarjeta_vertical("Dólar MEP", safe_get(df_d, 'mep_venta'), safe_get(df_d, 'mep_compra'))

    st.subheader("🌍 Otras Divisas")
    col_e, col_r, col_x = st.columns(3)
    with col_e:
        df_eur = datos.get("moneda_eur", pd.DataFrame())
        render_tarjeta_vertical("Euro", safe_get(df_eur, 'venta'), safe_get(df_eur, 'compra'))
    with col_r:
        df_brl = datos.get("moneda_brl", pd.DataFrame())
        render_tarjeta_vertical("Real", safe_get(df_brl, 'venta'), safe_get(df_brl, 'compra'))

    # Inflación Indicadores
    st.markdown("---")
    st.subheader("📈 Resumen de Inflación")
    if not df_i.empty:
        df_i['fecha'] = pd.to_datetime(df_i['fecha'])
        df_i = df_i.sort_values('fecha')
        ult = df_i.iloc[-1]
        a_act = ult['fecha'].year
        
        def calc_acumulado(año, mes_tope=12):
            mask = (df_i['fecha'].dt.year == año) & (df_i['fecha'].dt.month <= mes_tope)
            if not df_i[mask].empty:
                return ((df_i[mask]['valor']/100 + 1).prod() - 1) * 100
            return 0.0

        acum_2026 = calc_acumulado(2026, ult['fecha'].month)
        acum_2025 = calc_acumulado(2025)
        acum_2024 = calc_acumulado(2024)

        c_inf1, c_inf2 = st.columns(2)
        with c_inf1:
            st.markdown(f'<div class="cuadro-unico"><div class="titulo-cuadro">Mensual</div><div class="val-venta">{fmt_ar(ult["valor"])}%</div><div class="label-compra">Mes Actual</div></div>', unsafe_allow_html=True)
        with c_inf2:
            st.markdown(f'<div class="cuadro-unico"><div class="titulo-cuadro">Acumulado {a_act}</div><div class="val-venta">{fmt_ar(acum_2026)}%</div><div class="label-compra">Al cierre del último mes</div></div>', unsafe_allow_html=True)
        
        c_inf3, c_inf4 = st.columns(2)
        with c_inf3:
            st.markdown(f'<div class="cuadro-unico"><div class="titulo-cuadro">Inflación Anual 2025</div><div class="val-venta">{fmt_ar(acum_2025)}%</div><div class="label-compra">Enero - Diciembre</div></div>', unsafe_allow_html=True)
        with c_inf4:
            st.markdown(f'<div class="cuadro-unico"><div class="titulo-cuadro">Inflación Anual 2024</div><div class="val-venta">{fmt_ar(acum_2024)}%</div><div class="label-compra">Enero - Diciembre</div></div>', unsafe_allow_html=True)

    # --- SECCIÓN: GRÁFICOS ---
    st.markdown("---")
    st.subheader("📊 Gráficos de Análisis")

    # 1. Brecha Cambiaria
    if not df_d.empty and 'blue_venta' in df_d.columns and 'oficial_venta' in df_d.columns:
        df_brecha = df_d.copy().sort_values('fecha')
        df_brecha['brecha'] = ((df_brecha['blue_venta'] / df_brecha['oficial_venta']) - 1) * 100
        fig_b = go.Figure(go.Scatter(x=df_brecha['fecha'], y=df_brecha['brecha'], fill='tozeroy', line_color='#ef4444', name="Brecha %"))
        fig_b.update_layout(title="Evolución de la Brecha Cambiaria (%)", template="plotly_white", height=300)
        fig_b.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        st.plotly_chart(fig_b, use_container_width=True)

    # 2. Inflación últimos 12 meses (Ajustado con Formato Mes-Año y Marcado de todos los puntos)
    if not df_i.empty:
        df_12m = df_i.tail(12).copy()
        
        fig_12 = go.Figure(go.Scatter(
            x=df_12m['fecha'], 
            y=df_12m['valor'], 
            mode='lines+markers+text', # Marcadores y líneas
            text=[f"{fmt_ar(v)}%" for v in df_12m['valor']], # Etiquetas sobre los puntos
            textposition="top center",
            line=dict(color='#2563eb', width=4),
            marker=dict(size=10, symbol='circle')
        ))
        
        fig_12.update_layout(
            title="Inflación Mensual: Últimos 12 Meses",
            template="plotly_white",
            height=400,
            margin=dict(t=50, b=50)
        )
        
        # Configuración del Eje X: Formato Mar-25 y marcas para cada mes
        fig_12.update_xaxes(
            dtick="M1", # Marca cada mes
            tickformat="%b-%y", # Formato: Tres letras mes - Año 2 dígitos
            ticklabelmode="period",
            showgrid=True, 
            gridwidth=1, 
            gridcolor='LightGray',
            tickangle=-45 # Inclinado para mejor lectura
        )
        fig_12.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        
        st.plotly_chart(fig_12, use_container_width=True)

    # 3. Comparativa de años (2026, 2025, 2024)
    if not df_i.empty:
        df_i['mes'] = df_i['fecha'].dt.month
        df_i['año'] = df_i['fecha'].dt.year
        fig_comp = go.Figure()
        colores = {2026: '#2563eb', 2025: '#10b981', 2024: '#f59e0b'}
        for año in [2026, 2025, 2024]:
            df_year = df_i[df_i['año'] == año].sort_values('mes')
            if not df_year.empty:
                fig_comp.add_trace(go.Scatter(x=df_year['mes'], y=df_year['valor'], name=str(año), line=dict(color=colores.get(año), width=3), mode='lines+markers'))
        
        fig_comp.update_layout(
            title="Comparativa Inflación por Año (Enero-Diciembre)",
            xaxis=dict(tickmode='array', tickvals=list(range(1,13)), ticktext=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'], showgrid=True, gridwidth=1, gridcolor='LightGray'),
            template="plotly_white", height=400, hovermode="x unified"
        )
        fig_comp.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        st.plotly_chart(fig_comp, use_container_width=True)

# --- LAS OTRAS SECCIONES ---
elif menu == "📈 Mercado Cambiario":
    st.title("📊 Histórico")
    if not df_d.empty:
        fig = go.Figure()
        for c in ['blue_venta', 'mep_venta', 'oficial_venta']:
            if c in df_d.columns: fig.add_trace(go.Scatter(x=df_d['fecha'], y=df_d[c], name=c.replace('_venta','').upper()))
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        st.plotly_chart(fig, use_container_width=True)

elif menu == "💳 Dólar Tarjeta":
    st.title("💳 Calculador")
    u = st.number_input("Monto USD", value=100.0)
    of = safe_get(df_d, 'oficial_venta') if safe_get(df_d, 'oficial_venta') > 0 else 980.0
    st.metric("Total Pesos", f"${fmt_ar(u * of * 1.6)}")

elif menu == "🔄 Interés Compuesto":
    st.title("🔄 Interés Compuesto")
    cap = st.number_input("Capital", value=1000000)
    tna = st.number_input("TNA %", value=35.0)
    t = st.slider("Meses", 1, 60, 12)
    res = [float(cap)]
    for i in range(1, t+1): res.append(res[-1] * (1 + (tna/100/12)))
    st.metric("Final", f"${fmt_ar(res[-1])}")
    fig = go.Figure(go.Scatter(y=res, mode='lines+markers'))
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    st.plotly_chart(fig, use_container_width=True)

elif menu == "🧮 Comparador PF vs Inflación":
    st.title("🧮 Comparador")
    m = st.number_input("Monto", value=100000)
    b = st.selectbox("Banco", df_t['Banco'].tolist() if not df_t.empty else ["Promedio"])
    tna_p = df_t[df_t['Banco'] == b]['TNA'].values[0] if not df_t.empty else 35.0
    inf_e = st.number_input("Inflación mensual %", value=4.0)
    pf = m * (1 + (tna_p/100*30/365))
    inf_v = m * (1 + inf_e/100)
    st.metric("Resultado PF", f"${fmt_ar(pf)}", f"Dif: {fmt_ar(pf-inf_v)}")
    st.plotly_chart(go.Figure(go.Bar(x=['PF', 'Infla'], y=[pf, inf_v])), use_container_width=True)