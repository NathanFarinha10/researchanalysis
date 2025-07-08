import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime # <- NOVA IMPORTAÇÃO

# =================================================================================
# CONFIGURAÇÕES DA PÁGINA E CARREGAMENTO DE DADOS (sem alterações)
# =================================================================================
st.set_page_config(
    page_title="Análise de Emissores",
    page_icon="📈",
    layout="wide"
)
st.title("Plataforma de Análise de Bonds e Equity")
st.markdown("---")

URL_EMPRESAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=0&single=true&output=csv"
URL_DEMONSTRATIVOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=842583931&single=true&output=csv"
URL_BONDS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpOR6lS0j4bv0PSQmj3KkrWdXlJU8ppseLJvkajDl-CXUfcKU-qKqp2EO15zAFFYYM1ImmT30IOgGj/pub?gid=1081884812&single=true&output=csv" # <- ATUALIZE ESTE URL

@st.cache_data(ttl=600)
def carregar_dados(url):
    df = pd.read_csv(url)
    return df

@st.cache_data(ttl=3600)
def get_market_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        market_cap = stock.info.get('marketCap')
        return market_cap
    except Exception as e:
        return None

# =================================================================================
# NOVA FUNÇÃO: CÁLCULO DO YIELD TO MATURITY (YTM)
# =================================================================================
def calcular_ytm(preco_atual, valor_face, cupom_anual, anos_vencimento, pagamentos_anuais=1):
    """
    Calcula o Yield to Maturity (YTM) de um título usando um método numérico.
    """
    if anos_vencimento <= 0:
        return 0.0

    taxa_cupom_periodo = cupom_anual / pagamentos_anuais
    num_periodos = anos_vencimento * pagamentos_anuais
    
    # Tenta encontrar a taxa (yield) por tentativa e erro (método de Newton-Raphson simplificado)
    ytm_estimado = cupom_anual # Chute inicial
    for _ in range(100): # 100 iterações para encontrar a taxa
        # Calcula o Preço Presente com base na estimativa atual de YTM
        preco_estimado = 0
        ytm_periodo = ytm_estimado / pagamentos_anuais
        
        # Soma dos cupons trazidos a valor presente
        for i in range(1, int(num_periodos) + 1):
            preco_estimado += (taxa_cupom_periodo * valor_face) / ((1 + ytm_periodo) ** i)
        
        # Soma do valor de face trazido a valor presente
        preco_estimado += valor_face / ((1 + ytm_periodo) ** num_periodos)
        
        # Se o preço estimado está próximo do preço real, encontramos o YTM
        if abs(preco_estimado - preco_atual) < 0.0001:
            return ytm_estimado
        
        # Ajusta a estimativa para a próxima iteração
        if preco_estimado > preco_atual:
            ytm_estimado += 0.0001 # Aumenta o yield para diminuir o preço
        else:
            ytm_estimado -= 0.0001 # Diminui o yield para aumentar o preço
            
    return ytm_estimado # Retorna a melhor estimativa encontrada


# Carrega todos os dados
df_empresas = carregar_dados(URL_EMPRESAS)
df_demonstrativos = carregar_dados(URL_DEMONSTRATIVOS)
df_bonds = carregar_dados(URL_BONDS)

# =================================================================================
# BARRA LATERAL (sem alterações)
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
    # Filtra dados da empresa (sem alterações)
    info_empresa = df_empresas[df_empresas["Nome_Empresa"] == empresa_selecionada_nome].iloc[0]
    id_empresa_selecionada = info_empresa["ID_Empresa"]
    demonstrativos_filtrados = df_demonstrativos[df_demonstrativos["ID_Empresa"] == id_empresa_selecionada].sort_values(by="Ano")
    
    st.header(f"Análise de: {empresa_selecionada_nome}")
    
    # Lente de Equity (sem alterações)
    st.subheader("Lente de Análise de Equity")
    # ... (código da lente de equity permanece o mesmo)
    
    st.markdown("---")

    # --- LENTE DE CRÉDITO (SEÇÃO ATUALIZADA) ---
    st.subheader("Lente de Análise de Dívida (Corporate Bonds)")

    # Pega os dados financeiros mais recentes
    ultimo_ano_df = demonstrativos_filtrados.iloc[-1]
    ebitda = ultimo_ano_df['EBITDA']
    divida_bruta = ultimo_ano_df['Divida_Bruta']
    caixa = ultimo_ano_df['Caixa']
    
    # Calcular métricas de alavancagem
    divida_liquida = divida_bruta - caixa
    alavancagem = f"{(divida_liquida / ebitda):.2f}x" if ebitda > 0 else "N/A"

    col_cred_1, col_cred_2 = st.columns(2)
    col_cred_1.metric("Dívida Líquida / EBITDA (Alavancagem)", alavancagem)

    st.markdown("##### Títulos de Dívida Emitidos e Análise de Rentabilidade")
    bonds_da_empresa = df_bonds[df_bonds['ID_Empresa'] == id_empresa_selecionada]
    
    if not bonds_da_empresa.empty:
        for index, bond in bonds_da_empresa.iterrows():
            with st.expander(f"**{bond['Nome_Bond']}** - Vencimento: {bond['Vencimento']}"):
                # Calcular anos até o vencimento
                data_vencimento = datetime.strptime(bond['Vencimento'], '%d/%m/%Y')
                anos_vencimento = (data_vencimento - datetime.now()).days / 365.25

                # Calcular YTM
                ytm = calcular_ytm(
                    preco_atual=bond['Preco_Atual'],
                    valor_face=100, # Assumindo valor de face 100
                    cupom_anual=bond['Cupom_Anual'],
                    anos_vencimento=anos_vencimento,
                    pagamentos_anuais=bond['Pagamentos_Anuais']
                )

                # Exibir detalhes do Bond e seu YTM
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Preço Atual", f"${bond['Preco_Atual']:.2f}")
                col2.metric("Cupom", f"{bond['Cupom_Anual']:.3%}")
                col3.metric("Rating", bond['Rating'])
                col4.metric("Yield to Maturity (YTM)", f"{ytm:.3%}", help="Retorno anualizado esperado se o título for mantido até o vencimento.")

    else:
        st.info("Nenhum título de dívida cadastrado para esta empresa.")

    st.markdown("---")
    
    # Seções de Gráficos e Dados detalhados (sem alterações)
    # ... (código dos gráficos e da tabela permanece o mesmo)

else:
    st.warning("Por favor, selecione uma empresa na barra lateral.")
