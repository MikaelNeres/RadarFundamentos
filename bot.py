"""
🤖 RADAR IDIV v6.0 - Monitoramento Fundamentalista
Foco: Dividendos, Recompras e Factor Investing
Fontes: Yahoo Finance (oficial)
"""

# ==============================================================================
# IMPORTS E CONFIGURAÇÕES
# ==============================================================================

import yfinance as yf
import requests
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Configuração de logs (para debug)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configurações do Telegram
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604'

# Histórico de shares (para detectar recompras entre execuções)
HISTORICO_SHARES = {}

# ==============================================================================
# SEUS ATIVOS (PERSONALIZE AQUI!)
# ==============================================================================

MEUS_ATIVOS = [
    "CMIG4", "BBAS3", "SAPR11", "ISAE4", "ABCB4", "LOGG3", "FIQE3", "GGBR4",
    "VBBR3", "SAUD3", "DEXP3", "ITSA4", "PETR4", "BBSE3", "ITUB4", "BBDC4",
    "CPLE3", "VALE3", "CSMG3", "TIMS3", "VIVT3", "CXSE3", "KLBN11", "TAEE11",
    "EGIE3", "CPFE3", "CMIN3", "BMGB4", "ALOS3", "WEGE3", "AURE3"
]

# ==============================================================================
# CONFIGURAÇÕES DE VALOR JUSTO (PERSONALIZE POR ATIVO!)
# ==============================================================================

# Configuração padrão para todos os ativos
CONFIG_PADRAO = {
    "p_l_justo": 8.0,      # P/L justo de referência
    "p_vp_justo": 1.2,     # P/VP justo de referência
    "dy_medio": 0.06       # Dividend Yield médio esperado (6%)
}

# Configurações específicas por ativo (sobrescrevem o padrão)
CONFIG_POR_TICKER = {
    "BBAS3": {"p_l_justo": 6.0, "p_vp_justo": 1.0, "dy_medio": 0.08},
    "ABCB4": {"p_l_justo": 5.0, "p_vp_justo": 0.9, "dy_medio": 0.09},
    "VBBR3": {"p_l_justo": 7.0, "p_vp_justo": 1.5, "dy_medio": 0.09},
    "PETR4": {"p_l_justo": 5.0, "p_vp_justo": 1.0, "dy_medio": 0.10},
    "VALE3": {"p_l_justo": 6.0, "p_vp_justo": 1.1, "dy_medio": 0.09},
    "ITUB4": {"p_l_justo": 9.0, "p_vp_justo": 1.5, "dy_medio": 0.07},
    "BBDC4": {"p_l_justo": 7.0, "p_vp_justo": 1.2, "dy_medio": 0.08}
}

# ==============================================================================
# ESTRUTURA DE DADOS
# ==============================================================================

# Cria a lista de ativos com suas configurações
MEUS_PAPEIS = []
for ticker in MEUS_ATIVOS:
    # Pega configuração padrão
    config = CONFIG_PADRAO.copy()
    
    # Se tiver configuração específica, sobrescreve
    if ticker in CONFIG_POR_TICKER:
        config.update(CONFIG_POR_TICKER[ticker])
    
    # Adiciona à lista
    MEUS_PAPEIS.append({
        "ticker": ticker,
        "nome": ticker,
        **config  # Expande as configurações (p_l_justo, p_vp_justo, dy_medio)
    })

# Thresholds para alertas
THRESHOLDS = {
    "dividend_yield_min": 0.06,      # Alerta se DY > 6%
    "price_target_upside": 0.20,     # Alerta se upside > 20%
    "dividend_cut": -0.20,           # Alerta se corte > 20%
    "margem_seguranca_min": 0.20     # Margem de segurança mínima
}

# Pesos dos fatores (Factor Investing)
PESOS_FATORES = {
    "quality": 0.30,    # Qualidade (30%)
    "low_vol": 0.25,    # Baixa volatilidade (25%)
    "value": 0.20,      # Valor/Desconto (20%)
    "dividend": 0.15,   # Dividendos (15%)
    "momentum": 0.10    # Momento (10%)
}

# ==============================================================================
# FUNÇÕES DE COMUNICAÇÃO
# ==============================================================================

def enviar_telegram(msg):
    """
    Envia mensagem para o Telegram
    
    Args:
        msg (str): Mensagem a ser enviada (pode usar Markdown)
    
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        dados = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        resposta = requests.post(url, json=dados, timeout=15)
        
        # Retorna True se status code for 200 (sucesso)
        return resposta.status_code == 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao enviar Telegram: {e}")
        return False

# ==============================================================================
# FUNÇÕES DE DIVIDENDOS
# ==============================================================================

def estimar_dividendo(ticker):
    """
    Estima o próximo dividendo baseado na média dos últimos 5 anos
    
    Estratégia:
    1. Pega todos os dividendos dos últimos 5 anos
    2. Agrupa por ano e calcula total anual
    3. Calcula payout médio (dividendo / LPA)
    4. Projeta dividendo futuro: LPA médio × Payout médio
    
    Args:
        ticker (str): Código do ativo (ex: "PETR4")
    
    Returns:
        tuple: (dividendo_anual, payout_medio, lpa_medio, confianca, dividendo_por_pagamento)
    """
    try:
        # Cria ticker Yahoo Finance
        acao = yf.Ticker(f"{ticker}.SA")
        
        # Pega histórico de dividendos
        dividendos = acao.dividends
        
        # Se não tem dividendos, retorna zeros
        if dividendos.empty:
            return 0, 0, 0, 0, 0
        
        # Filtra últimos 5 anos
        hoje = datetime.now()
        cinco_anos_atras = hoje - timedelta(days=5*365)
        
        # Agrupa dividendos por ano
        dividendos_por_ano = {}
        for data, valor in dividendos.items():
            # Remove timezone se tiver
            if hasattr(data, 'tzinfo'):
                data = data.replace(tzinfo=None)
            
            # Só considera últimos 5 anos
            if data >= cinco_anos_atras:
                ano = data.year
                dividendos_por_ano[ano] = dividendos_por_ano.get(ano, 0) + valor
        
        # Pega LPA (Lucro Por Ação) atual
        info = acao.info
        lpa_atual = info.get('trailingEps', 0)
        
        # Se LPA negativo ou zero, não dá para calcular payout
        if lpa_atual <= 0:
            return 0, 0, 0, 0, 0
        
        # Calcula payout médio dos últimos 5 anos
        payouts = []
        for ano, total_dividendos in dividendos_por_ano.items():
            payout = total_dividendos / lpa_atual
            payouts.append(payout)
        
        payout_medio = sum(payouts) / len(payouts) if payouts else 0.5
        
        # Limita payout entre 0 e 100%
        payout_medio = min(payout_medio, 1.0)
        
        # Projeta dividendo anual futuro
        dividendo_anual = lpa_atual * payout_medio
        
        # Calcula confiança da estimativa (0 a 1)
        confianca = 0.5  # Confiança base
        
        # Aumenta confiança se LPA positivo
        if lpa_atual > 0:
            confianca += 0.2
        
        # Aumenta confiança se payout consistente (entre 30% e 80%)
        if 0.30 <= payout_medio <= 0.80:
            confianca += 0.2
        
        # Aumenta confiança se histórico longo (mais de 20 pagamentos)
        if len(dividendos) >= 20:
            confianca += 0.1
        
        # Limita confiança a 100%
        confianca = min(confianca, 1.0)
        
        # Estima frequência de pagamentos
        # Conta quantos pagamentos teve nos últimos 12 meses
        doze_meses_atras = hoje - timedelta(days=365)
        pagamentos_12m = sum(
            1 for d in dividendos.index 
            if (d.replace(tzinfo=None) if hasattr(d, 'tzinfo') else d) >= doze_meses_atras
        )
        
        # Define frequência baseada em pagamentos
        if pagamentos_12m >= 4:
            frequencia = 4  # Trimestral
        elif pagamentos_12m >= 2:
            frequencia = 2  # Semestral
        else:
            frequencia = 1  # Anual
        
        # Calcula dividendo por pagamento
        dividendo_por_pagamento = dividendo_anual / frequencia
        
        return dividendo_anual, payout_medio, lpa_atual, confianca, dividendo_por_pagamento
    
    except Exception as e:
        logger.error(f"❌ Erro ao estimar dividendo {ticker}: {e}")
        return 0, 0, 0, 0, 0

# ==============================================================================
# FUNÇÕES DE RECOMPRAS
# ==============================================================================

def detectar_recompra(ticker):
    """
    Detecta se a empresa está recomprando ações
    
    Estratégia:
    1. Pega shares outstanding (ações em circulação) atual
    2. Compara com balanço trimestral anterior
    3. Se reduziu > 2%, é recompra
    4. Compara também com histórico do bot (última execução)
    
    Args:
        ticker (str): Código do ativo
    
    Returns:
        dict: Dados da recompra ou None se não detectada
    """
    try:
        # Cria ticker
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        # Pega shares outstanding atual (ações em circulação)
        shares_atual = info.get('sharesOutstanding', 0)
        
        # Se não tem dados, retorna None
        if shares_atual <= 0:
            return None
        
        # ======================================================================
        # MÉTODO 1: Comparar com balanço trimestral
        # ======================================================================
        try:
            balanco = acao.quarterly_balance_sheet
            
            # Se tem balanço e tem pelo menos 2 períodos
            if balanco is not None and not balanco.empty and len(balanco.columns) >= 2:
                # Procura linha de "Common Stock" ou "Capital Stock"
                for indice in balanco.index:
                    if 'Common Stock' in indice or 'Capital Stock' in indice:
                        shares_balanco = balanco.loc[indice]
                        
                        # Se tem pelo menos 2 períodos
                        if len(shares_balanco) >= 2:
                            shares_antigo = shares_balanco.iloc[-1]  # Período mais antigo
                            shares_novo = shares_balanco.iloc[0]     # Período mais recente
                            
                            # Calcula variação
                            if shares_antigo > 0:
                                variacao = (shares_novo - shares_antigo) / shares_antigo
                                
                                # Se reduziu mais de 2%, é recompra
                                if variacao < -0.02:
                                    confianca = 'Alta' if variacao < -0.05 else 'Média'
                                    
                                    return {
                                        'ticker': ticker,
                                        'status': 'Recompra Detectada',
                                        'shares_atual': shares_atual,
                                        'shares_antigo': shares_antigo,
                                        'shares_novo': shares_novo,
                                        'variacao': variacao,
                                        'confianca': confianca,
                                        'fonte': 'Balanço Trimestral'
                                    }
        except Exception as e:
            logger.debug(f"Sem balanço para {ticker}: {e}")
        
        # ======================================================================
        # MÉTODO 2: Comparar com histórico do bot (última execução)
        # ======================================================================
        if ticker in HISTORICO_SHARES:
            shares_observacao_anterior = HISTORICO_SHARES[ticker]
            
            if shares_observacao_anterior > 0:
                variacao = (shares_atual - shares_observacao_anterior) / shares_observacao_anterior
                
                # Se reduziu mais de 1% desde última observação
                if variacao < -0.01:
                    return {
                        'ticker': ticker,
                        'status': 'Recompra em Andamento',
                        'shares_atual': shares_atual,
                        'shares_antigo': shares_observacao_anterior,
                        'variacao': variacao,
                        'confianca': 'Média',
                        'fonte': 'Observação Automática'
                    }
        
        # Atualiza histórico com shares atual
        HISTORICO_SHARES[ticker] = shares_atual
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Erro ao detectar recompra {ticker}: {e}")
        return None

# ==============================================================================
# FUNÇÕES DE ANÁLISE FUNDAMENTISTA
# ==============================================================================

def analisar_ativo(ticker):
    """
    Analisa um ativo e retorna dados fundamentalistas
    
    Args:
        ticker (str): Código do ativo
    
    Returns:
        dict: Dados fundamentalistas ou None se erro
    """
    try:
        # Cria ticker
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        # Preço atual
        preco = info.get('currentPrice', info.get('regularMarketPrice', 0))
        
        # Dividendos dos últimos 12 meses
        dividendos = acao.dividends
        doze_meses_atras = datetime.now() - timedelta(days=365)
        
        dividendos_12m = sum(
            valor for data, valor in dividendos.items()
            if (data.replace(tzinfo=None) if hasattr(data, 'tzinfo') else data) >= doze_meses_atras
        ) if not dividendos.empty else 0
        
        # Dividend Yield
        dividend_yield = dividendos_12m / preco if preco > 0 else 0
        
        # Estimativa de dividendo futuro
        div_anual, payout, lpa, confianca, proximo = estimar_dividendo(ticker)
        
        # LPA (Earnings Per Share)
        eps = info.get('trailingEps', 0)
        
        # Payout Ratio
        payout_ratio = min(dividendos_12m / eps, 1.0) if eps > 0 else 0
        
        # Monta dicionário com todos os dados
        dados = {
            "ticker": ticker,
            "nome": info.get('longName', ticker),
            "preco": preco,
            "dividend_yield": dividend_yield,
            "dividendos_12m": dividendos_12m,
            "proximo_dividendo": proximo,
            "confianca": confianca,
            "ex_dividend_date": info.get('exDividendDate'),
            "payout_ratio": payout_ratio,
            "pe_ratio": info.get('trailingPE', 0),
            "pb_ratio": info.get('priceToBook', 0),
            "eps": eps,
            "price_target": info.get('targetMeanPrice', 0),
            "beta": info.get('beta', 1.0),
            "roe": info.get('returnOnEquity', 0),
            "margem": info.get('profitMargins', 0),
            "divida_equity": info.get('debtToEquity', 0),
            "crescimento": info.get('revenueGrowth', 0),
            "upside": (info.get('targetMeanPrice', 0) - preco) / preco if preco > 0 and info.get('targetMeanPrice', 0) > 0 else 0
        }
        
        return dados
    
    except Exception as e:
        logger.error(f"❌ Erro ao analisar {ticker}: {e}")
        return None

# ==============================================================================
# FUNÇÕES DE FACTOR INVESTING
# ==============================================================================

def calcular_score(dados, historico, config):
    """
    Calcula score de Factor Investing (0-100)
    
    Fatores:
    - Quality (30%): ROE, Payout, Margem, Dívida, Crescimento
    - Low Vol (25%): Beta, Volatilidade, Drawdown
    - Value (20%): P/L, P/VP, EV/EBITDA
    - Dividend (15%): DY, Payout, Consistência
    - Momentum (10%): Retorno 6m, Distância do topo
    
    Args:
        dados (dict): Dados fundamentalistas
        historico (DataFrame): Histórico de preços (6 meses)
        config (dict): Configurações do ativo
    
    Returns:
        dict: Score total, classificação e scores por fator
    """
    
    # ==========================================================================
    # FATOR 1: QUALITY (30%)
    # ==========================================================================
    roe = dados.get("roe", 0)
    payout = dados.get("payout_ratio", 0)
    margem = dados.get("margem", 0)
    divida = dados.get("divida_equity", 0)
    crescimento = dados.get("crescimento", 0)
    
    # Score de ROE (Retorno sobre Equity)
    if roe > 0.20:
        score_roe = 100
    elif roe > 0.15:
        score_roe = 80
    elif roe > 0.10:
        score_roe = 60
    elif roe > 0.05:
        score_roe = 40
    else:
        score_roe = 20
    
    # Score de Payout (ideal: 30-60%)
    if 0.30 <= payout <= 0.60:
        score_payout = 100
    elif 0.20 <= payout <= 0.70:
        score_payout = 80
    elif 0.10 <= payout <= 0.80:
        score_payout = 60
    else:
        score_payout = 40
    
    # Score de Margem de Lucro
    if margem > 0.20:
        score_margem = 100
    elif margem > 0.15:
        score_margem = 80
    elif margem > 0.10:
        score_margem = 60
    elif margem > 0.05:
        score_margem = 40
    else:
        score_margem = 20
    
    # Score de Dívida/Equity (menor é melhor)
    if divida < 0.5:
        score_divida = 100
    elif divida < 1.0:
        score_divida = 80
    elif divida < 1.5:
        score_divida = 60
    elif divida < 2.0:
        score_divida = 40
    else:
        score_divida = 20
    
    # Score de Crescimento de Receita
    if crescimento > 0.15:
        score_crescimento = 100
    elif crescimento > 0.10:
        score_crescimento = 80
    elif crescimento > 0.05:
        score_crescimento = 60
    elif crescimento > 0:
        score_crescimento = 40
    else:
        score_crescimento = 20
    
    # Score composto de Quality (média ponderada)
    score_quality = (
        score_roe * 0.30 +
        score_payout * 0.20 +
        score_margem * 0.20 +
        score_divida * 0.20 +
        score_crescimento * 0.10
    )
    
    # ==========================================================================
    # FATOR 2: LOW VOLATILITY (25%)
    # ==========================================================================
    beta = dados.get("beta", 1.0)
    
    # Score de Beta (menor = menos volátil)
    if beta < 0.8:
        score_beta = 100
    elif beta < 1.0:
        score_beta = 80
    elif beta < 1.2:
        score_beta = 60
    elif beta < 1.5:
        score_beta = 40
    else:
        score_beta = 20
    
    # Volatilidade anualizada
    try:
        volatilidade = historico['Close'].pct_change().std() * np.sqrt(252) if len(historico) > 0 else 0.5
    except:
        volatilidade = 0.5
    
    if volatilidade < 0.20:
        score_vol = 100
    elif volatilidade < 0.30:
        score_vol = 80
    elif volatilidade < 0.40:
        score_vol = 60
    elif volatilidade < 0.50:
        score_vol = 40
    else:
        score_vol = 20
    
    # Drawdown (queda do topo)
    try:
        drawdown = (historico['Close'].max() - historico['Close'].iloc[-1]) / historico['Close'].max() if len(historico) > 0 else 0.5
    except:
        drawdown = 0.5
    
    if drawdown < 0.10:
        score_dd = 100
    elif drawdown < 0.20:
        score_dd = 80
    elif drawdown < 0.30:
        score_dd = 60
    elif drawdown < 0.40:
        score_dd = 40
    else:
        score_dd = 20
    
    # Score composto de Low Vol
    score_low_vol = (
        score_beta * 0.40 +
        score_vol * 0.30 +
        score_dd * 0.30
    )
    
    # ==========================================================================
    # FATOR 3: VALUE (20%)
    # ==========================================================================
    pe = dados.get("pe_ratio", 0)
    pvp = dados.get("pb_ratio", 0)
    ev_ebitda = dados.get("ev_ebitda", 0)
    
    p_l_justo = config.get("p_l_justo", 8.0)
    p_vp_justo = config.get("p_vp_justo", 1.2)
    
    # Score de P/L (quanto menor, mais barato)
    if pe > 0 and pe < p_l_justo * 0.5:
        score_pe = 100
    elif pe > 0 and pe < p_l_justo * 0.75:
        score_pe = 80
    elif pe > 0 and pe < p_l_justo:
        score_pe = 60
    elif pe > 0 and pe < p_l_justo * 1.25:
        score_pe = 40
    else:
        score_pe = 20
    
    # Score de P/VP
    if pvp > 0 and pvp < p_vp_justo * 0.5:
        score_pvp = 100
    elif pvp > 0 and pvp < p_vp_justo * 0.75:
        score_pvp = 80
    elif pvp > 0 and pvp < p_vp_justo:
        score_pvp = 60
    elif pvp > 0 and pvp < p_vp_justo * 1.25:
        score_pvp = 40
    else:
        score_pvp = 20
    
    # Score de EV/EBITDA
    if ev_ebitda > 0 and ev_ebitda < 5:
        score_ev = 100
    elif ev_ebitda > 0 and ev_ebitda < 8:
        score_ev = 80
    elif ev_ebitda > 0 and ev_ebitda < 12:
        score_ev = 60
    elif ev_ebitda > 0 and ev_ebitda < 15:
        score_ev = 40
    else:
        score_ev = 20
    
    # Score composto de Value
    score_value = (
        score_pe * 0.40 +
        score_pvp * 0.30 +
        score_ev * 0.30
    )
    
    # ==========================================================================
    # FATOR 4: DIVIDEND (15%)
    # ==========================================================================
    dy = dados.get("dividend_yield", 0)
    
    # Score de Dividend Yield
    if dy > 0.10:
        score_dy = 100
    elif dy > 0.08:
        score_dy = 80
    elif dy > 0.06:
        score_dy = 60
    elif dy > 0.04:
        score_dy = 40
    else:
        score_dy = 20
    
    # Score de Payout (já calculado em Quality)
    score_payout_div = score_payout
    
    # Score de consistência (DY atual vs média 5 anos)
    dy_medio = config.get("dy_medio", 0.06)
    if dy >= dy_medio:
        score_consistencia = 100
    elif dy >= dy_medio * 0.8:
        score_consistencia = 80
    else:
        score_consistencia = 60
    
    # Score composto de Dividend
    score_dividend = (
        score_dy * 0.50 +
        score_payout_div * 0.30 +
        score_consistencia * 0.20
    )
    
    # ==========================================================================
    # FATOR 5: MOMENTUM (10%)
    # ==========================================================================
    try:
        retorno_6m = (historico['Close'].iloc[-1] - historico['Close'].iloc[0]) / historico['Close'].iloc[0] if len(historico) > 0 else 0
    except:
        retorno_6m = 0
    
    if retorno_6m > 0.30:
        score_retorno = 100
    elif retorno_6m > 0.15:
        score_retorno = 80
    elif retorno_6m > 0:
        score_retorno = 60
    elif retorno_6m > -0.15:
        score_retorno = 40
    else:
        score_retorno = 20
    
    # Distância do topo (quanto menor, melhor momentum)
    try:
        distancia_topo = (historico['Close'].iloc[-1] - historico['Close'].max()) / historico['Close'].max() if len(historico) > 0 else 0
    except:
        distancia_topo = 0
    
    if distancia_topo > -0.10:
        score_dist = 100
    elif distancia_topo > -0.20:
        score_dist = 80
    elif distancia_topo > -0.30:
        score_dist = 60
    elif distancia_topo > -0.40:
        score_dist = 40
    else:
        score_dist = 20
    
    # Score composto de Momentum
    score_momentum = (
        score_retorno * 0.60 +
        score_dist * 0.40
    )
    
    # ==========================================================================
    # SCORE TOTAL (média ponderada dos 5 fatores)
    # ==========================================================================
    score_total = (
        score_quality * PESOS_FATORES["quality"] +
        score_low_vol * PESOS_FATORES["low_vol"] +
        score_value * PESOS_FATORES["value"] +
        score_dividend * PESOS_FATORES["dividend"] +
        score_momentum * PESOS_FATORES["momentum"]
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
            "quality": {"score": score_quality},
            "low_vol": {"score": score_low_vol},
            "value": {"score": score_value},
            "dividend": {"score": score_dividend},
            "momentum": {"score": score_momentum}
        }
    }

# ==============================================================================
# FUNÇÃO PRINCIPAL
# ==============================================================================

def main():
    """
    Função principal do bot
    
    Fluxo:
    1. Inicializa e envia mensagem de início
    2. Para cada ativo:
       - Analisa dados fundamentalistas
       - Detecta recompras
       - Verifica alertas (Data COM, Score, DY)
    3. Envia tabelas e alertas
    4. Envia resumo final
    """
    
    logger.info("="*60)
    logger.info(f"🤖 RADAR IDIV v6.0 - {len(MEUS_PAPEIS)} ativos")
    logger.info("="*60)
    
    # Envia mensagem de início
    hoje = datetime.now().strftime("%d/%m/%Y")
    enviar_telegram(
        f"🤖 *Radar IDIV | {hoje}*\n"
        f"Iniciando monitoramento de {len(MEUS_PAPEIS)} ativos..."
    )
    
    # Listas para acumular dados
    todos_dados = []
    dados_data_com = []
    alertas = []
    todas_recompras = []
    
    # Verifica rotinas (diária, semanal, mensal)
    hoje_semana = datetime.now().weekday()
    hoje_dia = datetime.now().day
    
    e_segunda = hoje_semana == 0  # Segunda-feira
    e_primeiro_dia = hoje_dia <= 3  # Primeiros 3 dias do mês
    
    # ==========================================================================
    # LOOP PRINCIPAL: Analisa cada ativo
    # ==========================================================================
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        logger.info(f"📊 Analisando {ticker}...")
        
        # Analisa ativo
        dados = analisar_ativo(ticker)
        if not dados:
            logger.warning(f"⚠️ Sem dados para {ticker}")
            continue
        
        # Pega histórico de preços (6 meses para cálculos)
        acao = yf.Ticker(f"{ticker}.SA")
        historico = acao.history(period="6mo")
        
        # ----------------------------------------------------------------------
        # DETECTA RECOMPRAS
        # ----------------------------------------------------------------------
        recompra = detectar_recompra(ticker)
        if recompra:
            todas_recompras.append(recompra)
            logger.info(f"✅ {ticker}: Recompra detectada ({recompra['variacao']:.1%})")
        
        # ----------------------------------------------------------------------
        # VERIFICA DATA COM (próximos 15 dias)
        # ----------------------------------------------------------------------
        if dados.get("proximo_dividendo", 0) > 0 and dados.get("ex_dividend_date"):
            data_com = datetime.fromtimestamp(dados["ex_dividend_date"])
            dias_para_data_com = (data_com - datetime.now()).days
            
            # Se Data COM é nos próximos 15 dias
            if 0 <= dias_para_data_com <= 15:
                dados_data_com.append({
                    **dados,
                    "data_com": data_com.strftime("%d/%m/%Y"),
                    "dias": dias_para_data_com
                })
        
        # ----------------------------------------------------------------------
        # CALCULA SCORE (apenas nos primeiros dias do mês)
        # ----------------------------------------------------------------------
        if e_primeiro_dia:
            score = calcular_score(dados, historico, papel)
            dados["score"] = score
            
            # Alerta se score alto (>= 70)
            if score["score_total"] >= 70:
                alertas.append(
                    f"🟢 *SCORE ALTO - {ticker}*\n"
                    f"Score: {score['score_total']:.0f}/100 ({score['classificacao']})"
                )
        
        # ----------------------------------------------------------------------
        # ALERTA DE DIVIDEND YIELD (apenas às segundas)
        # ----------------------------------------------------------------------
        if e_segunda and dados["dividend_yield"] > 0.06:
            alertas.append(
                f"🟢 *DY ATRAENTE - {ticker}*\n"
                f"Dividend Yield: {dados['dividend_yield']:.2%}"
            )
        
        # Adiciona à lista de todos os dados
        todos_dados.append(dados)
    
    # ==========================================================================
    # ENVIA TABELA DE DATA COM
    # ==========================================================================
    if dados_data_com:
        msg = "💰 *DATA COM PRÓXIMA*\n"
        msg += "Fonte: Estimativa Payout × LPA\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Data COM':<11} | {'Dias':<6} | {'Estimado':<10} | {'DY':<7}\n"
        msg += f"{'-'*47}\n"
        
        # Ordena por dias (mais próximos primeiro)
        for d in sorted(dados_data_com, key=lambda x: x["dias"]):
            msg += (
                f"{d['ticker']:<7} | "
                f"{d['data_com']:<11} | "
                f"{d['dias']:>5}  | "
                f"R$ {d['proximo_dividendo']:>6.4f} | "
                f"{d['dividend_yield']:>6.2%}\n"
            )
        
        msg += "```"
        enviar_telegram(msg)
    
    # ==========================================================================
    # ENVIA TABELA DE RECOMPRAS
    # ==========================================================================
    if todas_recompras:
        msg = "🔁 *RECOMPRAS DETECTADAS*\n"
        msg += "Variação de Shares Outstanding\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Status':<22} | {'Variação':<10} | {'Shares':<20}\n"
        msg += f"{'-'*63}\n"
        
        for r in todas_recompras:
            variacao = f"{r['variacao']:.1%}"
            
            if 'shares_novo' in r:
                shares = f"{r['shares_antigo']/1e9:.2f}B→{r['shares_novo']/1e9:.2f}B"
            else:
                shares = f"{r['shares_antigo']/1e9:.2f}B→{r['shares_atual']/1e9:.2f}B"
            
            msg += (
                f"{r['ticker']:<7} | "
                f"{r['status']:<22} | "
                f"{variacao:<10} | "
                f"{shares:<20}\n"
            )
        
        msg += "```\n"
        msg += "\n🟢 Recompras reduzem shares e aumentam LPA futuro!"
        enviar_telegram(msg)
    
    # ==========================================================================
    # ENVIA ALERTAS (Score, DY, etc)
    # ==========================================================================
    for alerta in alertas:
        enviar_telegram(alerta)
    
    # ==========================================================================
    # ENVIA RESUMO DIÁRIO
    # ==========================================================================
    if todos_dados:
        msg = "📊 *RESUMO DIÁRIO*\n"
        msg += hoje + "\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Preço':<8} | {'DY':<7} | {'P/L':<6} | {'P/VP':<6} | {'Status':<7}\n"
        msg += f"{'-'*47}\n"
        
        # Ordena por Dividend Yield (maior primeiro)
        for d in sorted(todos_dados, key=lambda x: x.get('dividend_yield', 0), reverse=True):
            # Ícone baseado no DY
            if d['dividend_yield'] > 0.06:
                icone = "🟢"
            elif d['dividend_yield'] > 0.04:
                icone = "🟡"
            else:
                icone = "🔴"
            
            # Status baseado em DY e P/L
            if d['dividend_yield'] > 0.06 and d['pe_ratio'] < 8:
                status = "🟢 Buy"
            elif d['dividend_yield'] > 0.04:
                status = "🟡 Hold"
            else:
                status = "🔴 Sell"
            
            msg += (
                f"{d['ticker']:<7} | "
                f"R$ {d['preco']:>5.2f} | "
                f"{d['dividend_yield']:>6.1%} {icone} | "
                f"{d['pe_ratio']:>5.2f} | "
                f"{d['pb_ratio']:>5.2f} | "
                f"{status:<7}\n"
            )
        
        msg += "```\n"
        msg += "\n🟢 DY > 6%  |  🟡 DY 4-6%  |  🔴 DY < 4%"
        enviar_telegram(msg)
    
    # ==========================================================================
    # MENSAGEM FINAL
    # ==========================================================================
    enviar_telegram(
        f"✅ *Monitoramento Concluído!*\n\n"
        f"📊 Ativos analisados: {len(todos_dados)}\n"
        f"💰 Data COM: {len(dados_data_com)}\n"
        f"🔁 Recompras: {len(todas_recompras)}\n"
        f"📈 Alertas: {len(alertas)}"
    )
    
    logger.info(f"✅ Fim: {len(alertas)} alertas enviados")

# ==============================================================================
# EXECUTA O BOT
# ==============================================================================

if __name__ == "__main__":
    main()
