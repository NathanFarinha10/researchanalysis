import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime
import gspread

# =================================================================================
# CONFIGURAÇÃO, FUNÇÕES E CARREGAMENTO DE DADOS
# =================================================================================
st.set_page_config(page_title="Plataforma de Análise", layout="wide")
st.title("Plataforma Integrada de Análise de Ativos")

NOME_PLANILHA = "Plataforma_DB_Final"

@st.cache_data(ttl=3600)
def carregar_dados_gsheets(worksheet_name):
    """Carrega e trata os dados de uma aba específica da planilha."""
    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        spreadsheet = gc.open(NOME_PLANILHA)
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        cols_to_numeric = [col for col in df.columns if col not in ['Ticker', 'Nome_Empresa', 'Setor_Manual', 'Pais', 'Website', 'Descricao_Longa', 'Data_Reporte', 'Data_Ultima_Atualizacao', 'Nome_Bond', 'Rating', 'Vencimento']]
        for col in cols_to_numeric:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a aba '{worksheet_name}': {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_yfinance_data(ticker):
    """Busca dados de info e histórico de preços do yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period="5y") # Pegando 5 anos para o gráfico histórico
        return info, history
    except Exception:
        return None, pd.DataFrame()

def calcular_ytm(preco_atual, valor_face, cupom_anual, anos_vencimento, pagamentos_anuais=1):
    """Calcula o Yield to Maturity (YTM) de um título."""
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

# Carregamento inicial de todos os dados
df_empresas_master = carregar_dados_gsheets("empresas_master")
df_perfis = carregar_dados_gsheets("perfis_empresas")
df_metricas_anuais = carregar_dados_gsheets("metricas_anuais")
df_metricas_trimestrais = carregar_dados_gsheets("metricas_trimestrais")
df_bonds = carregar_dados_gsheets("dados_bonds")

# =================================================================================
# BARRA LATERAL (SIDEBAR)
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
    # --- FILTRAGEM DE DADOS PARA O ATIVO SELECIONADO ---
    info_empresa = df_empresas_master[df_empresas_master["Ticker"] == ticker_selecionado].iloc[0]
    perfil_empresa = df_perfis[df_perfis["Ticker"] == ticker_selecionado].iloc[0] if not df_perfis[df_perfis["Ticker"] == ticker_selecionado].empty else None
    metricas_anuais_empresa = df_metricas_anuais[df_metricas_anuais["Ticker"] == ticker_selecionado].sort_values(by="Ano", ascending=False)
    metricas_trimestrais_empresa = df_metricas_trimestrais[df_metricas_trimestrais["Ticker"] == ticker_selecionado]
    
    market_data, price_history = get_yfinance_data(ticker_selecionado)
    
    st.header(f"{info_empresa['Nome_Empresa']} ({info_empresa['Ticker']})")
    st.caption(f"Setor: {info_empresa['Setor_Manual']}")
    
    ultimo_ano_df = metricas_anuais_empresa.iloc[0] if not metricas_anuais_empresa.empty else None

    # --- DEFINIÇÃO DAS ABAS ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Resumo", "📈 Análise Financeira", "债券 Análise de Dívida", "👥 Comparáveis", "⏳ Valuation Histórico"])

    # --- ABA 1: RESUMO ---
    with tab1:
        st.subheader("Descrição da Companhia")
        if perfil_empresa is not None:
            st.write(perfil_empresa.get('Descricao_Longa', 'Descrição não disponível.'))
            website = perfil_empresa.get('Website', '#')
            st.write(f"**Website:** [{website}]({website})")
        else:
            st.warning("Perfil da empresa não encontrado na base de dados.")

        st.subheader("Histórico de Preços (Últimos 5 Anos)")
        if not price_history.empty:
            fig_preco = px.line(price_history, x=price_history.index, y="Close", title=f"Preço de Fechamento - {ticker_selecionado}")
            st.plotly_chart(fig_preco, use_container_width=True)
        else:
            st.warning(f"Não foi possível carregar o histórico de preços para o ticker {ticker_selecionado}.")

    # --- ABA 2: ANÁLISE FINANCEIRA ---
    with tab2:
        if ultimo_ano_df is not None:
            st.subheader("Desempenho Financeiro Histórico (Anual)")
            fig_performance = px.bar(metricas_anuais_empresa.sort_values(by="Ano"), x="Ano", y=["Receita_Liquida", "EBIT", "Lucro_Liquido"], barmode='group', title="Performance Anual (em Milhões)")
            st.plotly_chart(fig_performance, use_container_width=True)

            st.subheader("Análise DuPont (Decomposição do ROE - Último Ano)")
            roe = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Patrimonio_Liquido']) if ultimo_ano_df.get('Patrimonio_Liquido', 0) > 0 else 0
            margem = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Receita_Liquida']) if ultimo_ano_df.get('Receita_Liquida', 0) > 0 else 0
            giro = (ultimo_ano_df['Receita_Liquida'] / ultimo_ano_df['Ativos_Totais']) if ultimo_ano_df.get('Ativos_Totais', 0) > 0 else 0
            alavancagem = (ultimo_ano_df['Ativos_Totais'] / ultimo_ano_df['Patrimonio_Liquido']) if ultimo_ano_df.get('Patrimonio_Liquido', 0) > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("ROE", f"{roe:.2%}")
            col2.metric("Margem Líquida", f"{margem:.2%}")
            col3.metric("Giro dos Ativos", f"{giro:.2f}x")
            col4.metric("Alavancagem Financeira", f"{alavancagem:.2f}x")
        else:
            st.warning("Não há dados financeiros anuais disponíveis para esta empresa.")
    
    # --- ABA 3: ANÁLISE DE DÍVIDA ---
    with tab3:
        st.subheader("Perfil da Dívida e Métricas de Crédito")
        if ultimo_ano_df is not None:
            ebit = ultimo_ano_df.get('EBIT', 0)
            divida_lp = ultimo_ano_df.get('Divida_Longo_Prazo', 0)
            caixa = ultimo_ano_df.get('Caixa', 0)
            despesa_juros = ultimo_ano_df.get('Despesa_Juros', 0)
            divida_liquida = divida_lp - caixa
            
            alavancagem_ebit = (divida_liquida / ebit) if ebit > 0 else 0
            icr = (ebit / abs(despesa_juros)) if despesa_juros != 0 else 0
            
            col1, col2 = st.columns(2)
            col1.metric("Dívida Líquida / EBIT", f"{alavancagem_ebit:.2f}x", help="Métrica de alavancagem.")
            col2.metric("Índice de Cobertura de Juros (ICR)", f"{icr:.2f}x", help="EBIT / Despesa com Juros.")

            st.markdown("---")
            st.markdown("##### Cronograma de Vencimento da Dívida")
            bonds_da_empresa = df_bonds[df_bonds['Ticker'] == ticker_selecionado].copy()

            if not bonds_da_empresa.empty:
                bonds_da_empresa['Ano_Vencimento'] = pd.to_datetime(bonds_da_empresa['Vencimento'], dayfirst=True, errors='coerce').dt.year
                perfil_divida = bonds_da_empresa.groupby('Ano_Vencimento')['Valor_Emissao_MM'].sum().reset_index()
                fig_divida = px.bar(perfil_divida, x='Ano_Vencimento', y='Valor_Emissao_MM', title='Valor a Vencer por Ano (MM)')
                st.plotly_chart(fig_divida, use_container_width=True)
            else:
                st.info("Nenhum título de dívida cadastrado para esta empresa.")
        else:
            st.warning("Não há dados financeiros para analisar a dívida.")
            
    # --- ABA 4: COMPARÁVEIS DE MERCADO ---
    with tab4:
        st.subheader(f"Análise de Comparáveis do Setor: {info_empresa['Setor_Manual']}")
        # ... (código da aba de comparáveis que já funcionava) ...
        pass

    # --- ABA 5: VALUATION HISTÓRICO ---
    with tab5:
        st.subheader(f"Histórico de P/L (Preço/Lucro) dos Últimos 5 Anos")
        # ... (código da aba de valuation histórico que já funcionava) ...
        pass

else:
    st.info("Selecione uma empresa na barra lateral para começar a análise.")


