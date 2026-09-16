"""
🤖 RADAR IDIV - Bot de Monitoramento Fundamentalista
=====================================================
Fonte: Yahoo Finance
Versão: Factor Investing + Payout × LPA

O que faz:
- Analisa ações brasileiras (B3)
- Estima dividendos futuros (Payout × LPA)
- Calcula score de qualidade (Factor Investing)
- Envia alertas no Telegram
- Roda automático (GitHub Actions)

Como usar:
1. Edite MEUS_ATIVOS para adicionar/remover ações
2. Commit no GitHub
3. Receba alertas no Telegram (automático)
"""

# ==============================================================================
# IMPORTS E CONFIGURAÇÕES
# ==============================================================================
import yfinance as yf
import requests
import re
from datetime import datetime, timedelta
import logging
import pandas as pd
import numpy as np

# Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Telegram
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604'

# ==============================================================================
# 📋 LISTA DE ATIVOS (EDITAR AQUI!)
# ==============================================================================
MEUS_ATIVOS = [
    "CMIG4", "BBAS3", "SAPR11", "ISAE4", "ABCB4", "LOGG3", "FIQE3", "GGBR4", "VBBR3", "SAUD3", "DEXP3",
    "ITSA4", "PETR4", "BBSE3", "ITUB4", "BBDC4", "CPLE3", "VALE3", "CSMG3", "TIMS3", "VIVT3", "CXSE3",
    "KLBN11", "TAEE11", "EGIE3", "CPFE3", "CMIN3", "BMGB4", "ALOS3", "WEGE3", "AURE3",
]

# Configurações padrão
CONFIG_PADRAO = {
    "p_l_justo": 8.0,
    "p_vp_justo": 1.2,
    "dy_medio": 0.06,
}

# Personalizações por ticker (opcional)
CONFIG_POR_TICKER = {
    "BBAS3": {"p_l_justo": 6.0, "p_vp_justo": 1.0, "dy_medio": 0.08},
    "ABCB4": {"p_l_justo": 5.0, "p_vp_justo": 0.9, "dy_medio": 0.09},
    "VBBR3": {"p_l_justo": 7.0, "p_vp_justo": 1.5, "dy_medio": 0.09},
}

def carregar_meus_papeis():
    """Carrega lista de ativos com configurações"""
    meus_papeis = []
    for ticker in MEUS_ATIVOS:
        config = CONFIG_PADRAO.copy()
        if ticker in CONFIG_POR_TICKER:
            config.update(CONFIG_POR_TICKER[ticker])
        meus_papeis.append({
            "ticker": ticker,
            "nome": ticker,
            "p_l_justo": config["p_l_justo"],
            "p_vp_justo": config["p_vp_justo"],
            "dy_medio": config["dy_medio"],
        })
    logger.info(f"📋 {len(meus_papeis)} ativos carregados")
    return meus_papeis

MEUS_PAPEIS = carregar_meus_papeis()

# Thresholds
THRESHOLDS = {
    "dividend_yield_min": 0.06,
    "price_target_upside": 0.20,
    "dividend_cut": -0.20,
    "margem_seguranca_min": 0.20,
}

# Pesos dos fatores
PESOS_FATORES = {
    "quality": 0.30,
    "low_vol": 0.25,
    "value": 0.20,
    "dividend": 0.15,
    "momentum": 0.10,
}

# ==============================================================================
# ESTIMATIVA DE DIVIDENDO (PAYOUT × LPA)
# ==============================================================================
def estimar_dividendo_por_payout(ticker):
    """Estima dividendo: LPA × Payout"""
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        lpa = info.get('trailingEps', 0)
        if not lpa or lpa <= 0:
            return 0, 0, 0, 0, 0
        
        dividendos = acao.dividends
        div_12m = 0
        if not dividendos.empty:
            hoje = datetime.now()
            um_ano_atras = hoje - timedelta(days=365)
            for data, valor in dividendos.items():
                if hasattr(data, 'tzinfo') and data.tzinfo is not None:
                    data = data.replace(tzinfo=None)
                if um_ano_atras <= data <= hoje:
                    div_12m += valor
        
        payout = min(div_12m / lpa, 1.0) if lpa > 0 else 0
        div_anual = lpa * payout
        
        # Frequência
        if not dividendos.empty:
            hoje = datetime.now()
            count = sum(1 for d in dividendos.index if (d.replace(tzinfo=None) if hasattr(d, 'tzinfo') else d) >= hoje - timedelta(days=365))
            freq = 4 if count >= 4 else 2 if count >= 2 else 1
            proximo = div_anual / freq
        else:
            proximo = div_anual / 4
        
        confianca = 0.5
        if lpa > 0: confianca += 0.2
        if 0.30 <= payout <= 0.80: confianca += 0.2
        if not dividendos.empty and len(dividendos) >= 4: confianca += 0.1
        confianca = min(confianca, 1.0)
        
        logger.info(f"📊 {ticker}: LPA R$ {lpa:.2f} | Payout {payout:.1%} | Est. R$ {proximo:.4f}")
        return div_anual, payout, lpa, confianca, proximo
    except Exception as e:
        logger.error(f"❌ Erro estimar {ticker}: {e}")
        return 0, 0, 0, 0, 0

# ==============================================================================
# FACTOR INVESTING
# ==============================================================================
def calcular_score_quality(dados):
    """Quality Factor (30%)"""
    scores = {}
    roe = dados.get("roe", 0)
    scores["roe"] = 100 if roe > 0.20 else 80 if roe > 0.15 else 60 if roe > 0.10 else 40 if roe > 0.05 else 20
    
    payout = dados.get("payout_ratio", 0)
    scores["payout"] = 100 if 0.30 <= payout <= 0.60 else 80 if 0.20 <= payout <= 0.70 else 60 if 0.10 <= payout <= 0.80 else 40
    
    margem = dados.get("profit_margins", 0)
    scores["margem"] = 100 if margem > 0.20 else 80 if margem > 0.15 else 60 if margem > 0.10 else 40 if margem > 0.05 else 20
    
    divida = dados.get("debt_to_equity", 0)
    scores["divida"] = 100 if divida < 0.5 else 80 if divida < 1.0 else 60 if divida < 1.5 else 40 if divida < 2.0 else 20
    
    crescimento = dados.get("revenue_growth", 0)
    scores["crescimento"] = 100 if crescimento > 0.15 else 80 if crescimento > 0.10 else 60 if crescimento > 0.05 else 40 if crescimento > 0 else 20
    
    score = scores.get("roe", 50)*0.30 + scores.get("payout", 50)*0.20 + scores.get("margem", 50)*0.20 + scores.get("divida", 50)*0.20 + scores.get("crescimento", 50)*0.10
    return {"score": score, "detalhes": scores}

def calcular_score_low_vol(dados, hist):
    """Low Volatility Factor (25%)"""
    scores = {}
    beta = dados.get("beta", 1.0)
    scores["beta"] = 100 if beta < 0.8 else 80 if beta < 1.0 else 60 if beta < 1.2 else 40 if beta < 1.5 else 20
    
    try:
        if len(hist) > 0:
            vol = hist['Close'].pct_change().std() * np.sqrt(252)
            scores["volatilidade"] = 100 if vol < 0.20 else 80 if vol < 0.30 else 60 if vol < 0.40 else 40 if vol < 0.50 else 20
        else:
            scores["volatilidade"] = 50
    except:
        scores["volatilidade"] = 50
    
    try:
        if len(hist) > 0:
            maxima = hist['Close'].max()
            atual = hist['Close'].iloc[-1]
            dd = (maxima - atual) / maxima
            scores["drawdown"] = 100 if dd < 0.10 else 80 if dd < 0.20 else 60 if dd < 0.30 else 40 if dd < 0.40 else 20
        else:
            scores["drawdown"] = 50
    except:
        scores["drawdown"] = 50
    
    score = scores.get("beta", 50)*0.40 + scores.get("volatilidade", 50)*0.30 + scores.get("drawdown", 50)*0.30
    return {"score": score, "detalhes": scores}

def calcular_score_value(dados, papel_config):
    """Value Factor (20%)"""
    scores = {}
    p_l = dados.get("pe_ratio", 0)
    p_l_justo = papel_config.get("p_l_justo", 8.0)
    scores["p_l"] = 100 if p_l > 0 and p_l < p_l_justo*0.5 else 80 if p_l > 0 and p_l < p_l_justo*0.75 else 60 if p_l > 0 and p_l < p_l_justo else 40 if p_l > 0 and p_l < p_l_justo*1.25 else 20
    
    p_vp = dados.get("pb_ratio", 0)
    p_vp_justo = papel_config.get("p_vp_justo", 1.2)
    scores["p_vp"] = 100 if p_vp > 0 and p_vp < p_vp_justo*0.5 else 80 if p_vp > 0 and p_vp < p_vp_justo*0.75 else 60 if p_vp > 0 and p_vp < p_vp_justo else 40 if p_vp > 0 and p_vp < p_vp_justo*1.25 else 20
    
    ev_ebitda = dados.get("ev_ebitda", 0)
    scores["ev_ebitda"] = 100 if ev_ebitda > 0 and ev_ebitda < 5 else 80 if ev_ebitda > 0 and ev_ebitda < 8 else 60 if ev_ebitda > 0 and ev_ebitda < 12 else 40 if ev_ebitda > 0 and ev_ebitda < 15 else 20
    
    score = scores.get("p_l", 50)*0.40 + scores.get("p_vp", 50)*0.30 + scores.get("ev_ebitda", 50)*0.30
    return {"score": score, "detalhes": scores}

def calcular_score_dividend(dados):
    """Dividend Factor (15%)"""
    scores = {}
    dy = dados.get("dividend_yield", 0)
    scores["dy"] = 100 if dy > 0.10 else 80 if dy > 0.08 else 60 if dy > 0.06 else 40 if dy > 0.04 else 20
    
    payout = dados.get("payout_ratio", 0)
    scores["payout"] = 100 if 0.30 <= payout <= 0.60 else 80 if 0.20 <= payout <= 0.70 else 60 if 0.10 <= payout <= 0.80 else 40
    
    dy_medio = dados.get("five_year_avg_dividend_yield", 0)
    scores["consistencia"] = 100 if dy_medio > 0 and dy >= dy_medio else 80 if dy_medio > 0 and dy >= dy_medio*0.8 else 60 if dy_medio > 0 else 40
    
    score = scores.get("dy", 50)*0.50 + scores.get("payout", 50)*0.30 + scores.get("consistencia", 50)*0.20
    return {"score": score, "detalhes": scores}

def calcular_score_momentum(dados, hist):
    """Momentum Factor (10%)"""
    scores = {}
    try:
        if len(hist) > 0:
            retorno = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
            scores["retorno_12m"] = 100 if retorno > 0.30 else 80 if retorno > 0.15 else 60 if retorno > 0 else 40 if retorno > -0.15 else 20
            
            maxima = hist['Close'].max()
            atual = hist['Close'].iloc[-1]
            dist = (atual - maxima) / maxima
            scores["distancia_maxima"] = 100 if dist > -0.10 else 80 if dist > -0.20 else 60 if dist > -0.30 else 40 if dist > -0.40 else 20
        else:
            scores["retorno_12m"] = 50
            scores["distancia_maxima"] = 50
    except:
        scores["retorno_12m"] = 50
        scores["distancia_maxima"] = 50
    
    score = scores.get("retorno_12m", 50)*0.60 + scores.get("distancia_maxima", 50)*0.40
    return {"score": score, "detalhes": scores}

def calcular_score_composto(dados, hist, papel_config):
    """Score total (média ponderada dos fatores)"""
    sq = calcular_score_quality(dados)
    sl = calcular_score_low_vol(dados, hist)
    sv = calcular_score_value(dados, papel_config)
    sd = calcular_score_dividend(dados)
    sm = calcular_score_momentum(dados, hist)
    
    score = sq["score"]*PESOS_FATORES["quality"] + sl["score"]*PESOS_FATORES["low_vol"] + sv["score"]*PESOS_FATORES["value"] + sd["score"]*PESOS_FATORES["dividend"] + sm["score"]*PESOS_FATORES["momentum"]
    
    if score >= 80: classif = "🟢 EXCELENTE"
    elif score >= 70: classif = "🟡 MUITO BOM"
    elif score >= 60: classif = "🟠 BOM"
    elif score >= 50: classif = "🔴 REGULAR"
    else: classif = "⚫ RUIM"
    
    return {"score_total": score, "classificacao": classif, "fatores": {"quality": sq, "low_vol": sl, "value": sv, "dividend": sd, "momentum": sm}}

def calcular_valor_intrinseco(dados, papel_config):
    """Valor intrínseco (Graham, P/L, P/VP, DY)"""
    preco = dados.get("preco_atual", 0)
    lpa = dados.get("eps", 0)
    p_vp = dados.get("pb_ratio", 0)
    vpa = preco / p_vp if preco > 0 and p_vp > 0 else 0
    div_12m = dados.get("dividendos_12m", 0)
    
    valores = {}
    if lpa > 0 and vpa > 0:
        vi = (22.5 * lpa * vpa) ** 0.5
        valores["graham"] = {"vi": vi, "desconto": (vi - preco) / vi if vi > preco else 0}
    
    p_l_justo = papel_config.get("p_l_justo", 8.0)
    if lpa > 0:
        vi = lpa * p_l_justo
        valores["p_l"] = {"vi": vi, "desconto": (vi - preco) / vi if vi > preco else 0}
    
    p_vp_justo = papel_config.get("p_vp_justo", 1.2)
    if vpa > 0:
        vi = vpa * p_vp_justo
        valores["p_vp"] = {"vi": vi, "desconto": (vi - preco) / vi if vi > preco else 0}
    
    dy_medio = papel_config.get("dy_medio", 0.06)
    if div_12m > 0 and dy_medio > 0:
        vi = div_12m / dy_medio
        valores["dy"] = {"vi": vi, "desconto": (vi - preco) / vi if vi > preco else 0}
    
    pesos = {"graham": 0.30, "p_l": 0.25, "p_vp": 0.25, "dy": 0.20}
    vi_final = sum(d["vi"]*p for (m, d), p in zip(valores.items(), pesos.values())) / sum(pesos.values())
    desconto = (vi_final - preco) / vi_final if vi_final > preco else 0
    
    if desconto >= 0.30: classif = "🟢 ALTO"
    elif desconto >= 0.15: classif = "🟡 MÉDIO"
    elif desconto >= 0: classif = "🟠 BAIXO"
    else: classif = "🔴 SOBREVALORIZADO"
    
    return {"vi_final": vi_final, "preco_atual": preco, "desconto_final": desconto, "classificacao": classif, "detalhes": valores}

# ==============================================================================
# ANÁLISE DE AÇÕES
# ==============================================================================
def analisar_acao(ticker):
    """Analisa ação completa"""
    logger.info(f"🔍 Analisando: {ticker}")
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        preco = info.get('currentPrice', info.get('regularMarketPrice', 0))
        
        dividendos = acao.dividends
        div_12m = 0
        if not dividendos.empty:
            hoje = datetime.now()
            um_ano_atras = hoje - timedelta(days=365)
            for data, valor in dividendos.items():
                if hasattr(data, 'tzinfo') and data.tzinfo is not None:
                    data = data.replace(tzinfo=None)
                if um_ano_atras <= data <= hoje:
                    div_12m += valor
        
        dy = div_12m / preco if preco > 0 else 0
        
        # Estimativa Payout × LPA
        div_anual, payout_medio, lpa, confianca, proximo_div = estimar_dividendo_por_payout(ticker)
        
        eps = info.get('trailingEps', 0)
        payout = min(div_12m / eps, 1.0) if eps > 0 else 0
        
        dados = {
            "ticker": ticker,
            "nome": info.get('longName', ticker),
            "setor": info.get('sector', 'N/A'),
            "preco_atual": preco,
            "dividend_rate": div_12m,
            "dividend_yield": dy,
            "dividendos_12m": div_12m,
            "lpa_12m": lpa,
            "payout_medio": payout_medio,
            "dividendo_anual_esperado": div_anual,
            "proximo_dividendo": proximo_div,
            "confianca_estimativa": confianca,
            "ex_dividend_date": info.get('exDividendDate'),
            "payout_ratio": payout,
            "five_year_avg_dividend_yield": info.get('fiveYearAvgDividendYield', 0),
            "pe_ratio": info.get('trailingPE', 0),
            "pb_ratio": info.get('priceToBook', 0),
            "ev_ebitda": info.get('enterpriseToEbitda', 0),
            "eps": eps,
            "price_target_mean": info.get('targetMeanPrice', 0),
            "recommendation": info.get('recommendationKey', 'N/A'),
            "beta": info.get('beta', 1.0),
            "roe": info.get('returnOnEquity', 0),
            "profit_margins": info.get('profitMargins', 0),
            "debt_to_equity": info.get('debtToEquity', 0),
            "revenue_growth": info.get('revenueGrowth', 0),
            "alertas": []
        }
        
        dados["upside"] = (dados["price_target_mean"] - preco) / preco if preco > 0 and dados["price_target_mean"] > 0 else 0
        
        if len(dividendos) >= 2:
            variacao = (dividendos.iloc[-1] - dividendos.iloc[-2]) / dividendos.iloc[-2] if dividendos.iloc[-2] > 0 else 0
            if variacao < THRESHOLDS["dividend_cut"]:
                dados["alertas"].append(f"⚠️ Dividendo caiu {variacao:.1%}")
        
        logger.info(f"✅ {ticker} | R$ {preco:.2f} | DY: {dy:.2%} | Est.: R$ {proximo_div:.4f}")
        return dados
    except Exception as e:
        logger.error(f"❌ Erro {ticker}: {e}")
        return None

# ==============================================================================
# ALERTAS
# ==============================================================================
def gerar_alertas(dados, hist, papel_config, rotinas):
    """Gera alertas baseado nas rotinas"""
    alertas = []
    
    # Score (MENSAL)
    if rotinas["mensal"]:
        score = calcular_score_composto(dados, hist, papel_config)
        dados["score_composto"] = score
        if score["score_total"] >= 70:
            alertas.append({
                "tipo": "SCORE_ALTO",
                "titulo": "🟢 Score Factor Investing Alto",
                "mensagem": f"Score: {score['score_total']:.0f}/100 ({score['classificacao']})\nQuality: {score['fatores']['quality']['score']:.0f} | Low Vol: {score['fatores']['low_vol']['score']:.0f}"
            })
    
    # DY (SEMANAL)
    if rotinas["semanal"]:
        if dados["dividend_yield"] > THRESHOLDS["dividend_yield_min"]:
            alertas.append({
                "tipo": "DY_ALTO",
                "titulo": "🟢 Dividend Yield Atraente",
                "mensagem": f"DY atual: {dados['dividend_yield']:.2%} (mínimo: {THRESHOLDS['dividend_yield_min']:.0%})"
            })
    
    # Upside (SEMANAL)
    if rotinas["semanal"]:
        if dados["upside"] > THRESHOLDS["price_target_upside"]:
            alertas.append({
                "tipo": "UPSIDE",
                "titulo": "🟢 Upside Potencial",
                "mensagem": f"Upside: {dados['upside']:.1%} (alvo: R$ {dados['price_target_mean']:.2f})"
            })
    
    # Corte Dividendo (DIÁRIO)
    for alerta in dados.get("alertas", []):
        if "Dividendo caiu" in alerta:
            alertas.append({"tipo": "CORTE_DIVIDENDO", "titulo": "🔴 Corte de Dividendo", "mensagem": alerta})
    
    # Valor Intrínseco (MENSAL)
    if rotinas["mensal"]:
        vi = calcular_valor_intrinseco(dados, papel_config)
        dados["valor_intrinseco"] = vi
        if vi["desconto_final"] >= THRESHOLDS["margem_seguranca_min"]:
            alertas.append({
                "tipo": "VALOR_INTRINSECO",
                "titulo": "🟢 Desconto vs Valor Intrínseco",
                "mensagem": f"Desconto: {vi['desconto_final']:.1%}\nVI: R$ {vi['vi_final']:.2f} | Preço: R$ {vi['preco_atual']:.2f}\n({vi['classificacao']})"
            })
    
    return alertas

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
# TABELAS
# ==============================================================================
def formatar_tabela_telegram(dados_lista):
    """Tabela resumo"""
    if not dados_lista:
        return None
    msg = "📊 *RESUMO DIÁRIO - FUNDAMENTOS*\n"
    msg += f"{datetime.now().strftime('%d/%m/%Y')}\n\n"
    msg += "```\n"
    msg += f"{'Ativo':<7} | {'Preço':<8} | {'DY':<7} | {'P/L':<6} | {'P/VP':<6} | {'Status':<7}\n"
    msg += f"{'-'*7} | {'-'*8} | {'-'*7} | {'-'*6} | {'-'*6} | {'-'*7}\n"
    
    for dados in sorted(dados_lista, key=lambda x: x.get('dividend_yield', 0), reverse=True):
        ticker = dados["ticker"]
        preco = dados["preco_atual"] or 0
        dy = dados["dividend_yield"] or 0
        pe = dados["pe_ratio"] or 0
        pb = dados["pb_ratio"] or 0
        icone = "🟢" if dy > 0.06 else "🟡" if dy > 0.04 else "🔴"
        status = "🟢 Buy" if dy > 0.06 and pe < 8 else "🟡 Hold" if dy > 0.04 else "🔴 Sell"
        msg += f"{ticker:<7} | R$ {preco:>5.2f} | {dy:>6.1%} {icone} | {pe:>5.2f} | {pb:>5.2f} | {status:<7}\n"
    msg += "```\n\n"
    msg += "🟢 DY > 6%  |  🟡 DY 4-6%  |  🔴 DY < 4%\n"
    return msg

def formatar_alertas_telegram(alertas_lista, rotinas):
    """Formata alertas"""
    if not alertas_lista:
        return None
    msg = ""
    
    if rotinas["mensal"]:
        score_alto = [a for a in alertas_lista if a['tipo'] == 'SCORE_ALTO']
        if score_alto:
            msg += "🟢 *SCORE FACTOR INVESTING ALTO* (≥70) - Mensal\n\n"
            msg += "```\n"
            msg += f"{'Ativo':<7} | {'Score':<8} | {'Classif.':<12}\n"
            msg += f"{'-'*7} | {'-'*8} | {'-'*12}\n"
            for a in score_alto:
                ticker = a['ticker']
                score = re.search(r'Score: ([\d.]+)/100', a['mensagem']).group(1) if re.search(r'Score: ([\d.]+)/100', a['mensagem']) else 'N/A'
                classif = re.search(r'\(([\w\s]+)\)', a['mensagem']).group(1) if re.search(r'\(([\w\s]+)\)', a['mensagem']) else 'N/A'
                msg += f"{ticker:<7} | {score:<8} | {classif:<12}\n"
            msg += "```\n\n"
        
        vi_alertas = [a for a in alertas_lista if a['tipo'] == 'VALOR_INTRINSECO']
        if vi_alertas:
            msg += "🟢 *DESCONTO VS VALOR INTRÍNSECO* (≥20%) - Mensal\n\n"
            msg += "```\n"
            msg += f"{'Ativo':<7} | {'Preço':<9} | {'VI':<9} | {'Desc.':<8}\n"
            msg += f"{'-'*7} | {'-'*9} | {'-'*9} | {'-'*8}\n"
            for a in vi_alertas:
                ticker = a['ticker']
                preco = re.search(r'Preço: R\$ ([\d.]+)', a['mensagem']).group(1) if re.search(r'Preço: R\$ ([\d.]+)', a['mensagem']) else 'N/A'
                vi = re.search(r'VI: R\$ ([\d.]+)', a['mensagem']).group(1) if re.search(r'VI: R\$ ([\d.]+)', a['mensagem']) else 'N/A'
                desc = re.search(r'Desconto: ([\d.]+%)', a['mensagem']).group(1) if re.search(r'Desconto: ([\d.]+%)', a['mensagem']) else 'N/A'
                msg += f"{ticker:<7} | R$ {preco:<8} | R$ {vi:<8} | {desc:<8}\n"
            msg += "```\n\n"
    
    if rotinas["semanal"]:
        dy_alto = [a for a in alertas_lista if a['tipo'] == 'DY_ALTO']
        if dy_alto:
            msg += "🟢 *DIVIDEND YIELD ATRAENTE* (>6%) - Semanal\n\n"
            msg += "```\n"
            msg += f"{'Ativo':<7} | {'DY Atual':<9} | {'Threshold':<9}\n"
            msg += f"{'-'*7} | {'-'*9} | {'-'*9}\n"
            for a in dy_alto:
                ticker = a['ticker']
                dy = re.search(r'DY atual: ([\d.]+%)', a['mensagem']).group(1) if re.search(r'DY atual: ([\d.]+%)', a['mensagem']) else 'N/A'
                msg += f"{ticker:<7} | {dy:<9} | {'>'  + ' 6.00%':<8}\n"
            msg += "```\n\n"
        
        upside = [a for a in alertas_lista if a['tipo'] == 'UPSIDE']
        if upside:
            msg += "🟢 *UPSIDE POTENCIAL* (>20%) - Semanal\n\n"
            msg += "```\n"
            msg += f"{'Ativo':<7} | {'Upside':<9} | {'Alvo':<12}\n"
            msg += f"{'-'*7} | {'-'*9} | {'-'*12}\n"
            for a in upside:
                ticker = a['ticker']
                up = re.search(r'Upside: ([\d.]+%)', a['mensagem']).group(1) if re.search(r'Upside: ([\d.]+%)', a['mensagem']) else 'N/A'
                alvo = re.search(r'alvo: R\$ ([\d.]+)', a['mensagem']).group(1) if re.search(r'alvo: R\$ ([\d.]+)', a['mensagem']) else 'N/A'
                msg += f"{ticker:<7} | {up:<9} | {'R$ ' + str(alvo):<11}\n"
            msg += "```\n\n"
    
    return msg

def formatar_data_com_telegram(dados_com):
    """Data COM"""
    if not dados_com:
        return None
    msg = "💰 *DATA COM PRÓXIMA*\n"
    msg += "Fonte: Estimativa Payout × LPA\n\n"
    msg += "```\n"
    msg += f"{'Ativo':<7} | {'Data COM':<11} | {'Dias':<6} | {'Estimado':<10} | {'DY':<7}\n"
    msg += f"{'-'*7} | {'-'*11} | {'-'*6} | {'-'*10} | {'-'*7}\n"
    
    for dados in sorted(dados_com, key=lambda x: x["dias_para_com"]):
        ticker = dados["ticker"]
        data_com = dados["data_com"]
        dias = dados["dias_para_com"]
        valor = dados.get("proximo_dividendo", 0)
        dy = dados["dividend_yield"]
        confianca = dados.get("confianca_estimativa", 0)
        icone = "🟢" if confianca >= 0.7 else "🟡" if confianca >= 0.5 else "🔴"
        msg += f"{ticker:<7} | {data_com:<11} | {dias:>5}  | R$ {valor:>6.4f} {icone} | {dy:>6.2%}\n"
    msg += "```\n"
    msg += "🟢 Alta confiança | 🟡 Média | 🔴 Baixa\n"
    return msg

def formatar_factors_detalhado(dados_factors):
    """Score detalhado (MENSAL)"""
    if not dados_factors:
        return None
    msg = "🛡️ *SCORE POR FATOR - DETALHADO* - Mensal\n\n"
    msg += "```\n"
    msg += f"{'Ativo':<7} | {'Total':<8} | {'Qlty':<7} | {'LowV':<7} | {'Value':<7} | {'Div':<7} | {'Mom':<7}\n"
    msg += f"{'-'*7} | {'-'*8} | {'-'*7} | {'-'*7} | {'-'*7} | {'-'*7} | {'-'*7}\n"
    
    for dados in sorted(dados_factors, key=lambda x: x.get('score_total', 0), reverse=True):
        ticker = dados["ticker"]
        score_total = dados.get("score_total", 0)
        quality = dados.get("fatores", {}).get("quality", {}).get("score", 0)
        low_vol = dados.get("fatores", {}).get("low_vol", {}).get("score", 0)
        value = dados.get("fatores", {}).get("value", {}).get("score", 0)
        dividend = dados.get("fatores", {}).get("dividend", {}).get("score", 0)
        momentum = dados.get("fatores", {}).get("momentum", {}).get("score", 0)
        msg += f"{ticker:<7} | {score_total:>5.0f} | {quality:>5.0f} | {low_vol:>5.0f} | {value:>5.0f} | {dividend:>5.0f} | {momentum:>5.0f}\n"
    msg += "```\n\n"
    msg += "Pesos: Quality 30% | Low Vol 25% | Value 20% | Div 15% | Mom 10%\n"
    msg += "🟢 > 70  |  🟡 60-70  |  🔴 < 60\n"
    return msg

# ==============================================================================
# ROTINAS
# ==============================================================================
def eh_segunda_feira():
    return datetime.now().weekday() == 0

def eh_primeiro_dia_util():
    hoje = datetime.now()
    primeiro_dia = datetime(hoje.year, hoje.month, 1)
    if primeiro_dia.weekday() == 5:
        primeiro_dia_util = primeiro_dia + timedelta(days=2)
    elif primeiro_dia.weekday() == 6:
        primeiro_dia_util = primeiro_dia + timedelta(days=1)
    else:
        primeiro_dia_util = primeiro_dia
    return (hoje.day == primeiro_dia_util.day and hoje.month == primeiro_dia_util.month and hoje.year == primeiro_dia_util.year)

def verificar_rotinas():
    rotinas = {"diaria": True, "semanal": eh_segunda_feira(), "mensal": eh_primeiro_dia_util()}
    logger.info(f"📅 Rotinas: Diária={rotinas['diaria']}, Semanal={rotinas['semanal']}, Mensal={rotinas['mensal']}")
    return rotinas

# ==============================================================================
# RADAR PRINCIPAL
# ==============================================================================
def main():
    logger.info("="*60)
    logger.info(f"🤖 RADAR IDIV - {len(MEUS_PAPEIS)} ativos")
    logger.info("="*60)
    
    rotinas = verificar_rotinas()
    hoje = datetime.now().strftime("%d/%m/%Y")
    enviar_telegram(f"🤖 *Radar IDIV | {hoje}*\nIniciando monitoramento de {len(MEUS_PAPEIS)} ativos...")
    
    todos_dados = []
    dados_data_com = []
    alertas_gerais = []
    dados_factors_detalhado = []
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        dados = analisar_acao(ticker)
        if not dados:
            continue
        
        acao = yf.Ticker(f"{ticker}.SA")
        hist = acao.history(period="6mo")
        
        alertas = gerar_alertas(dados, hist, papel, rotinas)
        for alerta in alertas:
            alertas_gerais.append({"ticker": ticker, "nome": dados["nome"], "tipo": alerta["tipo"], "mensagem": alerta["mensagem"]})
        
        todos_dados.append(dados)
        
        # Data COM
        if dados.get("proximo_dividendo", 0) > 0 and dados.get("ex_dividend_date"):
            data_com = datetime.fromtimestamp(dados["ex_dividend_date"])
            dias = (data_com - datetime.now()).days
            if 0 <= dias <= 15:
                dados_data_com.append({
                    "ticker": ticker,
                    "nome": dados["nome"],
                    "data_com": data_com.strftime("%d/%m/%Y"),
                    "dias_para_com": dias,
                    "proximo_dividendo": dados["proximo_dividendo"],
                    "dividend_yield": dados["dividend_yield"],
                    "confianca_estimativa": dados["confianca_estimativa"]
                })
        
        # Score detalhado (MENSAL)
        if rotinas["mensal"]:
            score = dados.get("score_composto", {})
            if score.get("score_total", 0) > 0:
                dados_factors_detalhado.append({"ticker": ticker, "score_total": score["score_total"], "classificacao": score["classificacao"], "fatores": score["fatores"]})
    
    # Data COM
    if dados_data_com:
        msg = formatar_data_com_telegram(dados_data_com)
        if msg: enviar_telegram(msg)
    
    # Alertas
    if alertas_gerais:
        msg = formatar_alertas_telegram(alertas_gerais, rotinas)
        if msg: enviar_telegram(msg)
    
    # Resumo
    if todos_dados:
        msg = formatar_tabela_telegram(todos_dados)
        if msg: enviar_telegram(msg)
    
    # Factors detalhado (MENSAL)
    if rotinas["mensal"] and dados_factors_detalhado:
        msg = formatar_factors_detalhado(dados_factors_detalhado)
        if msg: enviar_telegram(msg)
    
    # Final
    msg_final = (
        f"✅ *Monitoramento Concluído!*\n\n"
        f"📊 Ativos analisados: {len(todos_dados)}\n"
        f"💰 Alertas Data COM: {len(dados_data_com)}\n"
        f"📈 Alertas: {len(alertas_gerais)}\n"
        f"📅 Rotinas: Diária ✅ | Semanal {'✅' if rotinas['semanal'] else '❌'} | Mensal {'✅' if rotinas['mensal'] else '❌'}"
    )
    enviar_telegram(msg_final)
    
    logger.info(f"✅ Fim: {len(alertas_gerais)} alertas")

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    main()
