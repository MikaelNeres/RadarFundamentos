"""
🤖 RADAR IDIV - Bot de Monitoramento Fundamentalista
Fonte: Yahoo Finance
Versão: Factor Investing (Quality + Low Vol)
Gestão de Ativos: Simplificada
"""

import yfinance as yf
import requests
import re
import os
from datetime import datetime, timedelta
import logging
import pandas as pd
import numpy as np

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURAÇÕES GERAIS
# ==============================================================================
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not TOKEN or not CHAT_ID:
    logger.error("❌ TOKEN ou CHAT_ID não configurados!")
    exit(1)

# ==============================================================================
# 📋 LISTA DE ATIVOS (FÁCIL GESTÃO)
# ==============================================================================
# ADICIONE ou REMOVA ativos aqui!
# Formato: "TICKER" (apenas o ticker, o resto é automático)

MEUS_ATIVOS = [
    "CMIG4",
    "BBAS3",
    "SAPR11",
    "ISAE4",
    "ABCB4",
    "LOGG3",
    "FIQE3",
    "GGBR4",
    "VBBR3",
    "SAUD3",
    "DEXP3",
    # Adicione novos tickers aqui (ex: "PETR4", "VALE3")
]

# Configurações padrão (automáticas para todos os ativos)
# Você pode personalizar por ticker se quiser
CONFIG_PADRAO = {
    "p_l_justo": 8.0,        # P/L justo padrão
    "p_vp_justo": 1.2,       # P/VP justo padrão
    "dy_medio": 0.06,        # Dividend Yield médio padrão (6%)
}

# Personalizações por ticker (opcional)
# Deixe vazio {} para usar o padrão acima
CONFIG_POR_TICKER = {
    "BBAS3": {"p_l_justo": 6.0, "p_vp_justo": 1.0, "dy_medio": 0.08},
    "ABCB4": {"p_l_justo": 5.0, "p_vp_justo": 0.9, "dy_medio": 0.09},
    "VBBR3": {"p_l_justo": 7.0, "p_vp_justo": 1.5, "dy_medio": 0.09},
    # Adicione personalizações aqui se quiser
}

# ==============================================================================
# FUNÇÃO PARA CARREGAR CONFIGURAÇÃO DOS ATIVOS
# ==============================================================================
def carregar_meus_papeis():
    """
    Carrega lista de ativos com configurações
    Retorna: Lista de dicionários com ticker, nome e configs
    """
    meus_papeis = []
    
    for ticker in MEUS_ATIVOS:
        # Pega configuração personalizada ou usa padrão
        config = CONFIG_PADRAO.copy()
        
        if ticker in CONFIG_POR_TICKER:
            config.update(CONFIG_POR_TICKER[ticker])
        
        meus_papeis.append({
            "ticker": ticker,
            "nome": ticker,  # Será atualizado com nome real da API
            "p_l_justo": config["p_l_justo"],
            "p_vp_justo": config["p_vp_justo"],
            "dy_medio": config["dy_medio"],
        })
    
    logger.info(f"📋 {len(meus_papeis)} ativos carregados: {', '.join(MEUS_ATIVOS)}")
    return meus_papeis

# Carrega ativos no início
MEUS_PAPEIS = carregar_meus_papeis()

# ==============================================================================
# THRESHOLDS E PESOS
# ==============================================================================
THRESHOLDS = {
    "dividend_yield_min": 0.06,
    "payout_max": 0.80,
    "price_target_upside": 0.20,
    "revenue_decline": -0.10,
    "dividend_cut": -0.20,
    "margem_seguranca_min": 0.20,
}

# Pesos dos Fatores (Factor Investing)
PESOS_FATORES = {
    "quality": 0.30,      # 30% - Foco em qualidade
    "low_vol": 0.25,      # 25% - Baixa volatilidade
    "value": 0.20,        # 20% - Valor
    "dividend": 0.15,     # 15% - Dividendos
    "momentum": 0.10,     # 10% - Momentum
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
# CÁLCULO DE SCORE (FACTORS)
# ==============================================================================
def calcular_score_quality(dados):
    """Quality Factor: saúde financeira e eficiência"""
    scores = {}
    
    # ROE
    roe = dados.get("roe", 0)
    if roe > 0.20:
        scores["roe"] = 100
    elif roe > 0.15:
        scores["roe"] = 80
    elif roe > 0.10:
        scores["roe"] = 60
    elif roe > 0.05:
        scores["roe"] = 40
    else:
        scores["roe"] = 20
    
    # Payout
    payout = dados.get("payout_ratio", 0)
    if 0.30 <= payout <= 0.60:
        scores["payout"] = 100
    elif 0.20 <= payout <= 0.70:
        scores["payout"] = 80
    elif 0.10 <= payout <= 0.80:
        scores["payout"] = 60
    else:
        scores["payout"] = 40
    
    # Margem Líquida
    margem_liquida = dados.get("profit_margins", 0)
    if margem_liquida > 0.20:
        scores["margem"] = 100
    elif margem_liquida > 0.15:
        scores["margem"] = 80
    elif margem_liquida > 0.10:
        scores["margem"] = 60
    elif margem_liquida > 0.05:
        scores["margem"] = 40
    else:
        scores["margem"] = 20
    
    # Dívida/Equity
    divida_equity = dados.get("debt_to_equity", 0)
    if divida_equity < 0.5:
        scores["divida"] = 100
    elif divida_equity < 1.0:
        scores["divida"] = 80
    elif divida_equity < 1.5:
        scores["divida"] = 60
    elif divida_equity < 2.0:
        scores["divida"] = 40
    else:
        scores["divida"] = 20
    
    # Crescimento Receita
    crescimento_receita = dados.get("revenue_growth", 0)
    if crescimento_receita > 0.15:
        scores["crescimento"] = 100
    elif crescimento_receita > 0.10:
        scores["crescimento"] = 80
    elif crescimento_receita > 0.05:
        scores["crescimento"] = 60
    elif crescimento_receita > 0:
        scores["crescimento"] = 40
    else:
        scores["crescimento"] = 20
    
    # Score ponderado
    score_quality = (
        scores.get("roe", 50) * 0.30 +
        scores.get("payout", 50) * 0.20 +
        scores.get("margem", 50) * 0.20 +
        scores.get("divida", 50) * 0.20 +
        scores.get("crescimento", 50) * 0.10
    )
    
    return {
        "score": score_quality,
        "detalhes": scores
    }

def calcular_score_low_vol(dados, acao):
    """Low Volatility Factor: risco e estabilidade"""
    scores = {}
    
    # Beta
    beta = dados.get("beta", 1.0)
    if beta < 0.8:
        scores["beta"] = 100
    elif beta < 1.0:
        scores["beta"] = 80
    elif beta < 1.2:
        scores["beta"] = 60
    elif beta < 1.5:
        scores["beta"] = 40
    else:
        scores["beta"] = 20
    
    # Volatilidade
    try:
        hist = acao.history(period="1y")
        if len(hist) > 0:
            volatilidade = hist['Close'].pct_change().std() * np.sqrt(252)
            if volatilidade < 0.20:
                scores["volatilidade"] = 100
            elif volatilidade < 0.30:
                scores["volatilidade"] = 80
            elif volatilidade < 0.40:
                scores["volatilidade"] = 60
            elif volatilidade < 0.50:
                scores["volatilidade"] = 40
            else:
                scores["volatilidade"] = 20
        else:
            scores["volatilidade"] = 50
    except:
        scores["volatilidade"] = 50
    
    # Drawdown
    try:
        hist = acao.history(period="1y")
        if len(hist) > 0:
            maxima = hist['Close'].max()
            atual = hist['Close'].iloc[-1]
            drawdown = (maxima - atual) / maxima
            if drawdown < 0.10:
                scores["drawdown"] = 100
            elif drawdown < 0.20:
                scores["drawdown"] = 80
            elif drawdown < 0.30:
                scores["drawdown"] = 60
            elif drawdown < 0.40:
                scores["drawdown"] = 40
            else:
                scores["drawdown"] = 20
        else:
            scores["drawdown"] = 50
    except:
        scores["drawdown"] = 50
    
    # Score ponderado
    score_low_vol = (
        scores.get("beta", 50) * 0.40 +
        scores.get("volatilidade", 50) * 0.30 +
        scores.get("drawdown", 50) * 0.30
    )
    
    return {
        "score": score_low_vol,
        "detalhes": scores
    }

def calcular_score_value(dados, papel_config):
    """Value Factor: se ação está barata"""
    scores = {}
    
    # P/L
    p_l = dados.get("pe_ratio", 0)
    p_l_justo = papel_config.get("p_l_justo", 8.0)
    if p_l > 0 and p_l < p_l_justo * 0.5:
        scores["p_l"] = 100
    elif p_l > 0 and p_l < p_l_justo * 0.75:
        scores["p_l"] = 80
    elif p_l > 0 and p_l < p_l_justo:
        scores["p_l"] = 60
    elif p_l > 0 and p_l < p_l_justo * 1.25:
        scores["p_l"] = 40
    else:
        scores["p_l"] = 20
    
    # P/VP
    p_vp = dados.get("pb_ratio", 0)
    p_vp_justo = papel_config.get("p_vp_justo", 1.2)
    if p_vp > 0 and p_vp < p_vp_justo * 0.5:
        scores["p_vp"] = 100
    elif p_vp > 0 and p_vp < p_vp_justo * 0.75:
        scores["p_vp"] = 80
    elif p_vp > 0 and p_vp < p_vp_justo:
        scores["p_vp"] = 60
    elif p_vp > 0 and p_vp < p_vp_justo * 1.25:
        scores["p_vp"] = 40
    else:
        scores["p_vp"] = 20
    
    # EV/EBITDA
    ev_ebitda = dados.get("ev_ebitda", 0)
    if ev_ebitda > 0 and ev_ebitda < 5:
        scores["ev_ebitda"] = 100
    elif ev_ebitda > 0 and ev_ebitda < 8:
        scores["ev_ebitda"] = 80
    elif ev_ebitda > 0 and ev_ebitda < 12:
        scores["ev_ebitda"] = 60
    elif ev_ebitda > 0 and ev_ebitda < 15:
        scores["ev_ebitda"] = 40
    else:
        scores["ev_ebitda"] = 20
    
    # Score ponderado
    score_value = (
        scores.get("p_l", 50) * 0.40 +
        scores.get("p_vp", 50) * 0.30 +
        scores.get("ev_ebitda", 50) * 0.30
    )
    
    return {
        "score": score_value,
        "detalhes": scores
    }

def calcular_score_dividend(dados):
    """Dividend Factor: atratividade de dividendos"""
    scores = {}
    
    # DY
    dy = dados.get("dividend_yield", 0)
    if dy > 0.10:
        scores["dy"] = 100
    elif dy > 0.08:
        scores["dy"] = 80
    elif dy > 0.06:
        scores["dy"] = 60
    elif dy > 0.04:
        scores["dy"] = 40
    else:
        scores["dy"] = 20
    
    # Payout
    payout = dados.get("payout_ratio", 0)
    if 0.30 <= payout <= 0.60:
        scores["payout"] = 100
    elif 0.20 <= payout <= 0.70:
        scores["payout"] = 80
    elif 0.10 <= payout <= 0.80:
        scores["payout"] = 60
    else:
        scores["payout"] = 40
    
    # Consistência
    dy_medio_5a = dados.get("five_year_avg_dividend_yield", 0)
    if dy_medio_5a > 0 and dy >= dy_medio_5a:
        scores["consistencia"] = 100
    elif dy_medio_5a > 0 and dy >= dy_medio_5a * 0.8:
        scores["consistencia"] = 80
    elif dy_medio_5a > 0:
        scores["consistencia"] = 60
    else:
        scores["consistencia"] = 40
    
    # Score ponderado
    score_dividend = (
        scores.get("dy", 50) * 0.50 +
        scores.get("payout", 50) * 0.30 +
        scores.get("consistencia", 50) * 0.20
    )
    
    return {
        "score": score_dividend,
        "detalhes": scores
    }

def calcular_score_momentum(dados, acao):
    """Momentum Factor: tendência de preço"""
    scores = {}
    
    try:
        hist = acao.history(period="1y")
        if len(hist) > 0:
            # Retorno 12m
            retorno_12m = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
            if retorno_12m > 0.30:
                scores["retorno_12m"] = 100
            elif retorno_12m > 0.15:
                scores["retorno_12m"] = 80
            elif retorno_12m > 0:
                scores["retorno_12m"] = 60
            elif retorno_12m > -0.15:
                scores["retorno_12m"] = 40
            else:
                scores["retorno_12m"] = 20
            
            # Preço vs Máxima
            maxima_52s = hist['Close'].max()
            atual = hist['Close'].iloc[-1]
            distancia_maxima = (atual - maxima_52s) / maxima_52s
            if distancia_maxima > -0.10:
                scores["distancia_maxima"] = 100
            elif distancia_maxima > -0.20:
                scores["distancia_maxima"] = 80
            elif distancia_maxima > -0.30:
                scores["distancia_maxima"] = 60
            elif distancia_maxima > -0.40:
                scores["distancia_maxima"] = 40
            else:
                scores["distancia_maxima"] = 20
        else:
            scores["retorno_12m"] = 50
            scores["distancia_maxima"] = 50
    except:
        scores["retorno_12m"] = 50
        scores["distancia_maxima"] = 50
    
    # Score ponderado
    score_momentum = (
        scores.get("retorno_12m", 50) * 0.60 +
        scores.get("distancia_maxima", 50) * 0.40
    )
    
    return {
        "score": score_momentum,
        "detalhes": scores
    }

def calcular_score_composto(dados, acao, papel_config):
    """Score composto usando Factor Investing"""
    score_quality = calcular_score_quality(dados)
    score_low_vol = calcular_score_low_vol(dados, acao)
    score_value = calcular_score_value(dados, papel_config)
    score_dividend = calcular_score_dividend(dados)
    score_momentum = calcular_score_momentum(dados, acao)
    
    # Score composto
    score_total = (
        score_quality["score"] * PESOS_FATORES["quality"] +
        score_low_vol["score"] * PESOS_FATORES["low_vol"] +
        score_value["score"] * PESOS_FATORES["value"] +
        score_dividend["score"] * PESOS_FATORES["dividend"] +
        score_momentum["score"] * PESOS_FATORES["momentum"]
    )
    
    # Classificação
    if score_total >= 80:
        classificacao = "🟢 EXCELENTE"
    elif score_total >= 70:
        classificacao = "🟡 MUITO BOM"
    elif score_total >= 60:
        classificacao = "🟠 BOM"
    elif score_total >= 50:
        classificacao = "🔴 REGULAR"
    else:
        classificacao = "⚫ RUIM"
    
    return {
        "score_total": score_total,
        "classificacao": classificacao,
        "fatores": {
            "quality": score_quality,
            "low_vol": score_low_vol,
            "value": score_value,
            "dividend": score_dividend,
            "momentum": score_momentum
        }
    }

def calcular_valor_intrinseco(dados, papel_config):
    """Calcula valor intrínseco usando 4 metodologias"""
    preco_atual = dados.get("preco_atual", 0)
    lpa = dados.get("eps", 0)
    
    # VPA
    p_vp = dados.get("pb_ratio", 0)
    if preco_atual > 0 and p_vp > 0:
        vpa = preco_atual / p_vp
    else:
        vpa = 0
    
    dividendos_12m = dados.get("dividendos_12m", 0)
    
    valores_intrinsecos = {}
    
    # Graham
    if lpa > 0 and vpa > 0:
        vi_graham = (22.5 * lpa * vpa) ** 0.5
        valores_intrinsecos["graham"] = {
            "vi": vi_graham,
            "desconto": (vi_graham - preco_atual) / vi_graham if vi_graham > preco_atual else 0,
            "metodo": "Graham"
        }
    
    # P/L Justo
    p_l_justo = papel_config.get("p_l_justo", 8.0)
    if lpa > 0 and p_l_justo > 0:
        vi_pl = lpa * p_l_justo
        valores_intrinsecos["p_l"] = {
            "vi": vi_pl,
            "desconto": (vi_pl - preco_atual) / vi_pl if vi_pl > preco_atual else 0,
            "metodo": "P/L Justo"
        }
    
    # P/VP Justo
    p_vp_justo = papel_config.get("p_vp_justo", 1.2)
    if vpa > 0 and p_vp_justo > 0:
        vi_pvp = vpa * p_vp_justo
        valores_intrinsecos["p_vp"] = {
            "vi": vi_pvp,
            "desconto": (vi_pvp - preco_atual) / vi_pvp if vi_pvp > preco_atual else 0,
            "metodo": "P/VP Justo"
        }
    
    # Dividend Yield
    dy_medio = papel_config.get("dy_medio", 0.06)
    if dividendos_12m > 0 and dy_medio > 0:
        vi_dy = dividendos_12m / dy_medio
        valores_intrinsecos["dy"] = {
            "vi": vi_dy,
            "desconto": (vi_dy - preco_atual) / vi_dy if vi_dy > preco_atual else 0,
            "metodo": "Dividend Yield"
        }
    
    # VI ponderado
    pesos = {
        "graham": 0.30,
        "p_l": 0.25,
        "p_vp": 0.25,
        "dy": 0.20
    }
    
    vi_ponderado = 0
    peso_total = 0
    
    for metodo, dados_vi in valores_intrinsecos.items():
        peso = pesos.get(metodo, 0)
        vi_ponderado += dados_vi["vi"] * peso
        peso_total += peso
    
    if peso_total > 0:
        vi_final = vi_ponderado / peso_total
    else:
        vi_final = 0
    
    # Desconto
    if vi_final > 0 and preco_atual > 0:
        desconto_final = (vi_final - preco_atual) / vi_final
    else:
        desconto_final = 0
    
    # Classificação
    if desconto_final >= 0.30:
        classificacao = "🟢 ALTO"
    elif desconto_final >= 0.15:
        classificacao = "🟡 MÉDIO"
    elif desconto_final >= 0:
        classificacao = "🟠 BAIXO"
    else:
        classificacao = "🔴 SOBREVALORIZADO"
    
    return {
        "vi_final": vi_final,
        "preco_atual": preco_atual,
        "desconto_final": desconto_final,
        "classificacao": classificacao,
        "detalhes": valores_intrinsecos
    }

# ==============================================================================
# ANÁLISE DE AÇÕES
# ==============================================================================
def analisar_acao(ticker):
    """Analisa ação completa"""
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
            "five_year_avg_dividend_yield": info.get('fiveYearAvgDividendYield', 0),
            "pe_ratio": info.get('trailingPE', 0),
            "pb_ratio": info.get('priceToBook', 0),
            "ev_ebitda": info.get('enterpriseToEbitda', 0),
            "eps": eps,
            "price_target_mean": info.get('targetMeanPrice', 0),
            "price_target_high": info.get('targetHighPrice', 0),
            "price_target_low": info.get('targetLowPrice', 0),
            "recommendation": info.get('recommendationKey', 'N/A'),
            "beta": info.get('beta', 1.0),
            "roe": info.get('returnOnEquity', 0),
            "profit_margins": info.get('profitMargins', 0),
            "debt_to_equity": info.get('debtToEquity', 0),
            "revenue_growth": info.get('revenueGrowth', 0),
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
        
        logger.info(f"✅ {ticker} | R$ {preco_atual:.2f} | DY: {dividend_yield:.2%}")
        return dados
        
    except Exception as e:
        logger.error(f"❌ Erro {ticker}: {e}")
        return None

# ==============================================================================
# ALERTAS
# ==============================================================================
def gerar_alertas(dados, acao, papel_config):
    """Gera alertas baseados em factors"""
    alertas = []
    
    # Score Composto
    score_composto = calcular_score_composto(dados, acao, papel_config)
    dados["score_composto"] = score_composto
    
    if score_composto["score_total"] >= 70:
        alertas.append({
            "tipo": "SCORE_ALTO",
            "titulo": "🟢 Score Factor Investing Alto",
            "mensagem": f"Score: {score_composto['score_total']:.0f}/100 ({score_composto['classificacao']})\nQuality: {score_composto['fatores']['quality']['score']:.0f} | Low Vol: {score_composto['fatores']['low_vol']['score']:.0f}"
        })
    
    # DY Alto
    if dados["dividend_yield"] and dados["dividend_yield"] > THRESHOLDS["dividend_yield_min"]:
        alertas.append({
            "tipo": "DY_ALTO",
            "titulo": "🟢 Dividend Yield Atraente",
            "mensagem": f"DY atual: {dados['dividend_yield']:.2%} (mínimo: {THRESHOLDS['dividend_yield_min']:.0%})"
        })
    
    # Payout Elevado
    if dados["payout_ratio"] and dados["payout_ratio"] > THRESHOLDS["payout_max"]:
        alertas.append({
            "tipo": "PAYOUT_ALTO",
            "titulo": "🟡 Payout Elevado",
            "mensagem": f"Payout: {dados['payout_ratio']:.1%} (máximo: {THRESHOLDS['payout_max']:.0%})\n⚠️ Risco de corte de dividendos"
        })
    
    # Upside
    if dados["upside"] and dados["upside"] > THRESHOLDS["price_target_upside"]:
        alertas.append({
            "tipo": "UPSIDE",
            "titulo": "🟢 Upside Potencial",
            "mensagem": f"Upside: {dados['upside']:.1%} (alvo: R$ {dados['price_target_mean']:.2f})"
        })
    
    # Corte Dividendo
    for alerta in dados.get("alertas", []):
        if "Dividendo caiu" in alerta:
            alertas.append({
                "tipo": "CORTE_DIVIDENDO",
                "titulo": "🔴 Corte de Dividendo",
                "mensagem": alerta
            })
    
    # Valor Intrínseco
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
# TABELAS TELEGRAM
# ==============================================================================
def formatar_tabela_telegram(dados_lista):
    """Formata tabela para Telegram"""
    if not dados_lista:
        return None
    
    hoje = datetime.now().strftime("%d/%m/%Y")
    
    msg = "📊 *RESUMO DIÁRIO - FACTOR INVESTING*\n"
    msg += f"{hoje}\n\n"
    msg += "```\n"
    
    # Header
    msg += f"{'Ativo':<7} | {'Preço':<8} | {'Score':<8} | {'Qlty':<6} | {'LowV':<6} | {'Status':<7}\n"
    msg += f"{'-'*7} | {'-'*8} | {'-'*8} | {'-'*6} | {'-'*6} | {'-'*7}\n"
    
    # Linhas
    for dados in sorted(dados_lista, key=lambda x: x.get('score_composto', {}).get('score_total', 0), reverse=True):
        ticker = dados["ticker"]
        preco = dados["preco_atual"] or 0
        score = dados.get("score_composto", {})
        score_total = score.get("score_total", 0)
        
        score_quality = score.get("fatores", {}).get("quality", {}).get("score", 0)
        score_low_vol = score.get("fatores", {}).get("low_vol", {}).get("score", 0)
        
        # Ícones
        icone_score = "🟢" if score_total >= 70 else "🟡" if score_total >= 60 else "🔴"
        
        # Status
        if score_total >= 75:
            status = "🟢 Buy"
        elif score_total >= 65:
            status = "🟡 Hold"
        else:
            status = "🔴 Sell"
        
        msg += f"{ticker:<7} | R$ {preco:>5.2f} | {score_total:>5.0f} {icone_score} | {score_quality:>5.0f} | {score_low_vol:>5.0f} | {status:<7}\n"
    
    msg += "```\n\n"
    msg += "🟢 Score > 70  |  🟡 60-70  |  🔴 < 60\n"
    msg += "Pesos: Quality 30% | Low Vol 25% | Value 20% | Div 15% | Mom 10%\n"
    
    return msg

def formatar_alertas_telegram(alertas_lista):
    """Formata alertas"""
    if not alertas_lista:
        return None
    
    score_alto = [a for a in alertas_lista if a['tipo'] == 'SCORE_ALTO']
    vi_alertas = [a for a in alertas_lista if a['tipo'] == 'VALOR_INTRINSECO']
    dy_alto = [a for a in alertas_lista if a['tipo'] == 'DY_ALTO']
    payout_alto = [a for a in alertas_lista if a['tipo'] == 'PAYOUT_ALTO']
    upside = [a for a in alertas_lista if a['tipo'] == 'UPSIDE']
    
    msg = ""
    
    # Score Alto
    if score_alto:
        msg += "🟢 *SCORE FACTOR INVESTING ALTO* (≥70)\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Score':<8} | {'Classif.':<12}\n"
        msg += f"{'-'*7} | {'-'*8} | {'-'*12}\n"
        
        for alerta in score_alto:
            ticker = alerta['ticker']
            score_match = re.search(r'Score: ([\d.]+)/100', alerta['mensagem'])
            classif_match = re.search(r'\(([\w\s]+)\)', alerta['mensagem'])
            
            score_val = score_match.group(1) if score_match else 'N/A'
            classif_val = classif_match.group(1) if classif_match else 'N/A'
            
            msg += f"{ticker:<7} | {score_val:<8} | {classif_val:<12}\n"
        
        msg += "```\n\n"
    
    # Valor Intrínseco
    if vi_alertas:
        msg += "🟢 *DESCONTO VS VALOR INTRÍNSECO* (≥20%)\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Preço':<9} | {'VI':<9} | {'Desc.':<8}\n"
        msg += f"{'-'*7} | {'-'*9} | {'-'*9} | {'-'*8}\n"
        
        for alerta in vi_alertas:
            ticker = alerta['ticker']
            preco_match = re.search(r'Preço: R\$ ([\d.]+)', alerta['mensagem'])
            vi_match = re.search(r'VI: R\$ ([\d.]+)', alerta['mensagem'])
            desc_match = re.search(r'Desconto: ([\d.]+%)', alerta['mensagem'])
            
            preco = preco_match.group(1) if preco_match else 'N/A'
            vi = vi_match.group(1) if vi_match else 'N/A'
            desc = desc_match.group(1) if desc_match else 'N/A'
            
            msg += f"{ticker:<7} | R$ {preco:<8} | R$ {vi:<8} | {desc:<8}\n"
        
        msg += "```\n\n"
    
    # DY Alto
    if dy_alto:
        msg += "🟢 *DIVIDEND YIELD ATRAENTE* (>6%)\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'DY Atual':<9} | {'Threshold':<9}\n"
        msg += f"{'-'*7} | {'-'*9} | {'-'*9}\n"
        
        for alerta in dy_alto:
            ticker = alerta['ticker']
            dy_match = re.search(r'DY atual: ([\d.]+%)', alerta['mensagem'])
            dy = dy_match.group(1) if dy_match else 'N/A'
            msg += f"{ticker:<7} | {dy:<9} | {'>'  + ' 6.00%':<8}\n"
        
        msg += "```\n\n"
    
    # Payout Alto
    if payout_alto:
        msg += "🟡 *PAYOUT ELEVADO* (>80%) - Risco de Corte\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Payout':<9} | {'Threshold':<9}\n"
        msg += f"{'-'*7} | {'-'*9} | {'-'*9}\n"
        
        for alerta in payout_alto:
            ticker = alerta['ticker']
            payout_match = re.search(r'Payout: ([\d.]+%)', alerta['mensagem'])
            payout = payout_match.group(1) if payout_match else 'N/A'
            msg += f"{ticker:<7} | {payout:<9} | {'>'  + ' 80.0%':<8}\n"
        
        msg += "```\n\n"
    
    # Upside
    if upside:
        msg += "🟢 *UPSIDE POTENCIAL* (>20%)\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Upside':<9} | {'Alvo':<12}\n"
        msg += f"{'-'*7} | {'-'*9} | {'-'*12}\n"
        
        for alerta in upside:
            ticker = alerta['ticker']
            upside_match = re.search(r'Upside: ([\d.]+%)', alerta['mensagem'])
            alvo_match = re.search(r'alvo: R\$ ([\d.]+)', alerta['mensagem'])
            
            upside_val = upside_match.group(1) if upside_match else 'N/A'
            alvo_val = alvo_match.group(1) if alvo_match else 'N/A'
            
            msg += f"{ticker:<7} | {upside_val:<9} | {'R$ ' + str(alvo_val):<11}\n"
        
        msg += "```\n\n"
    
    return msg

def formatar_data_com_telegram(dados_com):
    """Formata Data COM"""
    if not dados_com:
        return None
    
    msg = "💰 *DATA COM PRÓXIMA*\n\n"
    msg += "```\n"
    msg += f"{'Ativo':<7} | {'Data COM':<11} | {'Dias':<6} | {'Valor':<10} | {'DY':<7}\n"
    msg += f"{'-'*7} | {'-'*11} | {'-'*6} | {'-'*10} | {'-'*7}\n"
    
    for dados in sorted(dados_com, key=lambda x: x["dias_para_com"]):
        ticker = dados["ticker"]
        data_com = dados["data_com"]
        dias = dados["dias_para_com"]
        valor = dados["dividend_rate"]
        dy = dados["dividend_yield"]
        
        msg += f"{ticker:<7} | {data_com:<11} | {dias:>5}  | R$ {valor:>6.4f} | {dy:>6.2%}\n"
    
    msg += "```\n"
    
    return msg

def formatar_factors_detalhado(dados_factors):
    """Formata tabela detalhada de scores"""
    if not dados_factors:
        return None
    
    msg = "🛡️ *SCORE POR FATOR - DETALHADO*\n\n"
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
# RADAR PRINCIPAL
# ==============================================================================
def main():
    logger.info("="*60)
    logger.info(f"🤖 RADAR IDIV - {len(MEUS_PAPEIS)} ativos")
    logger.info("="*60)
    
    hoje = datetime.now().strftime("%d/%m/%Y")
    enviar_telegram(f"🤖 *Radar IDIV | {hoje}*\nIniciando monitoramento de {len(MEUS_PAPEIS)} ativos...")
    
    todos_dados = []
    dados_data_com = []
    alertas_gerais = []
    dados_factors_detalhado = []
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        
        # Analisa ação
        dados = analisar_acao(ticker)
        if not dados:
            continue
        
        acao = yf.Ticker(f"{ticker}.SA")
        
        # Gera alertas
        alertas = gerar_alertas(dados, acao, papel)
        for alerta in alertas:
            alertas_gerais.append({
                "ticker": ticker,
                "nome": dados["nome"],
                "tipo": alerta["tipo"],
                "mensagem": alerta["mensagem"]
            })
        
        todos_dados.append(dados)
        
        # Data COM próxima
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
        
        # Coleta dados para tabela detalhada
        score = dados.get("score_composto", {})
        if score.get("score_total", 0) > 0:
            dados_factors_detalhado.append({
                "ticker": ticker,
                "score_total": score["score_total"],
                "classificacao": score["classificacao"],
                "fatores": score["fatores"]
            })
    
    # Tabela Data COM
    if dados_data_com:
        msg_com = formatar_data_com_telegram(dados_data_com)
        if msg_com:
            enviar_telegram(msg_com)
    
    # Tabela Alertas
    if alertas_gerais:
        msg_alertas = formatar_alertas_telegram(alertas_gerais)
        if msg_alertas:
            enviar_telegram(msg_alertas)
    
    # Tabela Resumo
    if todos_dados:
        msg_tabela = formatar_tabela_telegram(todos_dados)
        if msg_tabela:
            enviar_telegram(msg_tabela)
    
    # Tabela Factors Detalhado
    if dados_factors_detalhado:
        msg_factors = formatar_factors_detalhado(dados_factors_detalhado)
        if msg_factors:
            enviar_telegram(msg_factors)
    
    # Mensagem final
    msg_final = (
        f"✅ *Monitoramento Concluído!*\n\n"
        f"📊 Ativos analisados: {len(todos_dados)}\n"
        f"🔔 Alertas de dividendos: {len(dados_data_com)}\n"
        f"📈 Alertas de fundamentos: {len(alertas_gerais)}\n"
        f"🛡️ Ativos com score > 70: {len([a for a in alertas_gerais if a['tipo'] == 'SCORE_ALTO'])}\n"
        f"📣 Total: {len(dados_data_com) + len(alertas_gerais)} alertas"
    )
    enviar_telegram(msg_final)
    
    logger.info(f"✅ Fim: {len(alertas_gerais)} alertas")

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    main()
