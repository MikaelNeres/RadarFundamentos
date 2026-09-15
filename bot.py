"""
🤖 RADAR IDIV - Bot de Dividendos
Fonte: Yahoo Finance (yfinance)
Versão: Com distinção Data COM vs Pagamento
"""

import yfinance as yf
import requests
from datetime import datetime, timedelta
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
    {"ticker": "PETR4", "nome": "PETROBRAS"},
    {"ticker": "VALE3", "nome": "VALE"},
    {"ticker": "BBSE3", "nome": "BB SEGURIDADE"},
    {"ticker": "ITUB4", "nome": "ITAU"},
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
# BUSCAR DIVIDENDOS COM DATAS DETALHADAS
# ==============================================================================
def buscar_dividendos_detalhados(ticker):
    """
    Busca dividendos com Data COM e Data de Pagamento
    Yahoo Finance retorna:
    - dividends.index = Data de Pagamento
    - Precisamos estimar Data COM (geralmente 1-30 dias antes do pagamento)
    """
    logger.info(f"🔍 Buscando dividendos: {ticker}")
    
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        dividendos = acao.dividends
        
        if dividendos.empty:
            logger.warning(f"⚠️ Sem dividendos: {ticker}")
            return []
        
        logger.info(f"✅ {len(dividendos)} dividendos: {ticker}")
        
        lista = []
        for data_pagamento, valor in dividendos.items():
            # Yahoo Finance retorna Data de Pagamento
            # Data COM geralmente é 15-30 dias antes (varia por empresa)
            # Para simplificar, assumimos Data COM = 15 dias antes do pagamento
            
            data_com_estimada = data_pagamento - timedelta(days=15)
            
            lista.append({
                "data_pagamento": data_pagamento.strftime("%d/%m/%Y"),
                "data_com": data_com_estimada.strftime("%d/%m/%Y"),
                "valor": float(valor),
                "data_com_obj": data_com_estimada,
                "data_pagamento_obj": data_pagamento
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
    
    hoje = datetime.now()
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        nome = papel["nome"]
        
        dividendos = buscar_dividendos_detalhados(ticker)
        total_encontrados += len(dividendos)
        
        for div in dividendos:
            # Usa Data COM para filtro
            dias_atras_com = (hoje - div["data_com_obj"]).days
            
            # Filtra dividendos com Data COM nos últimos 60 dias
            if 0 <= dias_atras_com <= 60:
                # Calcula dias até pagamento (ou se já passou)
                dias_para_pagamento = (div["data_pagamento_obj"] - hoje).days
                
                # Define status do pagamento
                if dias_para_pagamento < 0:
                    status_pagamento = "✅ Já pago"
                elif dias_para_pagamento == 0:
                    status_pagamento = "💰 Pagamento HOJE"
                elif dias_para_pagamento <= 7:
                    status_pagamento = f"⏳ Em {dias_para_pagamento} dias"
                else:
                    status_pagamento = f"📅 Em {dias_para_pagamento} dias ({div['data_pagamento']})"
                
                # Monta mensagem
                msg = (
                    f"#{ticker} | {mes_ano} | {nome}\n\n"
                    f"💰 *DIVIDENDO*\n"
                    f"💵 *Valor:* R$ {div['valor']:.4f}\n"
                    f"📅 *Data COM:* {div['data_com']}\n"
                    f"💳 *Pagamento:* {status_pagamento}\n"
                    f"📊 *Dias desde COM:* {dias_atras_com}"
                )
                
                enviar_telegram(msg)
                total_alertas += 1
                logger.info(f"✅ Alerta: {ticker} | COM: {div['data_com']} | Pag: {div['data_pagamento']}")
    
    logger.info(f"✅ Fim: {total_alertas} alertas / {total_encontrados} encontrados")
    
    # Mensagem final
    if total_alertas == 0:
        enviar_telegram(
            f"ℹ️ *Status:*\n\n"
            f"📊 Ativos: {len(MEUS_PAPEIS)}\n"
            f"🔍 Encontrados: {total_encontrados}\n"
            f"⚠️ Nenhum dividendo com Data COM nos últimos 60 dias"
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
