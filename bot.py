import requests
import pandas as pd
import yfinance as yf
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURAÇÕES DO BOT
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604' # Confirme se está correto

MEUS_PAPEIS = [
    {"ticker": "CMIG4", "nome": "CEMIG"},
    {"ticker": "SAPR11", "nome": "SANEPAR"},
    {"ticker": "ISAE4", "nome": "ISA ENERGIA BRASIL"},
    {"ticker": "ABCB4", "nome": "BANCO ABC BRASIL"},
    {"ticker": "LOGG3", "nome": "LOG COMMERCIAL PROPERTIES"},
    {"ticker": "BBAS3", "nome": "BANCO DO BRASIL"},
    {"ticker": "FIQE3", "nome": "UNIFIQUE"},
    {"ticker": "GGBR4", "nome": "GERDAU"},
    {"ticker": "VBBR3", "nome": "VIBRA ENERGIA"},
    {"ticker": "SAUD3", "nome": "BRADSAÚDE"},
    {"ticker": "DEXP3", "nome": "DEXCO"},
]

def enviar_telegram(mensagem, ticker=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if ticker:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": f"📈 Status Invest {ticker}", "url": f"https://statusinvest.com.br/acoes/{ticker.lower()}"}
            ]]
        }
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Telegram status para {ticker or 'Geral'}: {r.status_code} - Resposta: {r.text}")
    except Exception as e:
        print(f"Erro no envio do Telegram: {e}")

def executar_radar_yf():
    mes_ano = datetime.now().strftime("%b/%y").upper()
    total_alertas = 0
    
    print("Iniciando varredura via yfinance...")
    enviar_telegram(f"🤖 *Radar IDIV | {mes_ano}*\nVarredura via YFinance iniciada na nuvem.")

    for papel in MEUS_PAPEIS:
        ticker_base = papel["ticker"]
        nome = papel["nome"]
        ticker_yf = f"{ticker_base}.SA"
        
        print(f"Consultando yfinance para: {ticker_yf}")
        
        try:
            acao = yf.Ticker(ticker_yf)
            dividendos = acao.dividends
            
            print(f"Total de registros de dividendos encontrados para {ticker_base}: {len(dividendos)}")
            
            if not dividendos.empty:
                # Pega a última linha (o provento mais recente registrado)
                ultima_data = dividendos.index[-1].strftime('%d/%m/%Y')
                ultimo_valor = dividendos.iloc[-1]
                
                print(f"Último provento de {ticker_base}: Data {ultima_data}, Valor {ultimo_valor}")
                
                msg = (
                    f"#{ticker_base} | {mes_ano} | {nome}\n\n"
                    f"💰 *PROVENTO RECENTE (YFinance):*\n"
                    f"💵 Valor: R$ {ultimo_valor:.4f}\n"
                    f"📅 Data Base (COM): {ultima_data}"
                )
                enviar_telegram(msg, ticker_base)
                total_alertas += 1
            else:
                print(f"Nenhum dividendo retornado pelo yfinance para {ticker_base}")
                
        except Exception as e:
            print(f"Erro crítico ao processar {ticker_base}: {e}")
            
    enviar_telegram(f"✅ *Varredura Concluída!*\nTotal de alertas enviados: {total_alertas}")
    print(f"Varredura concluída. {total_alertas} avisos enviados.")

if __name__ == "__main__":
    executar_radar_yf()
