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
URL_EMPRESAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pubhtml?gid=0&single=true"
URL_DEMONSTRATIVOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pubhtml?gid=842583931&single=true"
URL_BONDS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pubhtml?gid=1081884812&single=true"
# -----------------------------

# --- FUNÇÕES DE CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=600)
def carregar_dados_csv(url):
    df = pd.read_csv(url)
    return df

@st.cache_data(ttl=3600)
def get_market_data(ticker):
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return None

# --- NOVA FUNÇÃO PARA HISTÓRICO DE PREÇOS ---
@st.cache_data(ttl=3600)
def get_price_history(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.history(period="1y")
    except Exception:
        return pd.DataFrame() # Retorna DataFrame vazio em caso de erro

def calcular_ytm(preco_atual, valor_face, cupom_anual, anos_vencimento, pagamentos_anuais=1):
    # ... (função YTM sem alterações) ...
    if anos_vencimento <= 0: return 0.0
    taxa_cupom_periodo = cupom_anual / pagamentos_anuais
    num_periodos = anos_vencimento * pagamentos_anuais
    ytm_estimado = cupom_anual
    for _ in range(100):
        preco_estimado = 0
        ytm_periodo = ytm_estimado / pagamentos_anuais
        if ytm_periodo <= -1: return -1.0
        for i in range(1, int(num_periodos) + 1):
            preco_estimado += (taxa_cupom_periodo * valor_face) / ((1 + ytm_periodo) ** i)
        preco_estimado += valor_face / ((1 + ytm_periodo) ** num_periodos)
        if abs(preco_estimado - preco_atual) < 0.0001: return ytm_estimado
        if preco_estimado > preco_atual: ytm_estimado += 0.0001
        else: ytm_estimado -= 0.0001
    return ytm_estimado

# Carrega todos os dados
df_empresas = carregar_dados_csv(URL_EMPRESAS)
df_demonstrativos = carregar_dados_csv(URL_DEMONSTRATIVOS)
df_bonds = carregar_dados_csv(URL_BONDS)

# =================================================================================
# BARRA LATERAL
# =================================================================================
st.sidebar.header("Seleção de Ativo")
dict_empresas = pd.Series(df_empresas.Nome_Empresa.values, index=df_empresas.Ticker_Acao).to_dict()
ticker_selecionado = st.sidebar.selectbox("Selecione a Empresa:", options=list(dict_empresas.keys()), format_func=lambda x: f"{x} - {dict_empresas.get(x, 'N/A')}")

# =================================================================================
# LÓGICA PRINCIPAL
# =================================================================================
if ticker_selecionado:
    info_empresa = df_empresas[df_empresas["Ticker_Acao"] == ticker_selecionado].iloc[0]
    demonstrativos_filtrados = df_demonstrativos[df_demonstrativos["Ticker"] == ticker_selecionado].sort_values(by="Ano", ascending=False)
    
    st.header(f"{info_empresa['Nome_Empresa']} ({info_empresa['Ticker_Acao']})")
    st.caption(f"Setor: {info_empresa['Setor']} | País: {info_empresa['Pais']}")
    
    market_data = get_market_data(ticker_selecionado)
    market_cap = market_data.get('marketCap') if market_data else None

    ultimo_ano_df = demonstrativos_filtrados.iloc[0] if not demonstrativos_filtrados.empty else None

    # --- DEFINIÇÃO DAS ABAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumo e Múltiplos", "📈 Análise Financeira", "债券 Análise de Dívida", "👥 Comparáveis de Mercado"])

    # --- ABA 1: RESUMO E MÚLTIPLOS ---
    with tab1:
        st.subheader("Métricas de Mercado e Preço")
        if market_cap and ultimo_ano_df is not None:
            lucro_liquido = ultimo_ano_df.get('Lucro_Liquido', 0)
            patrimonio_liquido = ultimo_ano_df.get('Patrimonio_Liquido', 0)
            
            p_l = (market_cap / lucro_liquido) if lucro_liquido > 0 else 0
            p_vp = (market_cap / patrimonio_liquido) if patrimonio_liquido > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Market Cap", f"R$ {(market_cap / 1_000_000_000):.2f} bi")
            col2.metric("P/L", f"{p_l:.2f}x" if p_l > 0 else "N/A")
            col3.metric("P/VP", f"{p_vp:.2f}x" if p_vp > 0 else "N/A")
        else:
            st.warning("Dados de mercado ou financeiros não disponíveis para calcular múltiplos.")

        # NOVO GRÁFICO DE PREÇOS
        st.subheader("Histórico de Preços (Último Ano)")
        price_history = get_price_history(ticker_selecionado)
        if not price_history.empty:
            fig_preco = px.line(price_history, x=price_history.index, y="Close", title="Preço de Fechamento")
            st.plotly_chart(fig_preco, use_container_width=True)

    # --- ABA 2: ANÁLISE FINANCEIRA ---
    with tab2:
        # Conteúdo da Aba 2 (sem alterações, mas com verificação de dados)
        if ultimo_ano_df is not None:
             st.subheader("Desempenho Financeiro Histórico")
             # ... (código dos gráficos e ratios)
        else:
            st.warning("Não há dados financeiros para exibir.")


    # --- ABA 3: ANÁLISE DE DÍVIDA ---
    with tab3:
         # Conteúdo da Aba 3 (sem alterações, mas com verificação de dados)
        if ultimo_ano_df is not None:
            st.subheader("Perfil da Dívida e Métricas de Crédito")
            # ... (código da análise de dívida)
        else:
            st.warning("Não há dados financeiros para analisar a dívida.")

    # --- NOVA ABA 4: COMPARÁVEIS DE MERCADO ---
    with tab4:
        st.subheader(f"Análise de Comparáveis do Setor: {info_empresa['Setor']}")
        
        # 1. Encontrar os pares (peers)
        peers = df_empresas[df_empresas['Setor'] == info_empresa['Setor']]
        
        # 2. Coletar e calcular dados para os pares
        comparables_data = []
        for index, peer in peers.iterrows():
            peer_ticker = peer['Ticker_Acao']
            peer_market_data = get_market_data(peer_ticker)
            
            if not peer_market_data or 'marketCap' not in peer_market_data:
                continue

            peer_financials = df_demonstrativos[df_demonstrativos['Ticker'] == peer_ticker].sort_values(by="Ano", ascending=False)
            if peer_financials.empty:
                continue

            latest_financials = peer_financials.iloc[0]
            lucro_liquido = latest_financials.get('Lucro_Liquido', 0)
            patrimonio_liquido = latest_financials.get('Patrimonio_Liquido', 0)
            
            p_l = (peer_market_data['marketCap'] / lucro_liquido) if lucro_liquido > 0 else 0
            p_vp = (peer_market_data['marketCap'] / patrimonio_liquido) if patrimonio_liquido > 0 else 0
            
            comparables_data.append({
                'Empresa': peer['Nome_Empresa'],
                'Ticker': peer_ticker,
                'P/L': p_l,
                'P/VP': p_vp
            })

        if comparables_data:
            df_comparables = pd.DataFrame(comparables_data).round(2)
            
            # 3. Exibir a tabela de comparáveis
            st.markdown("##### Tabela de Múltiplos do Setor")
            st.dataframe(df_comparables.set_index('Ticker'), use_container_width=True)

            # 4. Exibir gráficos comparativos
            st.markdown("##### Gráficos Comparativos")
            
            # Gráfico P/L
            df_pl = df_comparables[df_comparables['P/L'] > 0] # Filtra P/L negativo/zero
            fig_pl = px.bar(df_pl, x='Ticker', y='P/L', title='Comparativo de P/L', color='Empresa')
            
            # Gráfico P/VP
            df_pvp = df_comparables[df_comparables['P/VP'] > 0] # Filtra P/VP negativo/zero
            fig_pvp = px.bar(df_pvp, x='Ticker', y='P/VP', title='Comparativo de P/VP', color='Empresa')

            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(fig_pl, use_container_width=True)
            with col2:
                st.plotly_chart(fig_pvp, use_container_width=True)
        else:
            st.warning("Não foi possível encontrar dados para os comparáveis do setor.")

else:
    st.info("Selecione uma empresa na barra lateral para começar a análise.")
