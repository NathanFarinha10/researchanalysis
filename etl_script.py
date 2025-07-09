import yfinance as yf
import pandas as pd

# --- SCRIPT DE INVESTIGAÇÃO DE DADOS ---
# O objetivo deste script é apenas imprimir os nomes das colunas disponíveis no yfinance

def investigar_tickers(tickers):
    """
    Para cada ticker, baixa o fluxo de caixa e imprime os nomes dos itens disponíveis.
    """
    print("--- INICIANDO INVESTIGAÇÃO DE DADOS DO YFINANCE ---")
    
    for ticker_str in tickers:
        try:
            print(f"\n=========================================================")
            print(f"| INVESTIGANDO TICKER: {ticker_str}")
            print(f"=========================================================")
            
            stock = yf.Ticker(ticker_str)
            
            # Pega o demonstrativo de fluxo de caixa (anual)
            cash_flow_anual = stock.cashflow
            
            if not cash_flow_anual.empty:
                print(f"\n--- Itens Disponíveis no Fluxo de Caixa Anual para {ticker_str}: ---")
                # O nome dos itens fica no 'index' do DataFrame não transposto
                for item in cash_flow_anual.index:
                    print(f"- {item}")
            else:
                print(f"Nenhum dado de fluxo de caixa anual encontrado para {ticker_str}.")

        except Exception as e:
            print(f"  ERRO ao processar {ticker_str}: {e}")
            continue
            
    print("\n--- INVESTIGAÇÃO CONCLUÍDA ---")


if __name__ == "__main__":
    # Vamos investigar apenas algumas empresas para manter o log limpo
    tickers_para_investigar = ['PETR4.SA', 'VALE3.SA', 'AAPL', 'MSFT']
    investigar_tickers(tickers_para_investigar)
