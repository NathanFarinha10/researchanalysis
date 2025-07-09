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

def autenticar_gspread():
    """Autentica com o Google Sheets usando as credenciais."""
    print("Iniciando autenticação com o Google Sheets...")
    # As credenciais são carregadas de uma variável de ambiente no GitHub Actions
    creds_json_str = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS")
    if not creds_json_str:
        raise ValueError("Credenciais GCP_SERVICE_ACCOUNT_CREDENTIALS não encontradas nas variáveis de ambiente.")
    
    creds_dict = json.loads(creds_json_str)
    gc = gspread.service_account_from_dict(creds_dict)
    print("Autenticação bem-sucedida.")
    return gc

def extrair_dados_yfinance(tickers):
    """Extrai dados de perfil e financeiros do yfinance para uma lista de tickers."""
    print(f"Iniciando extração de dados do yfinance para {len(tickers)} tickers...")
    dados_perfis = []
    dados_metricas = []
    
    for ticker_str in tickers:
        try:
            print(f"  Processando ticker: {ticker_str}...")
            stock = yf.Ticker(ticker_str)
            
            # --- Extração de Perfil ---
            info = stock.info
            dados_perfis.append({
                'Ticker': ticker_str,
                'Pais': info.get('country', 'N/A'),
                'Setor_API': info.get('sector', 'N/A'),
                'Industria_API': info.get('industry', 'N/A'),
                'Descricao_Longa': info.get('longBusinessSummary', 'N/A'),
                'Website': info.get('website', 'N/A'),
            })

            # --- Extração de Métricas Anuais ---
            financials = stock.financials.transpose().reset_index()
            balance_sheet = stock.balance_sheet.transpose().reset_index()
            cash_flow = stock.cashflow.transpose().reset_index()
            
            financials.rename(columns={'index': 'Ano'}, inplace=True)
            financials['Ano'] = pd.to_datetime(financials['Ano']).dt.year
            
            # Combina DRE, Balanço e Fluxo de Caixa
            metricas = pd.merge(financials, balance_sheet, on='index', how='left')
            metricas = pd.merge(metricas, cash_flow, on='index', how='left')
            metricas['Ticker'] = ticker_str
            dados_metricas.append(metricas)
            
        except Exception as e:
            print(f"  ERRO ao processar {ticker_str}: {e}")
            continue
            
    print("Extração de dados do yfinance concluída.")
    return dados_perfis, pd.concat(dados_metricas, ignore_index=True)

def transformar_dados(df_perfis, df_metricas):
    """Padroniza e limpa os DataFrames extraídos."""
    print("Iniciando transformação dos dados...")
    
    # --- Transformação de Perfis ---
    df_perfis_final = pd.DataFrame(df_perfis)
    df_perfis_final['Data_Ultima_Atualizacao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Transformação de Métricas ---
    mapeamento_colunas = {
        'Total Revenue': 'Receita_Liquida', 'Ebit': 'EBIT', 'Net Income': 'Lucro_Liquido',
        'Total Assets': 'Ativos_Totais', 'Total Liab': 'Passivos_Totais', 
        'Total Stockholder Equity': 'Patrimonio_Liquido', 'Total Current Assets': 'Ativos_Circulantes',
        'Total Current Liabilities': 'Passivos_Circulantes','Long Term Debt': 'Divida_Longo_Prazo',
        'Total Cash': 'Caixa', 'Operating Cash Flow': 'FCO', 'Investing Cash Flow': 'FCI',
        'Financing Cash Flow': 'FCF', 'Capital Expenditures': 'CAPEX', 'Working Capital': 'Capital_de_Giro'
    }
    
    df_metricas_renomeado = df_metricas.rename(columns=mapeamento_colunas)
    
    colunas_finais = [
        'Ticker', 'Ano', 'Receita_Liquida', 'EBIT', 'Lucro_Liquido', 'Ativos_Totais', 
        'Passivos_Totais', 'Patrimonio_Liquido', 'Caixa', 'Divida_Longo_Prazo', 'FCO', 
        'FCI', 'FCF', 'CAPEX', 'Capital_de_Giro'
    ]
    
    # Adiciona colunas faltantes com valor 0 para garantir consistência
    for col in colunas_finais:
        if col not in df_metricas_renomeado.columns:
            df_metricas_renomeado[col] = 0
            
    df_metricas_final = df_metricas_renomeado[colunas_finais].fillna(0)
    df_metricas_final['Data_Ultima_Atualizacao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("Transformação dos dados concluída.")
    return df_perfis_final, df_metricas_final

def carregar_dados_para_gsheets(gc, df, nome_aba):
    """Carrega um DataFrame para uma aba específica da planilha, limpando-a antes."""
    print(f"Iniciando carregamento para a aba '{nome_aba}'...")
    try:
        spreadsheet = gc.open(NOME_PLANILHA)
        worksheet = spreadsheet.worksheet(nome_aba)
        worksheet.clear()
        # Converte o DataFrame para lista de listas, incluindo o cabeçalho
        dados_para_escrever = [df.columns.values.tolist()] + df.values.tolist()
        worksheet.update('A1', dados_para_escrever, value_input_option='USER_ENTERED')
        print(f"Sucesso! {len(df)} linhas carregadas em '{nome_aba}'.")
    except Exception as e:
        print(f"ERRO ao carregar dados para '{nome_aba}': {e}")

def main():
    """Função principal que orquestra o processo de ETL."""
    print("--- INICIANDO PROCESSO DE ETL ---")
    
    # 1. Autenticação
    gc = autenticar_gspread()
    
    # 2. Extração (parte 1) - Leitura da lista de tickers
    spreadsheet = gc.open(NOME_PLANILHA)
    worksheet_master = spreadsheet.worksheet(ABA_MASTER)
    tickers_para_buscar = [row['Ticker'] for row in worksheet_master.get_all_records() if row['Ticker']]
    
    if not tickers_para_buscar:
        print("Nenhum ticker encontrado na aba master. Encerrando o processo.")
        return
        
    # 2. Extração (parte 2) - Busca no yfinance
    df_perfis_raw, df_metricas_raw = extrair_dados_yfinance(tickers_para_buscar)
    
    # 3. Transformação
    df_perfis_final, df_metricas_final = transformar_dados(df_perfis_raw, df_metricas_raw)
    
    # 4. Carregamento
    carregar_dados_para_gsheets(gc, df_perfis_final, ABA_PERFIS)
    carregar_dados_para_gsheets(gc, df_metricas_final, ABA_METRICAS_ANUAIS)
    
    print("--- PROCESSO DE ETL CONCLUÍDO ---")

if __name__ == "__main__":
    main()
