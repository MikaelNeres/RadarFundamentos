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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro no envio do Telegram: {e}")

def executar_radar_vigentes():
    mes_ano = datetime.now().strftime("%b/%y").upper()
    hoje = datetime.now()
    total_alertas = 0
    
    print("Iniciando varredura de proventos vigentes...")
    enviar_telegram(f"🤖 *Radar IDIV | {mes_ano}*\nVarredura de proventos com Data COM vigente iniciada...")

    for papel in MEUS_PAPEIS:
        ticker_base = papel["ticker"]
        nome = papel["nome"]
        ticker_yf = f"{ticker_base}.SA"
        
        try:
            acao = yf.Ticker(ticker_yf)
            dividendos = acao.dividends
            
            if not dividendos.empty:
                # Converte o índice do yfinance para datetime sem fuso horário para comparação segura
                dividendos.index = pd.to_datetime(dividendos.index).tz_localize(None)
                
                # Filtra apenas proventos cuja Data COM seja de hoje em diante (vigentes)
                proventos_vigentes = dividendos[dividendos.index >= hoje]
                
                for data_com, valor in proventos_vigentes.items():
                    data_com_str = data_com.strftime('%d/%m/%Y')
                    
                    msg = (
                        f"#{ticker_base} | {mes_ano} | {nome}\n\n"
                        f"💰 *PROVENTO COM DATA COM VIGENTE:*\n"
                        f"💵 *Valor Declarado:* R$ {valor:.4f} por ação\n"
                        f"📅 *Data COM:* {data_com_str}"
                    )
                    enviar_telegram(msg, ticker_base)
                    total_alertas += 1
                    
        except Exception as e:
            print(f"Erro ao processar {ticker_base}: {e}")
            
    print(f"Varredura concluída. {total_alertas} proventos vigentes encontrados.")
    if total_alertas == 0:
        enviar_telegram("✅ *Radar IDIV:* Nenhuma nova Data COM vigente mapeada para os ativos monitorados no momento.")

if __name__ == "__main__":
    executar_radar_vigentes()
