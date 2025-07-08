import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime

# =================================================================================
# CONFIGURAÇÃO E CARREGAMENTO DE DADOS
# =================================================================================
st.set_page_config(page_title="Plataforma de Análise", layout="wide")
st.title("Plataforma Integrada de Análise de Ativos")

# --- URLs DO GOOGLE SHEETS ---
URL_EMPRESAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=0&single=true&output=csv"
URL_DEMONSTRATIVOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=1001090064&single=true&output=csv" # <- ATUALIZAR
URL_BONDS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=1081884812&single=true&output=csv"
# -----------------------------

# Funções de carregamento de dados (sem alterações)
@st.cache_data(ttl=600)
def carregar_dados(url):
    df = pd.read_csv(url)
    return df

@st.cache_data(ttl=3600)
def get_market_data(ticker):
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return None

# Carrega todos os dados
df_empresas = carregar_dados(URL_EMPRESAS)
df_demonstrativos = carregar_dados(URL_DEMONSTRATIVOS)
df_bonds = carregar_dados(URL_BONDS)

# =================================================================================
# BARRA LATERAL
# =================================================================================
st.sidebar.header("Seleção de Ativo")
# Unifica a seleção, usando o Ticker como chave principal
dict_empresas = pd.Series(df_empresas.Nome_Empresa.values, index=df_empresas.Ticker_Acao).to_dict()
ticker_selecionado = st.sidebar.selectbox("Selecione a Empresa:", options=list(dict_empresas.keys()), format_func=lambda x: f"{x} - {dict_empresas[x]}")

# =================================================================================
# LÓGICA PRINCIPAL
# =================================================================================
if ticker_selecionado:
    # Filtra dados da empresa selecionada
    info_empresa = df_empresas[df_empresas["Ticker_Acao"] == ticker_selecionado].iloc[0]
    demonstrativos_filtrados = df_demonstrativos[df_demonstrativos["Ticker"] == ticker_selecionado].sort_values(by="Ano", ascending=False)
    
    st.header(f"{info_empresa['Nome_Empresa']} ({info_empresa['Ticker_Acao']})")
    st.caption(f"Setor: {info_empresa['Setor']} | País: {info_empresa['País']}")
    
    # Busca dados de mercado
    market_data = get_market_data(ticker_selecionado)
    market_cap = market_data.get('marketCap') if market_data else None

    # Pega os dados financeiros mais recentes
    ultimo_ano_df = demonstrativos_filtrados.iloc[0]

    # Cria as abas da aplicação
    tab1, tab2, tab3 = st.tabs(["📊 Resumo e Múltiplos", "📈 Análise Financeira", "债券 Análise de Dívida"])

    # --- ABA 1: RESUMO E MÚLTIPLOS ---
    with tab1:
        st.subheader("Valuation e Métricas de Mercado")
        if market_cap:
            # Cálculos dos múltiplos
            lucro_liquido = ultimo_ano_df['Lucro_Liquido']
            patrimonio_liquido = ultimo_ano_df['Patrimonio_Liquido']
            ebit = ultimo_ano_df['EBIT']
            
            p_l = (market_cap / lucro_liquido) if lucro_liquido > 0 else 0
            p_vp = (market_cap / patrimonio_liquido) if patrimonio_liquido > 0 else 0
            ev_ebit = "N/A" # EV/EBIT é mais complexo, deixamos para depois
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Market Cap", f"R$ {(market_cap / 1_000_000_000):.2f} bi")
            col2.metric("P/L", f"{p_l:.2f}x" if p_l > 0 else "N/A")
            col3.metric("P/VP", f"{p_vp:.2f}x" if p_vp > 0 else "N/A")
        else:
            st.warning("Dados de mercado não disponíveis.")

    # --- ABA 2: ANÁLISE FINANCEIRA ---
    with tab2:
        st.subheader("Desempenho Financeiro Histórico")
        fig = px.bar(demonstrativos_filtrados, x="Ano", y=["Receita_Liquida", "EBIT", "Lucro_Liquido"], barmode='group', title="Performance Anual (em Milhões)")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Ratios de Rentabilidade e Eficiência")
        # Cálculos de Ratios
        roe = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Patrimonio_Liquido']) if ultimo_ano_df['Patrimonio_Liquido'] > 0 else 0
        margem_liquida = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Receita_Liquida']) if ultimo_ano_df['Receita_Liquida'] > 0 else 0
        margem_ebit = (ultimo_ano_df['EBIT'] / ultimo_ano_df['Receita_Liquida']) if ultimo_ano_df['Receita_Liquida'] > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("ROE (Return on Equity)", f"{roe:.2%}")
        col2.metric("Margem Líquida", f"{margem_liquida:.2%}")
        col3.metric("Margem EBIT", f"{margem_ebit:.2%}")

    # --- ABA 3: ANÁLISE DE DÍVIDA ---
    with tab3:
        st.subheader("Estrutura de Capital e Títulos de Dívida")
        # A lógica de Alavancagem e YTM que já construímos pode ser inserida aqui
        st.info("Seção de análise de dívida em desenvolvimento.")

else:
    st.info("Selecione uma empresa na barra lateral para começar a análise.")
