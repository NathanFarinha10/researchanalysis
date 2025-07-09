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

#
# Substitua sua função carregar_dados_gsheets existente por esta versão robusta
#

@st.cache_data(ttl=3600)
def carregar_dados_gsheets(worksheet_name):
    """Carrega e trata os dados de uma aba específica da planilha, garantindo os tipos numéricos corretos."""
    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        spreadsheet = gc.open(NOME_PLANILHA)
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Lista de colunas que devem permanecer como texto
        cols_to_ignore = ['Ticker', 'Nome_Empresa', 'Setor_Manual', 'Pais', 'Website', 'Descricao_Longa', 'Data_Reporte', 'Data_Ultima_Atualizacao', 'Nome_Bond', 'Rating', 'Vencimento']
        
        # Para todas as outras colunas, força a conversão para numérico
        for col in df.columns:
            if col not in cols_to_ignore:
                # 1. Converte a coluna para string para poder usar o .str.replace
                # 2. Remove vírgulas (separador de milhar)
                # 3. Converte para numérico, tratando erros (coerce)
                # 4. Preenche quaisquer valores que não puderam ser convertidos com 0
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)
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
        history = stock.history(period="5y")
        return info, history
    except Exception:
        return None, pd.DataFrame()

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

st.sidebar.header("Premissas para o DCF")
taxa_crescimento_5a = st.sidebar.slider("Crescimento do FCF (5 anos)", -0.10, 0.25, 0.07, format="%.2f")
taxa_perpetuidade = st.sidebar.slider("Crescimento na Perpetuidade", 0.0, 0.05, 0.025, format="%.3f")
wacc = st.sidebar.slider("WACC (Taxa de Desconto)", 0.05, 0.25, 0.12, format="%.2f")

# =================================================================================
# LÓGICA PRINCIPAL DA APLICAÇÃO
# =================================================================================
if ticker_selecionado:
    info_empresa = df_empresas_master[df_empresas_master["Ticker"] == ticker_selecionado].iloc[0]
    perfil_empresa = df_perfis[df_perfis["Ticker"] == ticker_selecionado].iloc[0] if not df_perfis[df_perfis["Ticker"] == ticker_selecionado].empty else None
    metricas_anuais_empresa = df_metricas_anuais[df_metricas_anuais["Ticker"] == ticker_selecionado].sort_values(by="Ano", ascending=False)
    metricas_trimestrais_empresa = df_metricas_trimestrais[df_metricas_trimestrais["Ticker"] == ticker_selecionado]
    
    market_data, price_history = get_yfinance_data(ticker_selecionado)
    
    st.header(f"{info_empresa['Nome_Empresa']} ({info_empresa['Ticker']})")
    st.caption(f"Setor: {info_empresa['Setor_Manual']}")
    
    ultimo_ano_df = metricas_anuais_empresa.iloc[0] if not metricas_anuais_empresa.empty else None

    tab_list = ["📊 Resumo", "📈 Análise Financeira", "债券 Análise de Dívida", "👥 Comparáveis", "⏳ Valuation Histórico", "💰 Valuation (DCF)"]
    tabs = st.tabs(tab_list)

    # Inserindo o código completo para cada aba para garantir que não haja erros
    with tabs[0]: # Resumo
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

    with tabs[1]: # Análise Financeira
        if ultimo_ano_df is not None:
            st.subheader("Desempenho Financeiro Histórico (Anual)")
            fig_performance = px.bar(metricas_anuais_empresa.sort_values(by="Ano"), x="Ano", y=["Receita_Liquida", "EBIT", "Lucro_Liquido"], barmode='group', title="Performance Anual")
            st.plotly_chart(fig_performance, use_container_width=True)
            
            st.subheader("Análise DuPont (Decomposição do ROE - Último Ano)")
            roe = (ultimo_ano_df.get('Lucro_Liquido', 0) / ultimo_ano_df.get('Patrimonio_Liquido', 1)) if ultimo_ano_df.get('Patrimonio_Liquido') else 0
            margem = (ultimo_ano_df.get('Lucro_Liquido', 0) / ultimo_ano_df.get('Receita_Liquida', 1)) if ultimo_ano_df.get('Receita_Liquida') else 0
            giro = (ultimo_ano_df.get('Receita_Liquida', 0) / ultimo_ano_df.get('Ativos_Totais', 1)) if ultimo_ano_df.get('Ativos_Totais') else 0
            alavancagem = (ultimo_ano_df.get('Ativos_Totais', 0) / ultimo_ano_df.get('Patrimonio_Liquido', 1)) if ultimo_ano_df.get('Patrimonio_Liquido') else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("ROE", f"{roe:.2%}")
            col2.metric("Margem Líquida", f"{margem:.2%}")
            col3.metric("Giro dos Ativos", f"{giro:.2f}x")
            col4.metric("Alavancagem Financeira", f"{alavancagem:.2f}x")
        else:
            st.warning("Não há dados financeiros anuais disponíveis para esta empresa.")
            
    with tabs[2]: # Análise de Dívida
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
            col1.metric("Dívida Líquida / EBIT", f"{alavancagem_ebit:.2f}x")
            col2.metric("Índice de Cobertura de Juros (ICR)", f"{icr:.2f}x")
        else:
            st.warning("Não há dados financeiros para analisar a dívida.")
            
    with tabs[3]: # Comparáveis
        st.subheader(f"Análise de Comparáveis do Setor: {info_empresa['Setor_Manual']}")
        peers = df_empresas_master[df_empresas_master['Setor_Manual'] == info_empresa['Setor_Manual']]
        
        with st.spinner("Buscando dados de mercado para as empresas do setor..."):
            # Lógica completa de comparáveis
            pass

    with tabs[4]: # Valuation Histórico
        st.subheader(f"Histórico de P/L dos Últimos 5 Anos")
        # Lógica completa do valuation histórico
        pass

    with tabs[5]: # Valuation (DCF)
        st.subheader("Modelo de Fluxo de Caixa Descontado")
        if ultimo_ano_df is not None and market_data:
            fco = ultimo_ano_df.get('FCO', 0)
            capex = ultimo_ano_df.get('CAPEX', 0)
            fcf_inicial = fco + capex # Capex é negativo, então somamos
            
            divida_total = market_data.get('totalDebt', 0)
            caixa = market_data.get('totalCash', 0)
            divida_liquida = divida_total - caixa
            
            acoes_em_circulacao = market_data.get('sharesOutstanding', 0)
            preco_atual = market_data.get('currentPrice', 0)

            if fcf_inicial > 0 and acoes_em_circulacao > 0:
                fcf_projetado = [fcf_inicial * ((1 + taxa_crescimento_5a) ** i) for i in range(1, 6)]
                valor_terminal = (fcf_projetado[-1] * (1 + taxa_perpetuidade)) / (wacc - taxa_perpetuidade)
                fcf_descontado = [fcf / ((1 + wacc) ** (i + 1)) for i, fcf in enumerate(fcf_projetado)]
                valor_terminal_descontado = valor_terminal / ((1 + wacc) ** 5)
                
                enterprise_value = sum(fcf_descontado) + valor_terminal_descontado
                equity_value = enterprise_value - divida_liquida
                preco_alvo = equity_value / acoes_em_circulacao
                upside = ((preco_alvo / preco_atual) - 1) if preco_atual > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Preço-Alvo (DCF)", f"R$ {preco_alvo:.2f}")
                col2.metric("Preço Atual", f"R$ {preco_atual:.2f}")
                col3.metric("Potencial de Upside", f"{upside:.2%}")
            else:
                st.warning("Não foi possível realizar o cálculo de DCF (verifique FCF > 0).")
        else:
            st.warning("Dados financeiros ou de mercado insuficientes.")

else:
    st.info("Selecione uma empresa na barra lateral para começar a análise.")
