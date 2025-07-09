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
    """Autentica com o Google Sheets."""
    print("Autenticando com Google Sheets...")
    creds_json_str = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS")
    if not creds_json_str:
        raise ValueError("Credenciais não encontradas.")
    gc = gspread.service_account_from_dict(json.loads(creds_json_str))
    print("Autenticação OK.")
    return gc

def find_column_by_priority(df, keys):
    """Procura por uma coluna em uma lista de chaves prioritárias."""
    for key in keys:
        if key in df.columns:
            return df[key]
    return pd.Series(0, index=df.index)

def extrair_e_transformar(tickers):
    """Função única que extrai dados do yfinance e os transforma."""
    print(f"Iniciando extração para {len(tickers)} tickers...")
    all_perfis, all_anuais, all_trimestrais = [], [], []

    for ticker in tickers:
        try:
            print(f"  Processando {ticker}...")
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Perfil
            all_perfis.append({'Ticker': ticker, 'Pais': info.get('country'), 'Setor_API': info.get('sector'), 'Descricao_Longa': info.get('longBusinessSummary')})

            # Processa tanto anual quanto trimestral
            for period in ['anual', 'trimestral']:
                if period == 'anual':
                    financials = stock.financials
                    balance_sheet = stock.balance_sheet
                    cash_flow = stock.cashflow
                else:
                    financials = stock.quarterly_financials
                    balance_sheet = stock.quarterly_balance_sheet
                    cash_flow = stock.quarterly_cashflow

                if financials.empty or balance_sheet.empty or cash_flow.empty:
                    continue

                # Transforma e combina
                df = pd.concat([financials, balance_sheet, cash_flow]).transpose().reset_index().rename(columns={'index': 'Data_Reporte'})
                df['Ticker'] = ticker

                # CALCULO E BUSCA INTELIGENTE DAS MÉTRICAS
                df['Receita_Liquida'] = find_column_by_priority(df, ['Total Revenue'])
                df['EBIT'] = find_column_by_priority(df, ['Ebit', 'Operating Income'])
                df['Lucro_Liquido'] = find_column_by_priority(df, ['Net Income'])
                df['Despesa_Juros'] = find_column_by_priority(df, ['Interest Expense'])
                df['Ativos_Totais'] = find_column_by_priority(df, ['Total Assets'])
                df['Passivos_Totais'] = find_column_by_priority(df, ['Total Liab', 'Total Liabilities'])
                df['Patrimonio_Liquido'] = df['Ativos_Totais'] - df['Passivos_Totais'] # Cálculo direto
                df['Caixa'] = find_column_by_priority(df, ['Cash And Cash Equivalents', 'Cash'])
                df['Divida_Longo_Prazo'] = find_column_by_priority(df, ['Long Term Debt'])
                df['FCO'] = find_column_by_priority(df, ['Operating Cash Flow', 'Total Cash From Operating Activities'])
                df['CAPEX'] = find_column_by_priority(df, ['Capital Expenditure', 'Change In Fixed Assets And Intangibles', 'Purchase Of Property Plant And Equipment'])
                
                df['Data_Reporte'] = pd.to_datetime(df['Data_Reporte'])

                if period == 'anual':
                    df['Ano'] = df['Data_Reporte'].dt.year
                    all_anuais.append(df)
                else:
                    all_trimestrais.append(df)
        except Exception as e:
            print(f"  ERRO GERAL ao processar {ticker}: {e}")
            continue
    
    print("Extração concluída.")
    return pd.DataFrame(all_perfis), pd.concat(all_anuais, ignore_index=True), pd.concat(all_trimestrais, ignore_index=True)

def carregar_para_gsheets(gc, df, nome_aba):
    """Carrega um DataFrame para uma aba específica."""
    print(f"Carregando dados para '{nome_aba}'...")
    try:
        ss = gc.open(NOME_PLANILHA)
        ws = ss.worksheet(nome_aba)
        ws.clear()
        # Garante que as colunas com dados sejam escritas primeiro
        df_sem_nan = df.dropna(axis=1, how='all')
        ws.update([df_sem_nan.columns.values.tolist()] + df_sem_nan.values.tolist(), value_input_option='USER_ENTERED')
        print(f"Sucesso. {len(df)} linhas carregadas.")
    except Exception as e:
        print(f"ERRO ao carregar para '{nome_aba}': {e}")

def main():
    """Função principal que orquestra o processo de ETL."""
    print("--- INICIANDO PROCESSO DE ETL DEFINITIVO ---")
    gc = autenticar_gspread()
    
    master_ws = gc.open(NOME_PLANILHA).worksheet(ABA_MASTER)
    tickers = [row['Ticker'] for row in master_ws.get_all_records() if row.get('Ticker')]
    
    if not tickers:
        print("Nenhum ticker encontrado na aba master.")
        return
        
    df_perfis, df_anuais, df_trimestrais = extrair_e_transformar(tickers)

    colunas_finais_anuais = ['Ticker', 'Ano', 'Receita_Liquida', 'EBIT', 'Lucro_Liquido', 'Ativos_Totais', 'Passivos_Totais', 'Patrimonio_Liquido', 'Caixa', 'Divida_Longo_Prazo', 'Despesa_Juros', 'FCO', 'CAPEX']
    colunas_finais_trimestrais = ['Ticker', 'Data_Reporte', 'Receita_Liquida', 'EBIT', 'Lucro_Liquido', 'Ativos_Totais', 'Passivos_Totais', 'Patrimonio_Liquido', 'Caixa', 'Divida_Longo_Prazo', 'Despesa_Juros', 'FCO', 'CAPEX']

    carregar_para_gsheets(gc, df_perfis, ABA_PERFIS)
    carregar_para_gsheets(gc, df_anuais.reindex(columns=colunas_finais_anuais).fillna(0), ABA_METRICAS_ANUAIS)
    carregar_para_gsheets(gc, df_trimestrais.reindex(columns=colunas_finais_trimestrais).fillna(0), ABA_METRICAS_TRIMESTRAIS)
    
    print("--- PROCESSO DE ETL CONCLUÍDO ---")

if __name__ == "__main__":
    main()
