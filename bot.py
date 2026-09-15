"""
🤖 RADAR IDIV - Bot de Monitoramento Fundamentalista
Fonte: Yahoo Finance + Google News RSS
Versão: Tabelas WhatsApp (copy-paste friendly)
"""

import yfinance as yf
import requests
import feedparser
import re
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
            
            if titulo and link:
                noticias.append({
                    'title': titulo,
                    'link': link,
                    'publisher': publisher
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
        
        if preco_atual and preco_atual > 0:
            dividend_yield = dividendos_12m / preco_atual
        else:
            dividend_yield = 0
        
        dividend_rate = dividendos_12m
        
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
        
        if preco_atual > 0 and dados["price_target_mean"] > 0:
            dados["upside"] = (dados["price_target_mean"] - preco_atual) / preco_atual
        else:
            dados["upside"] = 0
        
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
# TABELAS WHATSAPP
# ==============================================================================
def formatar_tabela_resumo_whatsapp(dados_lista):
    """Formata tabela simples para WhatsApp (copy-paste friendly)"""
    if not dados_lista:
        return None
    
    hoje = datetime.now().strftime("%d/%m/%Y")
    
    msg = "📊 *RESUMO DIÁRIO - FUNDAMENTOS*\n"
    msg += f"{hoje}\n\n"
    
    msg += "Ativo   | DY (12m) | Payout  | P/L   | Ups.  | Status\n"
    msg += "--------|----------|---------|-------|-------|--------\n"
    
    for dados in sorted(dados_lista, key=lambda x: x.get('dividend_yield', 0), reverse=True):
        ticker = dados["ticker"]
        dy = dados["dividend_yield"] or 0
        payout = dados["payout_ratio"] or 0
        pe = dados["pe_ratio"] or 0
        upside = dados["upside"] or 0
        
        icone_dy = "🟢" if dy > 0.06 else "🟡" if dy > 0.04 else "🔴"
        icone_payout = "🟢" if payout < 0.60 else "🟡" if payout < 0.80 else "🔴"
        
        if dy > 0.06 and upside > 0.15:
            status = "🟢 Buy"
        elif dy > 0.04 or upside > 0.05:
            status = "🟡 Hold"
        else:
            status = "🔴 Sell"
        
        msg += f"{ticker:<7} | {dy:>6.2%} {icone_dy} | {payout:>6.1%} {icone_payout} | {pe:>6.2f} | {upside:>5.1%} | {status}\n"
    
    msg += "\n🟢 DY > 6%  |  🟡 DY 4-6%  |  🔴 DY < 4%\n"
    msg += "🟢 Payout < 60%  |  🟡 60-80%  |  🔴 > 80%\n"
    
    return msg

def formatar_alertas_whatsapp(alertas_lista):
    """Formata alertas em texto simples para WhatsApp"""
    if not alertas_lista:
        return None
    
    dy_alto = [a for a in alertas_lista if a['tipo'] == 'DY_ALTO']
    payout_alto = [a for a in alertas_lista if a['tipo'] == 'PAYOUT_ALTO']
    upside = [a for a in alertas_lista if a['tipo'] == 'UPSIDE']
    corte_div = [a for a in alertas_lista if a['tipo'] == 'CORTE_DIVIDENDO']
    
    msg = ""
    
    if dy_alto:
        msg += "🟢 *DIVIDEND YIELD ATRAENTE* (>6%)\n\n"
        msg += "Ativo   | DY Atual | Threshold\n"
        msg += "--------|----------|----------\n"
        
        for alerta in dy_alto:
            ticker = alerta['ticker']
            dy_match = re.search(r'DY atual: ([\d.]+%)', alerta['mensagem'])
            dy = dy_match.group(1) if dy_match else 'N/A'
            msg += f"{ticker:<7} | {dy:<8} | > 6.00%\n"
        
        msg += "\n"
    
    if payout_alto:
        msg += "🟡 *PAYOUT ELEVADO* (>80%) - Risco de Corte\n\n"
        msg += "Ativo   | Payout   | Threshold\n"
        msg += "--------|----------|----------\n"
        
        for alerta in payout_alto:
            ticker = alerta['ticker']
            payout_match = re.search(r'Payout: ([\d.]+%)', alerta['mensagem'])
            payout = payout_match.group(1) if payout_match else 'N/A'
            msg += f"{ticker:<7} | {payout:<8} | > 80.0%\n"
        
        msg += "\n"
    
    if upside:
        msg += "🟢 *UPSIDE POTENCIAL* (>20%)\n\n"
        msg += "Ativo   | Upside   | Alvo\n"
        msg += "--------|----------|----------\n"
        
        for alerta in upside:
            ticker = alerta['ticker']
            upside_match = re.search(r'Upside: ([\d.]+%)', alerta['mensagem'])
            alvo_match = re.search(r'alvo: R\$ ([\d.]+)', alerta['mensagem'])
            
            upside_val = upside_match.group(1) if upside_match else 'N/A'
            alvo_val = alvo_match.group(1) if alvo_match else 'N/A'
            
            msg += f"{ticker:<7} | {upside_val:<8} | R$ {alvo_val}\n"
        
        msg += "\n"
    
    if corte_div:
        msg += "🔴 *CORTE DE DIVIDENDO*\n\n"
        msg += "Ativo   | Variação  | Alerta\n"
        msg += "--------|-----------|----------------\n"
        
        for alerta in corte_div:
            ticker = alerta['ticker']
            variacao_match = re.search(r'caiu ([\d.-]+%)', alerta['mensagem'])
            variacao = variacao_match.group(1) if variacao_match else 'N/A'
            msg += f"{ticker:<7} | {variacao:<9} | ⚠️ Risco\n"
        
        msg += "\n"
    
    return msg

def formatar_data_com_whatsapp(dados_com):
    """Formata Data COM próxima para WhatsApp"""
    if not dados_com:
        return None
    
    msg = "💰 *DATA COM PRÓXIMA*\n\n"
    msg += "Ativo   | Data COM   | Dias  | Valor    | DY\n"
    msg += "--------|------------|-------|----------|------\n"
    
    for dados in sorted(dados_com, key=lambda x: x["dias_para_com"]):
        ticker = dados["ticker"]
        data_com = dados["data_com"]
        dias = dados["dias_para_com"]
        valor = dados["dividend_rate"]
        dy = dados["dividend_yield"]
        
        msg += f"{ticker:<7} | {data_com:<10} | {dias:>5} | R$ {valor:>5.4f} | {dy:>6.2%}\n"
    
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
    alertas_gerais = []
    total_noticias = 0
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        
        # 1. Analisa ação
        dados = analisar_acao(ticker)
        if not dados:
            continue
        
        todos_dados.append(dados)
        
        # 2. Data COM próxima
        if dados["ex_dividend_date"]:
            data_com = datetime.fromtimestamp(dados["ex_dividend_date"])
            dias_para_com = (data_com - datetime.now()).days
            
            if 0 <= dias_para_com <= 15:
                dados_data_com.append({
                    "ticker": ticker,
                    "nome": dados["nome"],
                    "data_com": data_com.strftime("%d/%m/%Y"),
                    "dias_para_com": dias_para_com,
                    "dividend_rate": dados["dividend_rate"],
                    "dividend_yield": dados["dividend_yield"]
                })
        
        # 3. Gera alertas
        alertas = gerar_alertas(dados)
        for alerta in alertas:
            alertas_gerais.append({
                "ticker": ticker,
                "nome": dados["nome"],
                "tipo": alerta["tipo"],
                "mensagem": alerta["mensagem"]
            })
        
        # 4. Notícias (se tiver alerta)
        if alertas:
            noticias = buscar_noticias_google(ticker, dados["nome"])
            if noticias:
                msg_noticias = formatar_noticias_google(ticker, dados["nome"].split()[0], noticias)
                if msg_noticias:
                    enviar_telegram(msg_noticias, disable_web_preview=True)
                    total_noticias += len(noticias)
    
    # 5. Tabela Data COM
    if dados_data_com:
        msg_com = formatar_data_com_whatsapp(dados_data_com)
        if msg_com:
            enviar_telegram(msg_com)
    
    # 6. Tabela Alertas
    if alertas_gerais:
        msg_alertas = formatar_alertas_whatsapp(alertas_gerais)
        if msg_alertas:
            enviar_telegram(msg_alertas)
    
    # 7. Tabela Resumo
    if todos_dados:
        msg_tabela = formatar_tabela_resumo_whatsapp(todos_dados)
        if msg_tabela:
            enviar_telegram(msg_tabela)
    
    # 8. Mensagem final
    msg_final = (
        f"✅ *Monitoramento Concluído!*\n\n"
        f"📊 Ativos analisados: {len(todos_dados)}\n"
        f"🔔 Alertas de dividendos: {len(dados_data_com)}\n"
        f"📈 Alertas de fundamentos: {len(alertas_gerais)}\n"
        f"📰 Notícias enviadas: {total_noticias}\n"
        f"📣 Total: {len(dados_data_com) + len(alertas_gerais)} alertas"
    )
    enviar_telegram(msg_final)
    
    logger.info(f"✅ Fim: {len(alertas_gerais)} alertas | {total_noticias} notícias")

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    main()
