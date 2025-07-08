import streamlit as st
import pandas as pd
import plotly.express as px  # <- NOVA IMPORTAÇÃO

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
URL_EMPRESAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=0&single=true&output=csv"
URL_DEMONSTRATIVOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=842583931&single=true&output=csv"
# -------------------------

@st.cache_data(ttl=600)
def carregar_dados(url):
    df = pd.read_csv(url)
    return df

df_empresas = carregar_dados(URL_EMPRESAS)
df_demonstrativos = carregar_dados(URL_DEMONSTRATIVOS)

# =================================================================================
# INTERFACE DO USUÁRIO (UI) - BARRA LATERAL E SELEÇÃO DE EMPRESA
# =================================================================================
st.sidebar.header("Filtros")

lista_empresas = df_empresas["Nome_Empresa"].tolist()

empresa_selecionada_nome = st.sidebar.selectbox(
    "Selecione a Empresa:",
    options=lista_empresas
)

# =================================================================================
# LÓGICA DE FILTRAGEM E EXIBIÇÃO DOS DADOS
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
    
    st.markdown("---") # Adicionando uma linha divisória

    # =================================================================================
    # SEÇÃO DE GRÁFICOS (NOVA SEÇÃO)
    # =================================================================================
    st.markdown("### Desempenho Financeiro Anual")

    # Garante que os dados estejam ordenados por ano para o gráfico.
    demonstrativos_filtrados = demonstrativos_filtrados.sort_values(by="Ano")

    # Cria a figura do gráfico de barras com o Plotly Express.
    fig = px.bar(
        demonstrativos_filtrados,
        x="Ano",
        y=["Receita_Liquida", "EBITDA", "Lucro_Liquido"],
        title="Receita, EBITDA e Lucro Líquido (em Milhões)",
        labels={'value': 'Valores', 'variable': 'Métrica Financeira'},
        barmode='group' # 'group' para barras lado a lado, 'stack' para empilhadas
    )

    # Exibe o gráfico no Streamlit. O use_container_width faz o gráfico se ajustar à largura da tela.
    st.plotly_chart(fig, use_container_width=True)


    st.markdown("### Dados Financeiros Detalhados")
    st.dataframe(demonstrativos_filtrados) # Mantemos a tabela para quem quiser ver os números.
else:
    st.warning("Por favor, selecione uma empresa na barra lateral.")
