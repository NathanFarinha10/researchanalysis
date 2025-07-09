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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Resumo", "📈 Análise Financeira", "债券 Análise de Dívida", "👥 Comparáveis", "⏳ Valuation Histórico"])

    # --- ABA 1: RESUMO ---
    # --- ABA 1: RESUMO ---
    with tab1:
        st.subheader("Descrição da Companhia")
        if perfil_empresa is not None:
            st.write(perfil_empresa.get('Descricao_Longa', 'Descrição não disponível.'))
            st.write(f"**Website:** [{perfil_empresa.get('Website', '#')}]({perfil_empresa.get('Website', '#')})")
        else:
            st.warning("Perfil da empresa não encontrado na base de dados.")

        st.subheader("Histórico de Preços (Último Ano)")
        price_history = get_price_history(ticker_selecionado)
        
        # Lógica de verificação aprimorada
        if not price_history.empty:
            fig_preco = px.line(price_history, x=price_history.index, y="Close", title=f"Preço de Fechamento - {ticker_selecionado}")
            st.plotly_chart(fig_preco, use_container_width=True)
        else:
            # Mensagem de aviso que aparecerá se o gráfico não puder ser gerado
            st.warning(f"Não foi possível carregar o histórico de preços para o ticker {ticker_selecionado}. Isso pode ser um problema temporário com a fonte de dados (yfinance) ou o ticker pode não ter dados de preço disponíveis.")

    # --- ABA 2: ANÁLISE FINANCEIRA ---
    # --- ABA 2: ANÁLISE FINANCEIRA ---
    with tab2:
        if ultimo_ano_df is not None and not metricas_empresa.empty:
            st.subheader("Desempenho Financeiro Histórico")
            fig_performance = px.bar(metricas_empresa.sort_values(by="Ano"), x="Ano", y=["Receita_Liquida", "EBIT", "Lucro_Liquido"], barmode='group', title="Performance Anual")
            st.plotly_chart(fig_performance, use_container_width=True)

            st.subheader("Ratios de Rentabilidade (Último Ano)")
            roe_ultimo_ano = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Patrimonio_Liquido']) if ultimo_ano_df.get('Patrimonio_Liquido', 0) > 0 else 0
            margem_liquida_ultimo_ano = (ultimo_ano_df['Lucro_Liquido'] / ultimo_ano_df['Receita_Liquida']) if ultimo_ano_df.get('Receita_Liquida', 0) > 0 else 0
            
            col1, col2 = st.columns(2)
            col1.metric("ROE (Return on Equity)", f"{roe_ultimo_ano:.2%}")
            col2.metric("Margem Líquida", f"{margem_liquida_ultimo_ano:.2%}")

            st.markdown("---")

            # --- NOVA SEÇÃO: ANÁLISE DUPONT ---
            st.subheader("Análise DuPont (Decomposição do ROE)")
            st.info("A Análise DuPont decompõe o ROE em três fatores: Lucratividade (Margem Líquida), Eficiência no uso de ativos (Giro dos Ativos) e Alavancagem Financeira.")

            # 1. Calcular os componentes do DuPont para todos os anos
            df_dupont = metricas_empresa.copy()
            df_dupont = df_dupont.sort_values(by="Ano") # Ordena do mais antigo para o mais novo para o gráfico

            df_dupont['Margem_Liquida'] = (df_dupont['Lucro_Liquido'] / df_dupont['Receita_Liquida']).where(df_dupont['Receita_Liquida'] != 0, 0)
            df_dupont['Giro_Ativos'] = (df_dupont['Receita_Liquida'] / df_dupont['Ativos_Totais']).where(df_dupont['Ativos_Totais'] != 0, 0)
            df_dupont['Alavancagem_Financeira'] = (df_dupont['Ativos_Totais'] / df_dupont['Patrimonio_Liquido']).where(df_dupont['Patrimonio_Liquido'] != 0, 0)

            # 2. Exibir os componentes do último ano
            st.markdown("##### Componentes do Último Ano Fiscal")
            ultimo_ano_dupont = df_dupont.iloc[-1]
            col_dupont1, col_dupont2, col_dupont3 = st.columns(3)
            col_dupont1.metric("Margem Líquida", f"{ultimo_ano_dupont['Margem_Liquida']:.2%}")
            col_dupont2.metric("Giro dos Ativos", f"{ultimo_ano_dupont['Giro_Ativos']:.2f}x")
            col_dupont3.metric("Alavancagem Financeira", f"{ultimo_ano_dupont['Alavancagem_Financeira']:.2f}x")

            # 3. Exibir gráficos históricos dos componentes
            st.markdown("##### Evolução Histórica dos Componentes")
            
            col_grafico1, col_grafico2, col_grafico3 = st.columns(3)
            with col_grafico1:
                fig_margem = px.line(df_dupont, x='Ano', y='Margem_Liquida', title='Margem Líquida', markers=True)
                fig_margem.update_layout(yaxis_tickformat=".1%")
                st.plotly_chart(fig_margem, use_container_width=True)
            with col_grafico2:
                fig_giro = px.line(df_dupont, x='Ano', y='Giro_Ativos', title='Giro dos Ativos', markers=True)
                st.plotly_chart(fig_giro, use_container_width=True)
            with col_grafico3:
                fig_alavancagem = px.line(df_dupont, x='Ano', y='Alavancagem_Financeira', title='Alavancagem Financeira', markers=True)
                st.plotly_chart(fig_alavancagem, use_container_width=True)

        else:
            st.warning("Não há dados financeiros anuais disponíveis para esta empresa.")
            
    # --- ABA 3: ANÁLISE DE DÍVIDA ---
    with tab3:
        st.subheader("Perfil da Dívida e Métricas de Crédito")
        if ultimo_ano_df is not None:
            # 1. Calcular métricas de alavancagem e cobertura
            ebit = ultimo_ano_df.get('EBIT', 0)
            divida_lp = ultimo_ano_df.get('Divida_Longo_Prazo', 0)
            caixa = ultimo_ano_df.get('Caixa', 0)
            despesa_juros = ultimo_ano_df.get('Despesa_Juros', 0)
            
            divida_liquida = divida_lp - caixa
            
            alavancagem = (divida_liquida / ebit) if ebit > 0 else 0
            # Usamos abs(despesa_juros) pois ela geralmente é um valor negativo no DRE
            icr = (ebit / abs(despesa_juros)) if despesa_juros != 0 else 0
            
            col1, col2 = st.columns(2)
            col1.metric("Dívida Líquida / EBIT", f"{alavancagem:.2f}x", help="Métrica de alavancagem que mostra quantos anos de EBIT seriam necessários para pagar a dívida líquida.")
            col2.metric("Índice de Cobertura de Juros (ICR)", f"{icr:.2f}x", help="Mede quantas vezes o lucro operacional (EBIT) cobre as despesas com juros. Valores mais altos indicam maior segurança para credores.")

            # 2. Gráfico de Perfil de Vencimento da Dívida
            st.markdown("---")
            st.markdown("##### Cronograma de Vencimento da Dívida")
            # Filtra os bonds pelo ticker, não mais pelo ID
            bonds_da_empresa = df_bonds[df_bonds['Ticker'] == ticker_selecionado].copy()

            if not bonds_da_empresa.empty:
                bonds_da_empresa['Ano_Vencimento'] = pd.to_datetime(bonds_da_empresa['Vencimento'], dayfirst=True, errors='coerce').dt.year
                perfil_divida = bonds_da_empresa.groupby('Ano_Vencimento')['Valor_Emissao_MM'].sum().reset_index()
                
                fig_divida = px.bar(perfil_divida, x='Ano_Vencimento', y='Valor_Emissao_MM', 
                                    title='Valor da Dívida a Vencer por Ano (em Milhões)',
                                    labels={'Ano_Vencimento': 'Ano de Vencimento', 'Valor_Emissao_MM': 'Valor a Vencer (MM)'})
                st.plotly_chart(fig_divida, use_container_width=True)

                # 3. Análise Detalhada por Título
                st.markdown("---")
                st.markdown("##### Análise Detalhada por Título")
                for index, bond in bonds_da_empresa.iterrows():
                    with st.expander(f"**{bond['Nome_Bond']}** - Vencimento: {bond['Vencimento']}"):
                        # O resto desta seção de YTM continua igual
                        data_vencimento = pd.to_datetime(bond['Vencimento'], dayfirst=True, errors='coerce')
                        if pd.notna(data_vencimento):
                            anos_vencimento = (data_vencimento - datetime.now()).days / 365.25

                            ytm = calcular_ytm(
                                preco_atual=float(bond['Preco_Atual']), valor_face=100,
                                cupom_anual=float(bond['Cupom_Anual']), anos_vencimento=anos_vencimento,
                                pagamentos_anuais=int(bond['Pagamentos_Anuais'])
                            )

                            col_bond1, col_bond2, col_bond3, col_bond4 = st.columns(4)
                            col_bond1.metric("Preço Atual", f"${float(bond['Preco_Atual']):.2f}")
                            col_bond2.metric("Cupom", f"{float(bond['Cupom_Anual']):.3%}")
                            col_bond3.metric("Rating", bond['Rating'])
                            col_bond4.metric("Yield to Maturity (YTM)", f"{ytm:.3%}", help="Retorno anualizado esperado se o título for mantido até o vencimento.")
            else:
                st.info("Nenhum título de dívida cadastrado para esta empresa.")
        else:
            st.warning("Não há dados financeiros para analisar a dívida.")
            
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


    with tab5:
            st.subheader(f"Histórico de P/L (Preço/Lucro) dos Últimos 5 Anos")
            
            with st.spinner("Calculando histórico de valuation... Este processo pode levar um momento."):
                if not price_history.empty and not metricas_trimestrais_empresa.empty and market_data:
                    try:
                        # 1. Preparar dados de lucro trimestral
                        df_lucro = metricas_trimestrais_empresa[['Data_Reporte', 'Lucro_Liquido']].copy()
                        df_lucro['Data_Reporte'] = pd.to_datetime(df_lucro['Data_Reporte'])
                        df_lucro = df_lucro.sort_values(by='Data_Reporte')
                        
                        # 2. Calcular o Lucro dos Últimos 12 Meses (TTM)
                        df_lucro['Lucro_TTM'] = df_lucro['Lucro_Liquido'].rolling(window=4).sum()
                        df_lucro.dropna(inplace=True) # Remove as primeiras linhas que não têm 4 trimestres para somar
    
                        # 3. Preparar dados de preço e market cap diários
                        df_preco = price_history[['Close']].copy()
                        df_preco.index = df_preco.index.tz_convert(None) # Remove timezone para o merge
                        
                        # Usa o número de ações atual para estimar o market cap histórico (uma aproximação comum)
                        shares_outstanding = market_data.get('sharesOutstanding', 0)
                        if shares_outstanding > 0:
                            df_preco['MarketCap_Hist'] = df_preco['Close'] * shares_outstanding
                        else:
                            st.warning("Número de ações não disponível. Não é possível calcular P/L histórico.")
                            st.stop()
                        
                        # 4. Juntar dados diários com trimestrais
                        df_pl = pd.merge_asof(df_preco.sort_index(), df_lucro.sort_values(by='Data_Reporte'), 
                                              left_index=True, right_on='Data_Reporte', direction='backward')
                        
                        # 5. Calcular o P/L Histórico
                        df_pl['PL_Historico'] = (df_pl['MarketCap_Hist'] / df_pl['Lucro_TTM']).where(df_pl['Lucro_TTM'] > 0)
                        
                        # 6. Calcular as linhas de referência
                        pl_medio = df_pl['PL_Historico'].mean()
                        pl_max = df_pl['PL_Historico'].max()
                        pl_min = df_pl['PL_Historico'].min()
                        pl_atual = df_pl['PL_Historico'].iloc[-1]
                        
                        st.markdown("##### Análise do P/L Atual vs. Média Histórica")
                        col1, col2, col3 = st.columns(3)
                        col1.metric("P/L Atual", f"{pl_atual:.2f}x")
                        col2.metric("Média de 5 Anos", f"{pl_medio:.2f}x")
                        delta_media = ((pl_atual - pl_medio) / pl_medio) if pl_medio != 0 else 0
                        col3.metric("Posição vs. Média", f"{delta_media:.1%}", help="Indica se o P/L atual está acima ou abaixo da sua média histórica de 5 anos.")
    
                        # 7. Plotar o gráfico
                        fig_pl_hist = px.line(df_pl, x='Data_Reporte', y='PL_Historico', title=f'P/L Histórico de {ticker_selecionado}')
                        fig_pl_hist.add_hline(y=pl_medio, line_dash="dot", line_color="green", annotation_text=f"Média: {pl_medio:.2f}x")
                        fig_pl_hist.add_hline(y=pl_max, line_dash="dot", line_color="red", annotation_text=f"Máxima: {pl_max:.2f}x")
                        fig_pl_hist.add_hline(y=pl_min, line_dash="dot", line_color="red", annotation_text=f"Mínima: {pl_min:.2f}x")
                        
                        st.plotly_chart(fig_pl_hist, use_container_width=True)
    
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao gerar a análise histórica: {e}")
                else:
                    st.warning("Não há dados trimestrais ou de preço suficientes para gerar a análise de valuation histórico.")
else:
    st.info("Selecione uma empresa na barra lateral para começar a análise.")
