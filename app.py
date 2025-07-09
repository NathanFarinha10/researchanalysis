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
        
        # Converte colunas para numérico, ignorando as que devem ser texto.
        cols_to_ignore = ['Ticker', 'Nome_Empresa', 'Setor_Manual', 'Pais', 'Website', 'Descricao_Longa', 'Data_Reporte', 'Data_Ultima_Atualizacao', 'Nome_Bond', 'Rating', 'Vencimento']
        cols_to_numeric = [col for col in df.columns if col not in cols_to_ignore]
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
        history = stock.history(period="5y")
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

st.sidebar.header("Premissas para o DCF")
taxa_crescimento_5a = st.sidebar.slider("Taxa de Crescimento do FCF (5 anos)", 0.0, 0.20, 0.05, format="%.2f")
taxa_perpetuidade = st.sidebar.slider("Taxa de Crescimento na Perpetuidade", 0.0, 0.05, 0.02, format="%.2f")
wacc = st.sidebar.slider("WACC (Taxa de Desconto)", 0.05, 0.25, 0.10, format="%.2f")

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
    tab_list = ["📊 Resumo", "📈 Análise Financeira", "债券 Análise de Dívida", "👥 Comparáveis", "⏳ Valuation Histórico", "💰 Valuation (DCF)"]
    tabs = st.tabs(tab_list)

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
        peers = df_empresas_master[df_empresas_master['Setor_Manual'] == info_empresa['Setor_Manual']]
        
        with st.spinner("Buscando dados de mercado para as empresas do setor..."):
            comparables_data = []
            for index, peer in peers.iterrows():
                peer_ticker = peer['Ticker']
                peer_market_data = get_yfinance_data(peer_ticker)[0]
                
                if not peer_market_data or not peer_market_data.get('marketCap'):
                    continue

                peer_financials = df_metricas_anuais[df_metricas_anuais['Ticker'] == peer_ticker].sort_values(by="Ano", ascending=False)
                if peer_financials.empty: continue

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
                
                comparables_data.append({'Empresa': peer['Nome_Empresa'], 'Ticker': peer_ticker, 'P/L': p_l, 'P/VP': p_vp, 'EV/EBIT': ev_ebit})

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

    # --- ABA 5: VALUATION HISTÓRICO ---
    with tab5:
        st.subheader(f"Histórico de P/L (Preço/Lucro) dos Últimos 5 Anos")
        with st.spinner("Calculando histórico de valuation..."):
            if not price_history.empty and not metricas_trimestrais_empresa.empty and market_data:
                try:
                    df_lucro = metricas_trimestrais_empresa[['Data_Reporte', 'Lucro_Liquido']].copy()
                    df_lucro['Data_Reporte'] = pd.to_datetime(df_lucro['Data_Reporte'])
                    df_lucro = df_lucro.sort_values(by='Data_Reporte')
                    
                    df_lucro['Lucro_TTM'] = df_lucro['Lucro_Liquido'].rolling(window=4).sum()
                    df_lucro.dropna(inplace=True)

                    df_preco = price_history[['Close']].copy()
                    df_preco.index = df_preco.index.tz_localize(None) # Remove timezone
                    
                    shares_outstanding = market_data.get('sharesOutstanding', 0)
                    if shares_outstanding > 0:
                        df_preco['MarketCap_Hist'] = df_preco['Close'] * shares_outstanding
                        
                        df_pl = pd.merge_asof(df_preco.sort_index(), df_lucro, left_index=True, right_on='Data_Reporte', direction='backward')
                        df_pl['PL_Historico'] = (df_pl['MarketCap_Hist'] / df_pl['Lucro_TTM']).where(df_pl['Lucro_TTM'] > 0)
                        
                        pl_medio = df_pl['PL_Historico'].mean()
                        pl_atual = df_pl['PL_Historico'].iloc[-1]
                        
                        col1, col2, col3 = st.columns(3)
                        col1.metric("P/L Atual", f"{pl_atual:.2f}x")
                        col2.metric("Média de 5 Anos", f"{pl_medio:.2f}x")
                        delta_media = ((pl_atual - pl_medio) / pl_medio) if pl_medio != 0 else 0
                        col3.metric("Posição vs. Média", f"{delta_media:.1%}")

                        fig_pl_hist = px.line(df_pl, x='Data_Reporte', y='PL_Historico', title=f'P/L Histórico de {ticker_selecionado}')
                        fig_pl_hist.add_hline(y=pl_medio, line_dash="dot", line_color="green", annotation_text=f"Média: {pl_medio:.2f}x")
                        st.plotly_chart(fig_pl_hist, use_container_width=True)
                    else:
                        st.warning("Número de ações não disponível (sharesOutstanding). Não é possível calcular P/L histórico.")
                except Exception as e:
                    st.error(f"Ocorreu um erro ao gerar a análise histórica: {e}")
            else:
                st.warning("Não há dados trimestrais ou de preço suficientes para gerar a análise de valuation histórico.")

else:
    st.info("Selecione uma empresa na barra lateral para começar a análise.")


    with tabs[5]:
            st.subheader("Modelo de Fluxo de Caixa Descontado (DCF Simplificado)")
            
            if ultimo_ano_df is not None and market_data:
                # 1. Pega os dados necessários
                fco = ultimo_ano_df.get('FCO', 0)
                capex = ultimo_ano_df.get('CAPEX', 0)
                fcf_inicial = fco + capex # Capex é negativo, então somamos
                
                divida_total = market_data.get('totalDebt', 0)
                caixa = market_data.get('totalCash', 0)
                divida_liquida = divida_total - caixa
                
                acoes_em_circulacao = market_data.get('sharesOutstanding', 0)
                preco_atual = market_data.get('currentPrice', 0)
    
                if fcf_inicial > 0 and acoes_em_circulacao > 0:
                    # 2. Projeta o FCF para os próximos 5 anos
                    fcf_projetado = []
                    for i in range(1, 6):
                        fcf_projetado.append(fcf_inicial * ((1 + taxa_crescimento_5a) ** i))
                    
                    # 3. Calcula o Valor Terminal
                    ultimo_fcf_projetado = fcf_projetado[-1]
                    valor_terminal = (ultimo_fcf_projetado * (1 + taxa_perpetuidade)) / (wacc - taxa_perpetuidade)
                    
                    # 4. Desconta todos os fluxos a valor presente
                    fcf_descontado = []
                    for i, fcf in enumerate(fcf_projetado):
                        fcf_descontado.append(fcf / ((1 + wacc) ** (i + 1)))
                    
                    valor_terminal_descontado = valor_terminal / ((1 + wacc) ** 5)
                    
                    # 5. Calcula o Preço-Alvo
                    enterprise_value = sum(fcf_descontado) + valor_terminal_descontado
                    equity_value = enterprise_value - divida_liquida
                    preco_alvo = equity_value / acoes_em_circulacao
                    upside = ((preco_alvo / preco_atual) - 1) if preco_atual > 0 else 0
                    
                    # 6. Exibe os Resultados
                    st.markdown("##### Resultado do Valuation")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Preço-Alvo (DCF)", f"R$ {preco_alvo:.2f}")
                    col2.metric("Preço Atual", f"R$ {preco_atual:.2f}")
                    col3.metric("Potencial de Upside", f"{upside:.2%}")
                    
                    st.markdown("---")
                    st.markdown("##### Detalhamento do Cálculo")
                    
                    # Cria um DataFrame para visualização
                    df_projecao = pd.DataFrame({
                        'Ano': [f'Ano {i}' for i in range(1, 6)],
                        'FCF Projetado': fcf_projetado,
                        'FCF Descontado': fcf_descontado
                    })
                    st.dataframe(df_projecao.style.format("R$ {:,.2f}"))
                    
                    st.write(f"**Valor Terminal (após o Ano 5):** R$ {valor_terminal:,.2f}")
                    st.write(f"**Valor Terminal Descontado:** R$ {valor_terminal_descontado:,.2f}")
                    st.write(f"**Enterprise Value (Soma dos FCFs):** R$ {enterprise_value:,.2f}")
                    st.write(f"**Dívida Líquida:** R$ {divida_liquida:,.2f}")
                    st.write(f"**Equity Value (Valor para o Acionista):** R$ {equity_value:,.2f}")
    
                else:
                    st.warning("Não foi possível realizar o cálculo de DCF. Verifique se a empresa possui Fluxo de Caixa Livre positivo e se os dados de mercado estão disponíveis.")
            else:
                st.warning("Dados financeiros ou de mercado insuficientes para o cálculo.")
    
        else:
            st.info("Selecione uma empresa na barra lateral para começar a análise.")

