import yfinance as yf
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURAÇÕES DO BOT
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID =  '566929604'

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

def enviar_telegram(mensagem, ticker):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": f"📈 Status Invest {ticker}", "url": f"https://statusinvest.com.br/acoes/{ticker.lower()}"}
            ]]
        }
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro Telegram: {e}")

def executar_radar_yf():
    mes_ano = datetime.now().strftime("%b/%y").upper()
    total_alertas = 0
    
    for papel in MEUS_PAPEIS:
        ticker_base = papel["ticker"]
        nome = papel["nome"]
        
        # No yfinance, ações da B3 exigem o sufixo .SA
        ticker_yf = f"{ticker_base}.SA"
        
        try:
            acao = yf.Ticker(ticker_yf)
            dividendos = acao.dividends
            
            if not dividendos.empty:
                # Pega a última linha (o provento mais recente registrado)
                ultima_data = dividendos.index[-1].strftime('%d/%m/%Y')
                ultimo_valor = dividendos.iloc[-1]
                
                msg = (
                    f"#{ticker_base} | {mes_ano} | {nome}\n\n"
                    f"💰 *PROVENTO RECENTE (YFinance):*\n"
                    f"💵 Valor: R$ {ultimo_valor:.4f}\n"
                    f"📅 Data Base (COM): {ultima_data}"
                )
                enviar_telegram(msg, ticker_base)
                total_alertas += 1
                
        except Exception as e:
            print(f"Erro ao consultar {ticker_base}: {e}")
            
    print(f"Varredura via yfinance concluída. {total_alertas} avisos enviados.")

if __name__ == "__main__":
    executar_radar_yf()
