"""
🤖 RADAR IDIV - Bot de Dividendos
Fonte: Yahoo Finance (yfinance)
"""

import yfinance as yf
import requests
from datetime import datetime
import logging

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604'

MEUS_PAPEIS = [
    {"ticker": "CMIG4", "nome": "CEMIG"},
    {"ticker": "BBAS3", "nome": "BANCO DO BRASIL"},
    {"ticker": "SAPR11", "nome": "SANEPAR"},
    {"ticker": "ISAE4", "nome": "ISA ENERGIA"},
    {"ticker": "ABCB4", "nome": "ABC BRASIL"},
    {"ticker": "LOGG3", "nome": "LOG PROPERTIES"},
    {"ticker": "FIQE3", "nome": "UNIFIQUE"},
    {"ticker": "GGBR4", "nome": "GERDAU"},
    {"ticker": "VBBR3", "nome": "VIBRA ENERGIA"},
    {"ticker": "SAUD3", "nome": "BRADSAUDE"},
    {"ticker": "DEXP3", "nome": "DEXCO"},
]

# ==============================================================================
# TELEGRAM
# ==============================================================================
def enviar_telegram(mensagem):
    """Envia mensagem para Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Telegram enviado")
            return True
        logger.warning(f"⚠️ Telegram status: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Erro Telegram: {e}")
    
    return False

# ==============================================================================
# BUSCAR DIVIDENDOS
# ==============================================================================
def buscar_dividendos(ticker):
    """Busca dividendos via Yahoo Finance"""
    logger.info(f"🔍 Buscando: {ticker}")
    
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        dividendos = acao.dividends
        
        if dividendos.empty:
            logger.warning(f"⚠️ Sem dividendos: {ticker}")
            return []
        
        logger.info(f"✅ {len(dividendos)} dividendos: {ticker}")
        
        lista = []
        for data, valor in dividendos.items():
            lista.append({
                "data": data.strftime("%d/%m/%Y"),
                "valor": float(valor)
            })
        
        return lista[-10:]
        
    except Exception as e:
        logger.error(f"❌ Erro {ticker}: {e}")
        return []

# ==============================================================================
# RADAR PRINCIPAL
# ==============================================================================
def main():
    logger.info("="*60)
    logger.info("🤖 RADAR IDIV - Iniciando")
    logger.info("="*60)
    
    mes_ano = datetime.now().strftime("%b/%y").upper()
    enviar_telegram(f"🤖 *Radar IDIV | {mes_ano}*\nVarredura de {len(MEUS_PAPEIS)} ativos...")
    
    total_alertas = 0
    total_encontrados = 0
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        nome = papel["nome"]
        
        dividendos = buscar_dividendos(ticker)
        total_encontrados += len(dividendos)
        
        hoje = datetime.now()
        for div in dividendos:
            try:
                data_div = datetime.strptime(div["data"], "%d/%m/%Y")
                dias_atras = (hoje - data_div).days
                
                if 0 <= dias_atras <= 60:
                    msg = (
                        f"#{ticker} | {mes_ano} | {nome}\n\n"
                        f"💰 *DIVIDENDO*\n"
                        f"💵 *Valor:* R$ {div['valor']:.4f}\n"
                        f"📅 *Data:* {div['data']}\n"
                        f"📊 *Dias atrás:* {dias_atras}"
                    )
                    
                    enviar_telegram(msg)
                    total_alertas += 1
                    logger.info(f"✅ Alerta: {ticker}")
                    
            except Exception as e:
                logger.debug(f"⚠️ Erro: {e}")
    
    logger.info(f"✅ Fim: {total_alertas} alertas / {total_encontrados} encontrados")
    
    if total_alertas == 0:
        enviar_telegram(
            f"ℹ️ *Status:*\n\n"
            f"📊 Ativos: {len(MEUS_PAPEIS)}\n"
            f"🔍 Encontrados: {total_encontrados}\n"
            f"⚠️ Nenhum dividendo nos últimos 60 dias"
        )
    else:
        enviar_telegram(
            f"✅ *Concluído!*\n\n"
            f"📊 Ativos: {len(MEUS_PAPEIS)}\n"
            f"🔍 Total: {total_encontrados}\n"
            f"📣 Alertas: {total_alertas}"
        )

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    main()
