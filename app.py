import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime
import gspread

# =================================================================================
# CONFIGURAÇÃO E DEFINIÇÃO DE FUNÇÕES
# =================================================================================
st.set_page_config(page_title="Plataforma de Análise", layout="wide")
st.title("Plataforma Integrada de Análise de Ativos")

NOME_PLANILHA = "Plataforma_DB_Final"

# --- FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO DE DADOS ---

@st.cache_data(ttl=3600)
def carregar_dados_gsheets(worksheet_name):
    """Função para carregar dados de uma aba específica usando gspread."""
    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        spreadsheet = gc.open(NOME_PLANILHA)
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao carregar a aba '{worksheet_name}': {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_market_data(ticker):
    """Busca dados de mercado do yfinance."""
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return None

@st.cache_data(ttl=3600)
def get_price_history(ticker):
    """Busca histórico de preços do yfinance."""
    try:
        return yf.Ticker(ticker).history(period="1y")
    except Exception:
        return pd.DataFrame()

def calcular_ytm(preco_atual, valor_face, cupom_anual, anos_vencimento, pagamentos_anuais=1):
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

# =================================================================================
# CARREGAMENTO INICIAL DOS DADOS
# =================================================================================
df_empresas_master = carregar_dados_gsheets("empresas_master")
df_perfis = carregar_dados_gsheets("perfis_empresas")
df_metricas_anuais = carregar_dados_gsheets("metricas_anuais")
df_bonds = carregar_dados_gsheets("dados_bonds")

# =================================================================================
# BARRA LATERAL
# =================================================================================
st.sidebar.header("Seleção de Ativo")

if not df_empresas_master.empty:
    dict_empresas = pd.Series(df_empresas_master.Nome_Empresa.values, index=df_empresas_master.Ticker).to_dict()
    ticker_selecionado = st.sidebar.selectbox("Selecione a Empresa:", options=list(dict_empresas.keys()), format_func=lambda x: f"{x} - {dict_empresas.get(x, 'N/A')}")
else:
    st.sidebar.error("A lista de empresas master não pôde ser carregada.")
    ticker_selecionado = None
    st.stop()

# =================================================================================
# LÓGICA PRINCIPAL DA APLICAÇÃO
# =================================================================================
if ticker_selecionado:
    # --- FILTRAGEM DE DADOS ---
    info_empresa = df_empresas_master[df_empresas_master["Ticker"] == ticker_selecionado].iloc[0]
    perfil_empresa = df_perfis[df_perfis["Ticker"] == ticker_selecionado].iloc[0] if not df_perfis[df_perfis["Ticker"] == ticker_selecionado].empty else None
    metricas_empresa = df_metricas_anuais[df_metricas_anuais["Ticker"] == ticker_selecionado].sort_values(by="Ano", ascending=False)
    
    st.header(f"{info_empresa['Nome_Empresa']} ({info_empresa['Ticker']})")
    st.caption(f"Setor: {info_empresa['Setor_Manual']}")
    
    ultimo_ano_df = metricas_empresa.iloc[0] if not metricas_empresa.empty else None

    # --- DEFINIÇÃO DAS ABAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumo", "📈 Análise Financeira", "债券 Análise de Dívida", "👥 Comparáveis de Mercado"])

    # --- ABA 1: RESUMO ---
    with tab1:
        st.subheader("Descrição da Companhia")
        if perfil_empresa is not None:
            st.write(perfil_empresa.get('Descricao_Longa', 'Descrição não disponível.'))
            st.write(f"**Website:** [{perfil_empresa.get('Website')}]({perfil_empresa.get('Website')})")
        
        st.subheader("Histórico de Preços (Último Ano)")
        price_history = get_price_history(ticker_selecionado)
        if not price_history.empty:
            fig_preco = px.line(price_history, x=price_history.index, y="Close", title="Preço de Fechamento")
            st.plotly_chart(fig_preco, use_container_width=True)

    # --- ABA 2: ANÁLISE FINANCEIRA ---
    with tab2:
        if ultimo_ano_df is not None:
            st.subheader("Desempenho Financeiro Histórico")
            fig_performance = px.bar(metricas_empresa, x="Ano", y=["Receita_Liquida", "EBIT", "Lucro_Liquido"], barmode='group', title="Performance Anual")
            st.plotly_chart(fig_performance, use_container_width=True)

            st.subheader("Ratios de Rentabilidade (Último Ano)")
            roe = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Patrimonio_Liquido']) if ultimo_ano_df.get('Patrimonio_Liquido', 0) > 0 else 0
            margem_liquida = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Receita_Liquida']) if ultimo_ano_df.get('Receita_Liquida', 0) > 0 else 0
            
            col1, col2 = st.columns(2)
            col1.metric("ROE (Return on Equity)", f"{roe:.2%}")
            col2.metric("Margem Líquida", f"{margem_liquida:.2%}")
        else:
            st.warning("Não há dados financeiros anuais disponíveis para esta empresa.")
            
    # --- ABA 3: ANÁLISE DE DÍVIDA ---
    with tab3:
        st.subheader("Análise de Dívida")
        st.info("Funcionalidade em desenvolvimento.")
            
    # --- ABA 4: COMPARÁVEIS DE MERCADO ---
    with tab4:
        st.subheader(f"Análise de Comparáveis do Setor: {info_empresa['Setor_Manual']}")
        
        peers = df_empresas_master[df_empresas_master['Setor_Manual'] == info_empresa['Setor_Manual']]
        
        with st.spinner("Buscando dados de mercado para as empresas do setor..."):
            comparables_data = []
            for index, peer in peers.iterrows():
                peer_ticker = peer['Ticker']
                peer_market_data = get_market_data(peer_ticker)
                
                if not peer_market_data or not peer_market_data.get('marketCap'):
                    continue

                peer_financials = df_metricas_anuais[df_metricas_anuais['Ticker'] == peer_ticker].sort_values(by="Ano", ascending=False)
                if peer_financials.empty:
                    continue

                latest_financials = peer_financials.iloc[0]
                market_cap = peer_market_data.get('marketCap', 0)
                lucro_liquido = latest_financials.get('Lucro_Liquido', 0)
                patrimonio_liquido = latest_financials.get('Patrimonio_Liquido', 0)
                ebit = latest_financials.get('EBIT', 0)
                divida_total = peer_market_data.get('totalDebt', 0)
                caixa = peer_market_data.get('totalCash', 0)
                
                p_l = (market_cap / lucro_liquido) if lucro_liquido > 0 else 0
                p_vp = (market_cap / patrimonio_liquido) if patrimonio_liquido > 0 else 0
                enterprise_value = market_cap + divida_total - caixa
                ev_ebit = (enterprise_value / ebit) if ebit > 0 else 0
                
                comparables_data.append({
                    'Empresa': peer['Nome_Empresa'], 'Ticker': peer_ticker,
                    'P/L': p_l, 'P/VP': p_vp, 'EV/EBIT': ev_ebit
                })

        if comparables_data:
            df_comparables = pd.DataFrame(comparables_data).round(2)
            st.markdown("##### Tabela de Múltiplos do Setor")
            st.dataframe(df_comparables.set_index('Ticker'), use_container_width=True)
            st.markdown("##### Gráficos Comparativos de Valuation")
            col1, col2, col3 = st.columns(3)
            with col1:
                df_pl = df_comparables[(df_comparables['P/L'] > 0) & (df_comparables['P/L'] < 100)]
                fig_pl = px.bar(df_pl.sort_values('P/L'), x='Ticker', y='P/L', title='Comparativo de P/L', color='Empresa')
                st.plotly_chart(fig_pl, use_container_width=True)
            with col2:
                df_pvp = df_comparables[(df_comparables['P/VP'] > 0) & (df_comparables['P/VP'] < 20)]
                fig_pvp = px.bar(df_pvp.sort_values('P/VP'), x='Ticker', y='P/VP', title='Comparativo de P/VP', color='Empresa')
                st.plotly_chart(fig_pvp, use_container_width=True)
            with col3:
                df_evebit = df_comparables[(df_comparables['EV/EBIT'] > 0) & (df_comparables['EV/EBIT'] < 50)]
                fig_evebit = px.bar(df_evebit.sort_values('EV/EBIT'), x='Ticker', y='EV/EBIT', title='Comparativo de EV/EBIT', color='Empresa')
                st.plotly_chart(fig_evebit, use_container_width=True)
        else:
            st.warning("Não foi possível encontrar dados para os comparáveis do setor.")

else:
    st.info("Selecione uma empresa na barra lateral para começar a análise.")
