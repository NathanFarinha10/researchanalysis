import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime
import gspread

# =================================================================================
# CONFIGURAÇÃO E CONEXÃO DE DADOS (VERSÃO FINAL)
# =================================================================================
st.set_page_config(page_title="Plataforma de Análise", layout="wide")
st.title("Plataforma Integrada de Análise de Ativos")

NOME_PLANILHA = "Plataforma_DB_Final"

@st.cache_data(ttl=3600) # Cache de 1 hora
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

# Carrega todos os dados das abas corretas
df_empresas_master = carregar_dados_gsheets("empresas_master")
df_perfis = carregar_dados_gsheets("perfis_empresas")
df_metricas_anuais = carregar_dados_gsheets("metricas_anuais")
df_bonds = carregar_dados_gsheets("dados_bonds")

@st.cache_data(ttl=3600)
def get_price_history(ticker):
    """Busca histórico de preços do yfinance."""
    try:
        stock = yf.Ticker(ticker)
        return stock.history(period="1y")
    except Exception:
        return pd.DataFrame()

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
# LÓGICA PRINCIPAL
# =================================================================================
if ticker_selecionado:
    # --- FILTRAGEM DE DADOS ---
    info_empresa = df_empresas_master[df_empresas_master["Ticker"] == ticker_selecionado].iloc[0]
    perfil_empresa = df_perfis[df_perfis["Ticker"] == ticker_selecionado].iloc[0] if not df_perfis[df_perfis["Ticker"] == ticker_selecionado].empty else None
    metricas_empresa = df_metricas_anuais[df_metricas_anuais["Ticker"] == ticker_selecionado].sort_values(by="Ano", ascending=False)
    
    st.header(f"{info_empresa['Nome_Empresa']} ({info_empresa['Ticker']})")
    st.caption(f"Setor: {info_empresa['Setor_Manual']}")
    
    # Pega o último ano de métricas disponíveis
    ultimo_ano_df = metricas_empresa.iloc[0] if not metricas_empresa.empty else None

    # --- DEFINIÇÃO DAS ABAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumo", "📈 Análise Financeira", "债券 Análise de Dívida", "👥 Comparáveis de Mercado"])

    # --- ABA 1: RESUMO ---
    with tab1:
        st.subheader("Descrição da Companhia")
        if perfil_empresa is not None:
            st.write(perfil_empresa['Descricao_Longa'])
            st.write(f"**Website:** [{perfil_empresa['Website']}]({perfil_empresa['Website']})")
        
        st.subheader("Histórico de Preços (Último Ano)")
        price_history = get_price_history(ticker_selecionado)
        if not price_history.empty:
            fig_preco = px.line(price_history, x=price_history.index, y="Close", title="Preço de Fechamento")
            st.plotly_chart(fig_preco, use_container_width=True)

    # --- ABA 2: ANÁLISE FINANCEIRA ---
    with tab2:
        if ultimo_ano_df is not None:
            st.subheader("Desempenho Financeiro Histórico")
            fig = px.bar(metricas_empresa, x="Ano", y=["Receita_Liquida", "EBIT", "Lucro_Liquido"], barmode='group', title="Performance Anual")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Ratios de Rentabilidade e Eficiência (Último Ano)")
            roe = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Patrimonio_Liquido']) if ultimo_ano_df['Patrimonio_Liquido'] > 0 else 0
            margem_liquida = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Receita_Liquida']) if ultimo_ano_df['Receita_Liquida'] > 0 else 0
            
            col1, col2 = st.columns(2)
            col1.metric("ROE (Return on Equity)", f"{roe:.2%}")
            col2.metric("Margem Líquida", f"{margem_liquida:.2%}")
        else:
            st.warning("Não há dados financeiros anuais disponíveis para esta empresa.")

    # --- ABA 3: ANÁLISE DE DÍVIDA ---
    with tab3:
        if ultimo_ano_df is not None:
             st.subheader("Perfil da Dívida")
             # A lógica completa da Aba de Dívida pode ser inserida aqui, lendo de `df_bonds`
             st.info("Funcionalidade de análise de bonds em desenvolvimento nesta nova arquitetura.")
        else:
            st.warning("Não há dados financeiros para analisar a dívida.")
            
    # --- ABA 4: COMPARÁVEIS DE MERCADO ---
   with tab4:
        st.subheader(f"Análise de Comparáveis do Setor: {info_empresa['Setor_Manual']}")
        
        # 1. Encontrar os pares (peers)
        peers = df_empresas_master[df_empresas_master['Setor_Manual'] == info_empresa['Setor_Manual']]
        
        # 2. Coletar e calcular dados para os pares
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
                
                # Coleta de dados para os cálculos
                market_cap = peer_market_data.get('marketCap', 0)
                lucro_liquido = latest_financials.get('Lucro_Liquido', 0)
                patrimonio_liquido = latest_financials.get('Patrimonio_Liquido', 0)
                ebit = latest_financials.get('EBIT', 0)
                divida_total = peer_market_data.get('totalDebt', 0)
                caixa = peer_market_data.get('totalCash', 0)
                
                # Cálculos dos múltiplos
                p_l = (market_cap / lucro_liquido) if lucro_liquido > 0 else 0
                p_vp = (market_cap / patrimonio_liquido) if patrimonio_liquido > 0 else 0
                
                enterprise_value = market_cap + divida_total - caixa
                ev_ebit = (enterprise_value / ebit) if ebit > 0 else 0
                
                comparables_data.append({
                    'Empresa': peer['Nome_Empresa'],
                    'Ticker': peer_ticker,
                    'P/L': p_l,
                    'P/VP': p_vp,
                    'EV/EBIT': ev_ebit
                })

        if comparables_data:
            df_comparables = pd.DataFrame(comparables_data).round(2)
            
            # 3. Exibir a tabela de comparáveis
            st.markdown("##### Tabela de Múltiplos do Setor")
            st.dataframe(df_comparables.set_index('Ticker'), use_container_width=True)

            # 4. Exibir gráficos comparativos
            st.markdown("##### Gráficos Comparativos de Valuation")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                df_pl = df_comparables[(df_comparables['P/L'] > 0) & (df_comparables['P/L'] < 100)] # Filtra outliers
                fig_pl = px.bar(df_pl.sort_values('P/L'), x='Ticker', y='P/L', title='Comparativo de P/L', color='Empresa')
                st.plotly_chart(fig_pl, use_container_width=True)
            
            with col2:
                df_pvp = df_comparables[(df_comparables['P/VP'] > 0) & (df_comparables['P/VP'] < 20)] # Filtra outliers
                fig_pvp = px.bar(df_pvp.sort_values('P/VP'), x='Ticker', y='P/VP', title='Comparativo de P/VP', color='Empresa')
                st.plotly_chart(fig_pvp, use_container_width=True)
                
            with col3:
                df_evebit = df_comparables[(df_comparables['EV/EBIT'] > 0) & (df_comparables['EV/EBIT'] < 50)] # Filtra outliers
                fig_evebit = px.bar(df_evebit.sort_values('EV/EBIT'), x='Ticker', y='EV/EBIT', title='Comparativo de EV/EBIT', color='Empresa')
                st.plotly_chart(fig_evebit, use_container_width=True)
        else:
            st.warning("Não foi possível encontrar dados para os comparáveis do setor.")
else:
    st.info("Selecione uma empresa na barra lateral para começar a análise.")
