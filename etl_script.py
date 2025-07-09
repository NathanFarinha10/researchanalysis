import os
import json
import gspread
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÕES ---
NOME_PLANILHA = "Plataforma_DB_Final"
ABA_MASTER = "empresas_master"
ABA_PERFIS = "perfis_empresas"
ABA_METRICAS_ANUAIS = "metricas_anuais"
ABA_METRICAS_TRIMESTRAIS = "metricas_trimestrais"

def autenticar_gspread():
    """Autentica com o Google Sheets usando as credenciais."""
    print("Iniciando autenticação com o Google Sheets...")
    creds_json_str = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS")
    if not creds_json_str:
        raise ValueError("Credenciais GCP_SERVICE_ACCOUNT_CREDENTIALS não encontradas.")
    creds_dict = json.loads(creds_json_str)
    gc = gspread.service_account_from_dict(creds_dict)
    print("Autenticação bem-sucedida.")
    return gc

def find_capex_column(df_cashflow):
    """Encontra a coluna de CAPEX correta em um DataFrame de fluxo de caixa, usando uma lista de prioridade."""
    # Lista de nomes possíveis para CAPEX, em ordem de preferência
    possible_capex_cols = [
        'Capital Expenditures',
        'Change In Fixed Assets And Intangibles',
        'Purchase Of Property Plant And Equipment',
        'Acquisition Of Property Plant And Equipment'
    ]
    for col in possible_capex_cols:
        if col in df_cashflow.columns:
            print(f"  Coluna de CAPEX encontrada: '{col}'")
            return df_cashflow[col]
    
    print("  Nenhuma coluna de CAPEX explícita encontrada.")
    return pd.Series(0, index=df_cashflow.index) # Retorna uma série de zeros se nada for encontrado

def extrair_dados_yfinance(tickers):
    """Extrai dados de perfil, anuais e trimestrais do yfinance."""
    print(f"Iniciando extração de dados do yfinance para {len(tickers)} tickers...")
    dados_perfis, lista_metricas_anuais, lista_metricas_trimestrais = [], [], []
    
    for ticker_str in tickers:
        try:
            print(f"  Processando ticker: {ticker_str}...")
            stock = yf.Ticker(ticker_str)
            info = stock.info
            
            dados_perfis.append({'Ticker': ticker_str, 'Pais': info.get('country'), 'Setor_API': info.get('sector'), 'Industria_API': info.get('industry'), 'Descricao_Longa': info.get('longBusinessSummary'), 'Website': info.get('website')})

            # --- Processamento Anual ---
            financials_anual = stock.financials.transpose().reset_index()
            balance_sheet_anual = stock.balance_sheet.transpose().reset_index()
            cash_flow_anual = stock.cashflow.transpose().reset_index()
            cash_flow_anual['CAPEX'] = find_capex_column(cash_flow_anual) #<-- LÓGICA INTELIGENTE
            metricas_anuais = pd.merge(financials_anual, balance_sheet_anual, on='index', how='left').merge(cash_flow_anual, on='index', how='left')
            metricas_anuais.rename(columns={'index': 'Data_Reporte'}, inplace=True)
            metricas_anuais['Ticker'] = ticker_str
            lista_metricas_anuais.append(metricas_anuais)

            # --- Processamento Trimestral ---
            financials_trimestral = stock.quarterly_financials.transpose().reset_index()
            balance_sheet_trimestral = stock.quarterly_balance_sheet.transpose().reset_index()
            cash_flow_trimestral = stock.quarterly_cashflow.transpose().reset_index()
            cash_flow_trimestral['CAPEX'] = find_capex_column(cash_flow_trimestral) #<-- LÓGICA INTELIGENTE
            metricas_trimestrais = pd.merge(financials_trimestral, balance_sheet_trimestral, on='index', how='left').merge(cash_flow_trimestral, on='index', how='left')
            metricas_trimestrais.rename(columns={'index': 'Data_Reporte'}, inplace=True)
            metricas_trimestrais['Ticker'] = ticker_str
            lista_metricas_trimestrais.append(metricas_trimestrais)
            
        except Exception as e:
            print(f"  ERRO ao processar {ticker_str}: {e}")
            continue
            
    print("Extração de dados do yfinance concluída.")
    return pd.DataFrame(dados_perfis), pd.concat(lista_metricas_anuais, ignore_index=True), pd.concat(lista_metricas_trimestrais, ignore_index=True)

def transformar_metricas(df_metricas, eh_anual=True):
    """Padroniza e limpa um DataFrame de métricas (anual ou trimestral)."""
    mapeamento_colunas = {
        'Total Revenue': 'Receita_Liquida', 'Ebit': 'EBIT', 'Operating Income': 'EBIT', 'Net Income': 'Lucro_Liquido',
        'Interest Expense': 'Despesa_Juros', 'Interest Expense Non Operating': 'Despesa_Juros', 'Total Assets': 'Ativos_Totais',
        'Total Liab': 'Passivos_Totais', 'Total Liabilities': 'Passivos_Totais', 'Total Stockholder Equity': 'Patrimonio_Liquido',
        'Stockholders Equity': 'Patrimonio_Liquido', 'Shareholders Equity': 'Patrimonio_Liquido', 'Total Current Assets': 'Ativos_Circulantes',
        'Total Current Liabilities': 'Passivos_Circulantes', 'Long Term Debt': 'Divida_Longo_Prazo', 'Total Cash': 'Caixa',
        'Cash': 'Caixa', 'Cash And Cash Equivalents': 'Caixa', 'Working Capital': 'Capital_de_Giro', 'Operating Cash Flow': 'FCO',
        'Total Cash From Operating Activities': 'FCO', 'Investing Cash Flow': 'FCI', 'Total Cashflows From Investing Activities': 'FCI',
        'Financing Cash Flow': 'FCF', 'Total Cash From Financing Activities': 'FCF'
        # CAPEX foi removido daqui pois agora é tratado diretamente na extração
    }
    df_renomeado = df_metricas.rename(columns=mapeamento_colunas).loc[:,~df_metricas.rename(columns=mapeamento_colunas).columns.duplicated()]
    df_renomeado['Data_Reporte'] = pd.to_datetime(df_renomeado['Data_Reporte']).dt.strftime('%Y-%m-%d')

    colunas_base = ['Ticker', 'Receita_Liquida', 'EBIT', 'Lucro_Liquido', 'Ativos_Totais', 'Passivos_Totais', 'Patrimonio_Liquido', 'Caixa', 'Divida_Longo_Prazo', 'Despesa_Juros', 'FCO', 'FCI', 'FCF', 'CAPEX', 'Capital_de_Giro']
    if eh_anual:
        df_renomeado['Ano'] = pd.to_datetime(df_renomeado['Data_Reporte']).dt.year
        colunas_finais = ['Ticker', 'Ano'] + colunas_base[1:]
    else:
        colunas_finais = ['Ticker', 'Data_Reporte'] + colunas_base[1:]

    for col in colunas_finais:
        if col not in df_renomeado.columns:
            df_renomeado[col] = 0
            
    df_final = df_renomeado[colunas_finais].fillna(0)
    df_final['Data_Ultima_Atualizacao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return df_final

def carregar_dados_para_gsheets(gc, df, nome_aba):
    """Carrega um DataFrame para uma aba específica da planilha."""
    print(f"Iniciando carregamento para a aba '{nome_aba}'...")
    try:
        spreadsheet = gc.open(NOME_PLANILHA)
        worksheet = spreadsheet.worksheet(nome_aba)
        worksheet.clear()
        dados_para_escrever = [df.columns.values.tolist()] + df.values.tolist()
        worksheet.update('A1', dados_para_escrever, value_input_option='USER_ENTERED')
        print(f"Sucesso! {len(df)} linhas carregadas em '{nome_aba}'.")
    except Exception as e:
        print(f"ERRO ao carregar dados para '{nome_aba}': {e}")

def main():
    """Função principal que orquestra o processo de ETL."""
    print("--- INICIANDO PROCESSO DE ETL ---")
    gc = autenticar_gspread()
    worksheet_master = gc.open(NOME_PLANILHA).worksheet(ABA_MASTER)
    tickers_para_buscar = [row['Ticker'] for row in worksheet_master.get_all_records() if row.get('Ticker')]
    
    if not tickers_para_buscar:
        print("Nenhum ticker encontrado na aba master. Encerrando.")
        return
        
    df_perfis_raw, df_metricas_anuais_raw, df_metricas_trimestrais_raw = extrair_dados_yfinance(tickers_para_buscar)
    
    df_perfis_final = pd.DataFrame(df_perfis_raw)
    df_perfis_final['Data_Ultima_Atualizacao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    df_metricas_anuais_final = transformar_metricas(df_metricas_anuais_raw, eh_anual=True)
    df_metricas_trimestrais_final = transformar_metricas(df_metricas_trimestrais_raw, eh_anual=False)
    
    carregar_dados_para_gsheets(gc, df_perfis_final, ABA_PERFIS)
    carregar_dados_para_gsheets(gc, df_metricas_anuais_final, ABA_METRICAS_ANUAIS)
    carregar_dados_para_gsheets(gc, df_metricas_trimestrais_final, ABA_METRICAS_TRIMESTRAIS)
    
    print("--- PROCESSO DE ETL CONCLUÍDO ---")

if __name__ == "__main__":
    main()
