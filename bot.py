"""
🤖 RADAR IDIV - Bot de Monitoramento Fundamentalista
Fonte: Yahoo Finance (yfinance)
Versão: Dividendos + Fundamentos + Notícias + Sinais
"""

import yfinance as yf
import requests
from datetime import datetime, timedelta
import logging
import pandas as pd

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

# Thresholds para alertas
THRESHOLDS = {
    "dividend_yield_min": 0.06,      # Alerta se DY > 6%
    "payout_max": 0.80,              # Alerta se payout > 80%
    "price_target_upside": 0.20,     # Alerta se upside > 20%
    "revenue_decline": -0.10,        # Alerta se receita cair > 10%
    "dividend_cut": -0.20,           # Alerta se dividendo cair > 20%
}

# ==============================================================================
# TELEGRAM
# ==============================================================================
def enviar_telegram(mensagem, disable_web_preview=False):
    """Envia mensagem para Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": disable_web_preview
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            logger.info("✅ Telegram enviado")
            return True
        logger.warning(f"⚠️ Telegram status: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Erro Telegram: {e}")
    
    return False

# ==============================================================================
# BUSCAR DADOS COMPLETOS DA AÇÃO
# ==============================================================================
def analisar_acao(ticker):
    """
    Analisa ação completa: dividendos, fundamentos, notícias, etc.
    Retorna dicionário com todos os dados relevantes
    """
    logger.info(f"🔍 Analisando: {ticker}")
    
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        # Dados básicos
        dados = {
            "ticker": ticker,
            "nome": info.get('longName', ticker),
            "setor": info.get('sector', 'N/A'),
            "preco_atual": info.get('currentPrice', info.get('regularMarketPrice', 0)),
            
            # Dividendos
            "dividend_rate": info.get('dividendRate', 0),
            "dividend_yield": info.get('dividendYield', 0),
            "ex_dividend_date": info.get('exDividendDate'),
            "payout_ratio": info.get('payoutRatio', 0),
            "five_year_avg_dy": info.get('fiveYearAvgDividendYield', 0),
            
            # Valuation
            "pe_ratio": info.get('trailingPE', 0),
            "pb_ratio": info.get('priceToBook', 0),
            "ev_ebitda": info.get('enterpriseToEbitda', 0),
            
            # Preços-alvo
            "price_target_mean": info.get('targetMeanPrice', 0),
            "price_target_high": info.get('targetHighPrice', 0),
            "price_target_low": info.get('targetLowPrice', 0),
            "recommendation": info.get('recommendationKey', 'N/A'),
            
            # Histórico
            "dividendos": acao.dividends,
            "actions": acao.actions,
            "splits": acao.splits,
            
            # Fundamentos
            "financials": acao.financials,
            "cashflow": acao.cashflow,
            "quarterly_cashflow": acao.quarterly_cashflow,
            "balance_sheet": acao.balance_sheet,
            
            # Notícias
            "noticias": acao.news[:5],  # Últimas 5
            
            # Sinais de alerta
            "alertas": []
        }
        
        # Calcular upside/downside
        if dados["preco_atual"] > 0 and dados["price_target_mean"] > 0:
            dados["upside"] = (dados["price_target_mean"] - dados["preco_atual"]) / dados["preco_atual"]
        else:
            dados["upside"] = 0
        
        # Verificar se dividendo foi cortado
        if len(dados["dividendos"]) >= 2:
            ultimo = dados["dividendos"].iloc[-1]
            anterior = dados["dividendos"].iloc[-2]
            if anterior > 0:
                variacao = (ultimo - anterior) / anterior
                if variacao < THRESHOLDS["dividend_cut"]:
                    dados["alertas"].append(f"⚠️ Dividendo caiu {variacao:.1%}")
        
        logger.info(f"✅ Análise completa: {ticker}")
        return dados
        
    except Exception as e:
        logger.error(f"❌ Erro ao analisar {ticker}: {e}")
        return None

# ==============================================================================
# GERAR ALERTAS FUNDAMENTISTAS
# ==============================================================================
def gerar_alertas(dados):
    """
    Gera alertas baseados em thresholds
    """
    alertas = []
    ticker = dados["ticker"]
    
    # 1. Dividend Yield alto
    if dados["dividend_yield"] and dados["dividend_yield"] > THRESHOLDS["dividend_yield_min"]:
        alertas.append({
            "tipo": "DY_ALTO",
            "titulo": "🟢 Dividend Yield Atraente",
            "mensagem": f"DY atual: {dados['dividend_yield']:.2%} (mínimo: {THRESHOLDS['dividend_yield_min']:.0%})"
        })
    
    # 2. Payout muito alto
    if dados["payout_ratio"] and dados["payout_ratio"] > THRESHOLDS["payout_max"]:
        alertas.append({
            "tipo": "PAYOUT_ALTO",
            "titulo": "🟡 Payout Elevado",
            "mensagem": f"Payout: {dados['payout_ratio']:.1%} (máximo: {THRESHOLDS['payout_max']:.0%})\n⚠️ Risco de corte de dividendos"
        })
    
    # 3. Upside significativo
    if dados["upside"] and dados["upside"] > THRESHOLDS["price_target_upside"]:
        alertas.append({
            "tipo": "UPSIDE",
            "titulo": "🟢 Upside Potencial",
            "mensagem": f"Upside: {dados['upside']:.1%} (alvo: R$ {dados['price_target_mean']:.2f})"
        })
    
    # 4. Dividendo cortado
    for alerta in dados.get("alertas", []):
        if "Dividendo caiu" in alerta:
            alertas.append({
                "tipo": "CORTE_DIVIDENDO",
                "titulo": "🔴 Corte de Dividendo",
                "mensagem": alerta
            })
    
    return alertas

# ==============================================================================
# FORMATAR MENSAGENS
# ==============================================================================
def formatar_resumo_diario(dados_lista):
    """
    Formata resumo diário de todos os ativos
    """
    msg = "📊 *RESUMO DIÁRIO - FUNDAMENTOS*\n\n"
    
    for dados in dados_lista:
        if not dados:
            continue
        
        ticker = dados["ticker"]
        nome = dados["nome"].split()[0]  # Só primeiro nome
        
        dy = dados["dividend_yield"] or 0
        payout = dados["payout_ratio"] or 0
        pe = dados["pe_ratio"] or 0
        upside = dados["upside"] or 0
        
        # Ícones baseados em fundamentos
        icone_dy = "🟢" if dy > 0.08 else "🟡" if dy > 0.06 else "🔴"
        icone_payout = "🟢" if payout < 0.60 else "🟡" if payout < 0.80 else "🔴"
        
        msg += f"#{ticker} | {nome}\n"
        msg += f"{icone_dy} DY: {dy:.2%} | "
        msg += f"{icone_payout} Payout: {payout:.1%}\n"
        msg += f"P/L: {pe:.2f} | Upside: {upside:.1%}\n\n"
    
    return msg

def formatar_alerta_dividendo(dados):
    """
    Formata alerta de dividendo (Data COM próxima)
    """
    ticker = dados["ticker"]
    nome = dados["nome"].split()[0]
    
    ex_div = dados["ex_dividend_date"]
    if not ex_div:
        return None
    
    data_com = datetime.fromtimestamp(ex_div)
    hoje = datetime.now()
    dias_para_com = (data_com - hoje).days
    
    # Só alerta se Data COM for nos próximos 15 dias
    if dias_para_com < 0 or dias_para_com > 15:
        return None
    
    valor_div = dados["dividend_rate"] or 0
    dy = dados["dividend_yield"] or 0
    
    if dias_para_com == 0:
        status = "💰 Data COM HOJE"
    elif dias_para_com <= 7:
        status = f"⏳ Em {dias_para_com} dias"
    else:
        status = f"📅 Em {dias_para_com} dias"
    
    msg = (
        f"#{ticker} | {nome}\n\n"
        f"💰 *DIVIDENDO - DATA COM PRÓXIMA*\n"
        f"{status}\n"
        f"📅 *Data COM:* {data_com.strftime('%d/%m/%Y')}\n"
        f"💵 *Dividendo:* R$ {valor_div:.4f}\n"
        f"📊 *DY:* {dy:.2%}"
    )
    
    return msg

def formatar_alerta_fundamento(alerta, dados):
    """
    Formata alerta de fundamento (DY alto, payout alto, etc)
    """
    ticker = dados["ticker"]
    nome = dados["nome"].split()[0]
    
    msg = (
        f"#{ticker} | {nome}\n\n"
        f"{alerta['titulo']}\n\n"
        f"{alerta['mensagem']}"
    )
    
    return msg

def formatar_noticias(dados):
    """
    Formata últimas notícias
    """
    ticker = dados["ticker"]
    nome = dados["nome"].split()[0]
    noticias = dados.get("noticias", [])
    
    if not noticias:
        return None
    
    msg = f"📰 *NOTÍCIAS - #{ticker} | {nome}*\n\n"
    
    for i, noticia in enumerate(noticias[:3], 1):
        titulo = noticia.get('title', 'Sem título')
        publisher = noticia.get('publisher', 'Desconhecido')
        link = noticia.get('link', '#')
        
        # Trunca título se muito longo
        if len(titulo) > 80:
            titulo = titulo[:77] + "..."
        
        msg += f"{i}. *{titulo}*\n"
        msg += f"   📌 {publisher}\n"
        msg += f"   🔗 [Ler mais]({link})\n\n"
    
    return msg

# ==============================================================================
# RADAR PRINCIPAL
# ==============================================================================
def main():
    logger.info("="*60)
    logger.info("🤖 RADAR IDIV - Monitoramento Fundamentalista")
    logger.info("="*60)
    
    hoje = datetime.now().strftime("%d/%m/%Y")
    enviar_telegram(f"🤖 *Radar IDIV | {hoje}*\nIniciando monitoramento de {len(MEUS_PAPEIS)} ativos...")
    
    todos_dados = []
    total_alertas = 0
    total_alertas_fundamentos = 0
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        
        # Analisa ação completa
        dados = analisar_acao(ticker)
        if not dados:
            continue
        
        todos_dados.append(dados)
        
        # 1. Alerta de Data COM próxima
        msg_com = formatar_alerta_dividendo(dados)
        if msg_com:
            enviar_telegram(msg_com)
            total_alertas += 1
            logger.info(f"✅ Alerta Data COM: {ticker}")
        
        # 2. Alertas de fundamentos
        alertas = gerar_alertas(dados)
        for alerta in alertas:
            msg = formatar_alerta_fundamento(alerta, dados)
            enviar_telegram(msg)
            total_alertas += 1
            total_alertas_fundamentos += 1
            logger.info(f"✅ Alerta fundamento: {ticker} | {alerta['tipo']}")
        
        # 3. Notícias (apenas se tiver alerta de fundamento)
        if alertas:
            msg_noticias = formatar_noticias(dados)
            if msg_noticias:
                enviar_telegram(msg_noticias, disable_web_preview=True)
    
    # 4. Resumo diário
    if todos_dados:
        msg_resumo = formatar_resumo_diario(todos_dados)
        enviar_telegram(msg_resumo)
    
    # 5. Mensagem final
    msg_final = (
        f"✅ *Monitoramento Concluído!*\n\n"
        f"📊 Ativos analisados: {len(todos_dados)}\n"
        f"🔔 Alertas de dividendos: {total_alertas - total_alertas_fundamentos}\n"
        f"📈 Alertas de fundamentos: {total_alertas_fundamentos}\n"
        f"📣 Total alertas: {total_alertas}"
    )
    enviar_telegram(msg_final)
    
    logger.info(f"✅ Fim: {total_alertas} alertas")

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    main()
