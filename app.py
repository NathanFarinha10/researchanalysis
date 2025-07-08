import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf # <- NOVA IMPORTAÇÃO

# =================================================================================
# CONFIGURAÇÕES DA PÁGINA
# =================================================================================
st.set_page_config(
    page_title="Análise de Emissores",
    page_icon="📈",
    layout="wide"
)

st.title("Plataforma de Análise de Bonds e Equity")
st.markdown("---")

# =================================================================================
# CARREGAMENTO DE DADOS
# =================================================================================
URL_EMPRESAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=0&single=true&output=csv"
URL_DEMONSTRATIVOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=842583931&single=true&output=csv"

@st.cache_data(ttl=600)
def carregar_dados(url):
    df = pd.read_csv(url)
    return df

# NOVA FUNÇÃO PARA BUSCAR DADOS DE MERCADO
@st.cache_data(ttl=3600) # Cache de 1 hora para dados de mercado
def get_market_data(ticker):
    """Busca dados de mercado (Market Cap) usando yfinance."""
    try:
        stock = yf.Ticker(ticker)
        market_cap = stock.info.get('marketCap')
        return market_cap
    except Exception as e:
        st.error(f"Erro ao buscar dados para o ticker {ticker}: {e}")
        return None

df_empresas = carregar_dados(URL_EMPRESAS)
df_demonstrativos = carregar_dados(URL_DEMONSTRATIVOS)

# =================================================================================
# BARRA LATERAL E SELEÇÃO DE EMPRESA
# =================================================================================
st.sidebar.header("Filtros")
lista_empresas = df_empresas["Nome_Empresa"].tolist()
empresa_selecionada_nome = st.sidebar.selectbox(
    "Selecione a Empresa:",
    options=lista_empresas
)

# =================================================================================
# LÓGICA PRINCIPAL E EXIBIÇÃO
# =================================================================================
if empresa_selecionada_nome:
    # Filtra dados da empresa selecionada
    info_empresa = df_empresas[df_empresas["Nome_Empresa"] == empresa_selecionada_nome].iloc[0]
    id_empresa_selecionada = info_empresa["ID_Empresa"]
    demonstrativos_filtrados = df_demonstrativos[df_demonstrativos["ID_Empresa"] == id_empresa_selecionada].sort_values(by="Ano")

    st.header(f"Análise de: {empresa_selecionada_nome}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ticker", info_empresa["Ticker_Acao"])
    col2.metric("Setor", info_empresa["Setor"])
    col3.metric("País", info_empresa["Pais"])
    
    st.markdown("---")

    # --- NOVA SEÇÃO: MÚLTIPLOS DE VALUATION ---
    st.markdown("### Múltiplos de Valuation")
    
    # 1. Obter dados de mercado
    ticker_acao = info_empresa["Ticker_Acao"]
    market_cap = get_market_data(ticker_acao)
    
    if market_cap:
        # 2. Obter os dados financeiros mais recentes
        ultimo_ano_df = demonstrativos_filtrados.iloc[-1]
        lucro_liquido = ultimo_ano_df['Lucro_Liquido']
        patrimonio_liquido = ultimo_ano_df['Patrimonio_Liquido']
        ebitda = ultimo_ano_df['EBITDA']
        divida_bruta = ultimo_ano_df['Divida_Bruta']
        caixa = ultimo_ano_df['Caixa']
        
        # 3. Calcular os múltiplos
        # P/L
        p_l = "N/A"
        if lucro_liquido > 0:
            p_l_value = market_cap / (lucro_liquido * 1_000_000) # Ajusta para milhões
            p_l = f"{p_l_value:.2f}x"
        
        # P/VP
        p_vp = "N/A"
        if patrimonio_liquido > 0:
            p_vp_value = market_cap / (patrimonio_liquido * 1_000_000) # Ajusta para milhões
            p_vp = f"{p_vp_value:.2f}x"

        # EV/EBITDA
        ev_ebitda = "N/A"
        if ebitda > 0:
            divida_liquida = divida_bruta - caixa
            ev = market_cap + (divida_liquida * 1_000_000) # Ajusta para milhões
            ev_ebitda_value = ev / (ebitda * 1_000_000) # Ajusta para milhões
            ev_ebitda = f"{ev_ebitda_value:.2f}x"
            
        # 4. Exibir os múltiplos
        col_mult_1, col_mult_2, col_mult_3 = st.columns(3)
        col_mult_1.metric("P/L", p_l)
        col_mult_2.metric("P/VP", p_vp)
        col_mult_3.metric("EV/EBITDA", ev_ebitda)
        
    else:
        st.warning(f"Não foi possível calcular os múltiplos. Verifique o ticker: {ticker_acao}")


    st.markdown("---")
    
    # Seção de Gráficos (existente)
    st.markdown("### Desempenho Financeiro Anual")
    fig = px.bar(
        demonstrativos_filtrados, x="Ano", y=["Receita_Liquida", "EBITDA", "Lucro_Liquido"],
        title="Receita, EBITDA e Lucro Líquido (em Milhões)",
        labels={'value': 'Valores', 'variable': 'Métrica Financeira'},
        barmode='group'
    )
    st.plotly_chart(fig, use_container_width=True)

    # Seção de Dados Detalhados (existente)
    st.markdown("### Dados Financeiros Detalhados")
    st.dataframe(demonstrativos_filtrados)
else:
    st.warning("Por favor, selecione uma empresa na barra lateral.")
