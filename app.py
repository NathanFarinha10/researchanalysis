import streamlit as st
import pandas as pd

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
# CARREGAMENTO DE DADOS (MÉTODO CSV PÚBLICO)
# =================================================================================
# --- COLE SEUS URLs AQUI ---
# Substitua "URL_GERADO_PARA_A_ABA_EMPRESAS" pelo link que você copiou.
URL_EMPRESAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=0&single=true&output=csv"
# Substitua "URL_GERADO_PARA_A_ABA_DEMONSTRATIVOS" pelo outro link.
URL_DEMONSTRATIVOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=842583931&single=true&output=csv"
# -------------------------

@st.cache_data(ttl=600)
def carregar_dados(url):
    """Função genérica para carregar dados de uma URL CSV do Google Sheets."""
    df = pd.read_csv(url)
    return df

# Carrega os dados usando a função.
df_empresas = carregar_dados(URL_EMPRESAS)
df_demonstrativos = carregar_dados(URL_DEMONSTRATIVOS)


# =================================================================================
# INTERFACE DO USUÁRIO (UI) - BARRA LATERAL E SELEÇÃO DE EMPRESA
# (Esta parte do código não muda)
# =================================================================================
st.sidebar.header("Filtros")

lista_empresas = df_empresas["Nome_Empresa"].tolist()

empresa_selecionada_nome = st.sidebar.selectbox(
    "Selecione a Empresa:",
    options=lista_empresas
)


# =================================================================================
# LÓGICA DE FILTRAGEM E EXIBIÇÃO DOS DADOS
# (Esta parte do código não muda)
# =================================================================================
if empresa_selecionada_nome:
    info_empresa = df_empresas[df_empresas["Nome_Empresa"] == empresa_selecionada_nome].iloc[0]
    id_empresa_selecionada = info_empresa["ID_Empresa"]
    demonstrativos_filtrados = df_demonstrativos[df_demonstrativos["ID_Empresa"] == id_empresa_selecionada]

    st.header(f"Análise de: {empresa_selecionada_nome}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ticker", info_empresa["Ticker_Acao"])
    col2.metric("Setor", info_empresa["Setor"])
    col3.metric("País", info_empresa["Pais"])
    
    st.markdown("### Demonstrativos Financeiros")
    st.dataframe(demonstrativos_filtrados)
else:
    st.warning("Por favor, selecione uma empresa na barra lateral.")
