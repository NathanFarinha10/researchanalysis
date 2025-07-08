import streamlit as st
import pandas as pd
from gsheetsdb import GSheetsConnection

# =================================================================================
# CONFIGURAÇÕES DA PÁGINA
# =================================================================================
# Configura o título da página, ícone e layout.
st.set_page_config(
    page_title="Análise de Emissores",
    page_icon="📈",
    layout="wide"
)

# Título principal da aplicação.
st.title("Plataforma de Análise de Bonds e Equity")
st.markdown("---")


# =================================================================================
# CONEXÃO E CARREGAMENTO DE DADOS (com cache)
# =================================================================================
# O @st.cache_data é um "decorador" que armazena o resultado da função em memória.
# Isso evita que a aplicação precise recarregar os dados da planilha toda vez
# que o usuário interage com um widget. O 'ttl=600' define que o cache
# expira a cada 10 minutos (600 segundos), buscando dados frescos.

@st.cache_data(ttl=600)
def carregar_dados_empresas():
    """Função para carregar a aba 'empresas' da nossa planilha."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_empresas = conn.read(worksheet="empresas", usecols=list(range(5)), header=0)
    # Remove linhas que possam estar completamente vazias
    df_empresas.dropna(how="all", inplace=True)
    return df_empresas

@st.cache_data(ttl=600)
def carregar_demonstrativos():
    """Função para carregar a aba 'demonstrativos_financeiros'."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_demonstrativos = conn.read(worksheet="demonstrativos_financeiros", usecols=list(range(8)), header=0)
    df_demonstrativos.dropna(how="all", inplace=True)
    return df_demonstrativos

# Carrega os dados usando as funções definidas acima.
df_empresas = carregar_dados_empresas()
df_demonstrativos = carregar_demonstrativos()


# =================================================================================
# INTERFACE DO USUÁRIO (UI) - BARRA LATERAL E SELEÇÃO DE EMPRESA
# =================================================================================
st.sidebar.header("Filtros")

# Cria uma lista com os nomes das empresas para o usuário escolher.
lista_empresas = df_empresas["Nome_Empresa"].tolist()

# Cria o menu dropdown (selectbox) na barra lateral.
empresa_selecionada_nome = st.sidebar.selectbox(
    "Selecione a Empresa:",
    options=lista_empresas
)


# =================================================================================
# LÓGICA DE FILTRAGEM E EXIBIÇÃO DOS DADOS
# =================================================================================
if empresa_selecionada_nome:
    # 1. Encontrar as informações da empresa selecionada no dataframe 'df_empresas'.
    info_empresa = df_empresas[df_empresas["Nome_Empresa"] == empresa_selecionada_nome].iloc[0]
    
    # 2. Obter o ID da empresa para usar como filtro.
    id_empresa_selecionada = info_empresa["ID_Empresa"]
    
    # 3. Filtrar o dataframe 'df_demonstrativos' para obter apenas os dados da empresa selecionada.
    demonstrativos_filtrados = df_demonstrativos[df_demonstrativos["ID_Empresa"] == id_empresa_selecionada]

    # 4. Exibir as informações na tela.
    st.header(f"Análise de: {empresa_selecionada_nome}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ticker", info_empresa["Ticker_Acao"])
    col2.metric("Setor", info_empresa["Setor"])
    col3.metric("País", info_empresa["Pais"])
    
    st.markdown("### Demonstrativos Financeiros")
    st.dataframe(demonstrativos_filtrados)

else:
    st.warning("Por favor, selecione uma empresa na barra lateral.")
