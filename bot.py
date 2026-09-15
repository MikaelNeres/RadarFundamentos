"""
🤖 RADAR IDIV - Bot de Monitoramento Fundamentalista
Fonte: Yahoo Finance + Google News RSS
Versão: Tabelas Organizadas + Alertas Individuais
"""

import yfinance as yf
import requests
import feedparser
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
]

THRESHOLDS = {
    "dividend_yield_min": 0.06,
    "payout_max": 0.80,
    "price_target_upside": 0.20,
    "revenue_decline": -0.10,
    "dividend_cut": -0.20,
}

# ==============================================================================
# TELEGRAM
# ==============================================================================
def enviar_telegram(mensagem, disable_web_preview=False, parse_mode="Markdown"):
    """Envia mensagem para Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": parse_mode,
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
# GOOGLE NEWS RSS
# ==============================================================================
def buscar_noticias_google(ticker, nome_empresa):
    """Busca notícias no Google News RSS"""
    logger.info(f"🔍 Buscando notícias Google: {ticker}")
    
    query = f"{ticker} OR {nome_empresa.split()[0]} OR {nome_empresa} ação OR {nome_empresa} dividendos"
    url = f"https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    
    try:
        feed = feedparser.parse(url)
        
        if not feed.entries:
            logger.warning(f"⚠️ Sem notícias: {ticker}")
            return []
        
        noticias = []
        for entry in feed.entries[:5]:
            titulo = entry.title if hasattr(entry, 'title') else ''
            link = entry.link if hasattr(entry, 'link') else ''
            
            publisher = "Google News"
            if hasattr(entry, 'source') and entry.source:
                publisher = entry.source
            elif ' - ' in titulo:
                parts = titulo.split(' - ')
                if len(parts) > 1:
                    publisher = parts[0]
                    titulo = ' - '.join(parts[1:])
            
            publicado = entry.published if hasattr(entry, 'published') else ''
            
            if titulo and link:
                noticias.append({
                    'title': titulo,
                    'link': link,
                    'publisher': publisher,
                    'published': publicado
                })
        
        logger.info(f"✅ {len(noticias)} notícias: {ticker}")
        return noticias
        
    except Exception as e:
        logger.error(f"❌ Erro Google News {ticker}: {e}")
        return []

def formatar_noticias_google(ticker, nome, noticias):
    """Formata notícias do Google News"""
    if not noticias:
        return None
    
    msg = f"📰 *NOTÍCIAS - #{ticker} | {nome}*\n\n"
    
    for i, noticia in enumerate(noticias[:3], 1):
        titulo = noticia['title']
        link = noticia['link']
        publisher = noticia['publisher']
        
        if len(titulo) > 100:
            titulo = titulo[:97] + "..."
        
        msg += f"{i}. *{titulo}*\n"
        msg += f"   📌 {publisher}\n"
        msg += f"   🔗 [Ler mais]({link})\n\n"
    
    return msg

# ==============================================================================
# ANÁLISE DE AÇÕES
# ==============================================================================
def analisar_acao(ticker):
    """Analisa ação completa com cálculos manuais de DY e Payout"""
    logger.info(f"🔍 Analisando: {ticker}")
    
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        preco_atual = info.get('currentPrice', info.get('regularMarketPrice', 0))
        
        # Dividendos últimos 12 meses
        dividendos = acao.dividends
        dividendos_12m = 0
        
        if not dividendos.empty:
            hoje = datetime.now()
            um_ano_atras = hoje - timedelta(days=365)
            
            for data, valor in dividendos.items():
                if hasattr(data, 'tzinfo') and data.tzinfo is not None:
                    data = data.replace(tzinfo=None)
                
                if data >= um_ano_atras:
                    dividendos_12m += valor
        
        # Calcula DY manualmente
        if preco_atual and preco_atual > 0:
            dividend_yield = dividendos_12m / preco_atual
        else:
            dividend_yield = 0
        
        dividend_rate = dividendos_12m
        
        # Calcula Payout manualmente
        eps = info.get('trailingEps', 0)
        
        if eps and eps > 0:
            payout_ratio = dividendos_12m / eps
        else:
            payout_ratio = 0
        
        payout_ratio = min(payout_ratio, 1.0)
        
        dados = {
            "ticker": ticker,
            "nome": info.get('longName', ticker),
            "setor": info.get('sector', 'N/A'),
            "preco_atual": preco_atual,
            "dividend_rate": dividend_rate,
            "dividend_yield": dividend_yield,
            "dividendos_12m": dividendos_12m,
            "ex_dividend_date": info.get('exDividendDate'),
            "payout_ratio": payout_ratio,
            "five_year_avg_dy": info.get('fiveYearAvgDividendYield', 0),
            "pe_ratio": info.get('trailingPE', 0),
            "pb_ratio": info.get('priceToBook', 0),
            "ev_ebitda": info.get('enterpriseToEbitda', 0),
            "eps": eps,
            "price_target_mean": info.get('targetMeanPrice', 0),
            "price_target_high": info.get('targetHighPrice', 0),
            "price_target_low": info.get('targetLowPrice', 0),
            "recommendation": info.get('recommendationKey', 'N/A'),
            "dividendos": dividendos,
            "actions": acao.actions,
            "splits": acao.splits,
            "financials": acao.financials,
            "cashflow": acao.cashflow,
            "quarterly_cashflow": acao.quarterly_cashflow,
            "balance_sheet": acao.balance_sheet,
            "alertas": []
        }
        
        # Upside
        if preco_atual > 0 and dados["price_target_mean"] > 0:
            dados["upside"] = (dados["price_target_mean"] - preco_atual) / preco_atual
        else:
            dados["upside"] = 0
        
        # Corte de dividendo
        if len(dividendos) >= 2:
            ultimo = dividendos.iloc[-1]
            anterior = dividendos.iloc[-2]
            if anterior > 0:
                variacao = (ultimo - anterior) / anterior
                if variacao < THRESHOLDS["dividend_cut"]:
                    dados["alertas"].append(f"⚠️ Dividendo caiu {variacao:.1%}")
        
        logger.info(f"✅ {ticker} | R$ {preco_atual:.2f} | DY: {dividend_yield:.2%} | Payout: {payout_ratio:.1%}")
        return dados
        
    except Exception as e:
        logger.error(f"❌ Erro {ticker}: {e}")
        return None

# ==============================================================================
# ALERTAS
# ==============================================================================
def gerar_alertas(dados):
    """Gera alertas baseados em thresholds"""
    alertas = []
    
    if dados["dividend_yield"] and dados["dividend_yield"] > THRESHOLDS["dividend_yield_min"]:
        alertas.append({
            "tipo": "DY_ALTO",
            "titulo": "🟢 Dividend Yield Atraente",
            "mensagem": f"DY atual: {dados['dividend_yield']:.2%} (mínimo: {THRESHOLDS['dividend_yield_min']:.0%})"
        })
    
    if dados["payout_ratio"] and dados["payout_ratio"] > THRESHOLDS["payout_max"]:
        alertas.append({
            "tipo": "PAYOUT_ALTO",
            "titulo": "🟡 Payout Elevado",
            "mensagem": f"Payout: {dados['payout_ratio']:.1%} (máximo: {THRESHOLDS['payout_max']:.0%})\n⚠️ Risco de corte de dividendos"
        })
    
    if dados["upside"] and dados["upside"] > THRESHOLDS["price_target_upside"]:
        alertas.append({
            "tipo": "UPSIDE",
            "titulo": "🟢 Upside Potencial",
            "mensagem": f"Upside: {dados['upside']:.1%} (alvo: R$ {dados['price_target_mean']:.2f})"
        })
    
    for alerta in dados.get("alertas", []):
        if "Dividendo caiu" in alerta:
            alertas.append({
                "tipo": "CORTE_DIVIDENDO",
                "titulo": "🔴 Corte de Dividendo",
                "mensagem": alerta
            })
    
    return alertas

# ==============================================================================
# FORMATAR TABELAS
# ==============================================================================
def formatar_tabela_resumo(dados_lista):
    """Formata resumo em tabela organizada"""
    if not dados_lista:
        return None
    
    hoje = datetime.now().strftime("%d/%m/%Y")
    
    msg = "📊 *RESUMO DIÁRIO - FUNDAMENTOS*\n"
    msg += f"{hoje}\n\n"
    
    # Tabela em código monoespaçado
    msg += "```\n"
    msg += "┌─────────┬──────────┬─────────┬──────────┬──────┬─────────┐\n"
    msg += "│ Ativo   │ DY (12m) │ Payout  │ P/L      │ Ups. │ Status  │\n"
    msg += "├─────────┼──────────┼─────────┼──────────┼──────┼─────────┤\n"
    
    for dados in sorted(dados_lista, key=lambda x: x.get('dividend_yield', 0), reverse=True):
        ticker = dados["ticker"]
        nome = dados["nome"].split()[:8][0]
        
        dy = dados["dividend_yield"] or 0
        payout = dados["payout_ratio"] or 0
        pe = dados["pe_ratio"] or 0
        upside = dados["upside"] or 0
        
        icone_dy = "🟢" if dy > 0.06 else "🟡" if dy > 0.04 else "🔴"
        icone_payout = "🟢" if payout < 0.60 else "🟡" if payout < 0.80 else "🔴"
        
        if dy > 0.06 and upside > 0.15:
            status = "🟢 Buy "
        elif dy > 0.04 or upside > 0.05:
            status = "🟡 Hold"
        else:
            status = "🔴 Sell"
        
        msg += f"│ {ticker:<7} │ {dy:>6.2%} {icone_dy} │ {payout:>6.1%} {icone_payout} │ {pe:>8.2f} │ {upside:>5.1%}│ {status} │\n"
    
    msg += "└─────────┴──────────┴─────────┴──────────┴──────┴─────────┘\n"
    msg += "```\n\n"
    
    msg += "🟢 DY > 6%  |  🟡 DY 4-6%  |  🔴 DY < 4%\n"
    msg += "🟢 Payout < 60%  |  🟡 60-80%  |  🔴 > 80%\n"
    
    return msg

def formatar_tabela_data_com(dados_com):
    """Formata tabela de Data COM próxima"""
    if not dados_com:
        return None
    
    msg = "💰 *DATA COM PRÓXIMA*\n\n"
    
    msg += "```\n"
    msg += "┌─────────┬──────────────┬────────────┬──────────┬─────────┐\n"
    msg += "│ Ativo   │ Data COM     │ Pagamento  │ Valor    │ DY      │\n"
    msg += "├─────────┼──────────────┼────────────┼──────────┼─────────┤\n"
    
    for dados in sorted(dados_com, key=lambda x: x["dias_para_com"]):
        ticker = dados["ticker"]
        nome = dados["nome"].split()[:8][0]
        data_com = dados["data_com"]
        data_pag = dados["data_pagamento"]
        valor = dados["dividend_rate"]
        dy = dados["dividend_yield"]
        
        msg += f"│ {ticker:<7} │ {data_com:<12} │ {data_pag:<10} │ R$ {valor:>5.4f} │ {dy:>6.2%} │\n"
    
    msg += "└─────────┴──────────────┴────────────┴──────────┴─────────┘\n"
    msg += "```\n"
    
    return msg

# ==============================================================================
# ALERTAS INDIVIDUAIS
# ==============================================================================
def formatar_alerta_fundamento(alerta, dados):
    """Formata alerta individual de fundamento"""
    ticker = dados["ticker"]
    nome = dados["nome"].split()[0]
    
    msg = f"{alerta['titulo']}\n\n"
    msg += f"#{ticker} | {nome}\n\n"
    msg += f"{alerta['mensagem']}"
    
    return msg

def formatar_alerta_data_com(dados):
    """Formata alerta de Data COM próxima"""
    ticker = dados["ticker"]
    nome = dados["nome"].split()[0]
    
    ex_div = dados["ex_dividend_date"]
    if not ex_div:
        return None
    
    data_com = datetime.fromtimestamp(ex_div)
    hoje = datetime.now()
    dias_para_com = (data_com - hoje).days
    
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
    dados_data_com = []
    total_alertas = 0
    total_alertas_fundamentos = 0
    total_noticias = 0
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        
        # 1. Analisa ação
        dados = analisar_acao(ticker)
        if not dados:
            continue
        
        todos_dados.append(dados)
        
        # 2. Alerta Data COM
        msg_com = formatar_alerta_data_com(dados)
        if msg_com:
            enviar_telegram(msg_com)
            dados_data_com.append({
                "ticker": ticker,
                "nome": dados["nome"],
                "data_com": dados["ex_dividend_date"],
                "data_pagamento": dados.get("ex_dividend_date", 0) + 15,
                "dividend_rate": dados["dividend_rate"],
                "dividend_yield": dados["dividend_yield"],
                "dias_para_com": (datetime.fromtimestamp(dados["ex_dividend_date"]) - datetime.now()).days
            })
            total_alertas += 1
            logger.info(f"✅ Alerta Data COM: {ticker}")
        
        # 3. Alertas de fundamentos
        alertas = gerar_alertas(dados)
        for alerta in alertas:
            msg = formatar_alerta_fundamento(alerta, dados)
            enviar_telegram(msg)
            total_alertas += 1
            total_alertas_fundamentos += 1
            logger.info(f"✅ Alerta fundamento: {ticker} | {alerta['tipo']}")
        
        # 4. Notícias (se tiver alerta)
        if alertas:
            noticias = buscar_noticias_google(ticker, dados["nome"])
            if noticias:
                msg_noticias = formatar_noticias_google(ticker, dados["nome"].split()[0], noticias)
                if msg_noticias:
                    enviar_telegram(msg_noticias, disable_web_preview=True)
                    total_noticias += len(noticias)
                    logger.info(f"✅ Notícias: {ticker} | {len(noticias)} notícias")
    
    # 5. Tabela de Data COM (se tiver)
    if dados_data_com:
        msg_tabela_com = formatar_tabela_data_com(dados_data_com)
        if msg_tabela_com:
            enviar_telegram(msg_tabela_com)
    
    # 6. Tabela Resumo (sempre envia)
    if todos_dados:
        msg_tabela = formatar_tabela_resumo(todos_dados)
        if msg_tabela:
            enviar_telegram(msg_tabela)
    
    # 7. Mensagem final
    msg_final = (
        f"✅ *Monitoramento Concluído!*\n\n"
        f"📊 Ativos analisados: {len(todos_dados)}\n"
        f"🔔 Alertas de dividendos: {total_alertas - total_alertas_fundamentos}\n"
        f"📈 Alertas de fundamentos: {total_alertas_fundamentos}\n"
        f"📰 Notícias enviadas: {total_noticias}\n"
        f"📣 Total alertas: {total_alertas}"
    )
    enviar_telegram(msg_final)
    
    logger.info(f"✅ Fim: {total_alertas} alertas | {total_noticias} notícias")

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    main()
