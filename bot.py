import requests
import pandas as pd

# ==============================================================================
# CONFIGURAÇÕES DO BOT (Insira seus dados entre as aspas)
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604'
def enviar_alerta_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro no Telegram: {e}")

def executar_radar():
    print("Iniciando varredura por Ticker...")
    
    # URL dos Fatos Relevantes da CVM (ex: FPE)
    url_cvm = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FPE/DADOS/fpe_cia_aberta_2026.csv"
    
    try:
        tabela_cvm = pd.read_csv(url_cvm, sep=';', encoding='latin1')
        
        # Lista focada nos Tickers principais ou códigos CVM das "vacas leiteiras"
        # Dica: Na CVM o ideal é mapear os tickers ou os nomes oficiais exatos de pregão
        tickers_radar = ['ITSA4', 'BBSE3', 'PETR4', 'TAEE11', 'EGIE3']
        gatilhos_valor = ['RECOMPRA', 'DIVIDENDOS', 'JCP', 'PROVENTOS']
        
        contador = 0
        for index, linha in tabela_cvm.iterrows():
            # Verificamos se a coluna de Ticker/Código bate com o nosso radar
            ticker = str(linha.get('DENOM_SOCIAL', '')).upper() # Ou coluna de código equivalente na base
            assunto = str(linha.get('ASSUNTO', '')).upper()
            
            # Filtro refinado
            if any(t in ticker for t in tickers_radar) and any(g in assunto for g in gatilhos_valor):
                enviar_alerta_telegram(f"🎯 *ALERTA IDIV (Ticker)* \n🏢 *Empresa:* {ticker}\n📄 *Assunto:* {assunto}")
                contador += 1
                
        print(f"Varredura por Ticker concluída. Alertas enviados: {contador}")
        
    except Exception as e:
        print(f"Erro na execução: {e}")

if __name__ == "__main__":
    executar_radar()
