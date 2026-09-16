"""
🤖 RADAR IDIV v7.0 - Monitoramento Fundamentalista
Foco: Dividendos, Recompras (CVM) e Factor Investing
Fontes: Yahoo Finance + CVM Dados Abertos
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
from io import StringIO

# Configuração de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configurações do Telegram
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604'

# Cache para recompras CVM (atualiza a cada 24h)
CACHE_RECOMPRAS = {"dados": None, "data": None}

# ==============================================================================
# SEUS ATIVOS (PERSONALIZE AQUI!)
# ==============================================================================

MEUS_ATIVOS = [
    "CMIG4", "BBAS3", "SAPR11", "ISAE4", "ABCB4", "LOGG3", "FIQE3", "GGBR4",
    "VBBR3", "SAUD3", "DEXP3", "ITSA4", "PETR4", "BBSE3", "ITUB4", "BBDC4",
    "CPLE3", "VALE3", "CSMG3", "TIMS3", "VIVT3", "CXSE3", "KLBN11", "TAEE11",
    "EGIE3", "CPFE3", "CMIN3", "BMGB4", "ALOS3", "WEGE3", "AURE3"
]

# Configurações de valor justo
CONFIG_PADRAO = {
    "p_l_justo": 8.0,
    "p_vp_justo": 1.2,
    "dy_medio": 0.06
}

CONFIG_POR_TICKER = {
    "BBAS3": {"p_l_justo": 6.0, "p_vp_justo": 1.0, "dy_medio": 0.08},
    "ABCB4": {"p_l_justo": 5.0, "p_vp_justo": 0.9, "dy_medio": 0.09},
    "VBBR3": {"p_l_justo": 7.0, "p_vp_justo": 1.5, "dy_medio": 0.09},
    "PETR4": {"p_l_justo": 5.0, "p_vp_justo": 1.0, "dy_medio": 0.10},
    "VALE3": {"p_l_justo": 6.0, "p_vp_justo": 1.1, "dy_medio": 0.09},
    "ITUB4": {"p_l_justo": 9.0, "p_vp_justo": 1.5, "dy_medio": 0.07},
    "BBDC4": {"p_l_justo": 7.0, "p_vp_justo": 1.2, "dy_medio": 0.08}
}

# Cria lista de ativos com configurações
MEUS_PAPEIS = []
for ticker in MEUS_ATIVOS:
    config = CONFIG_PADRAO.copy()
    if ticker in CONFIG_POR_TICKER:
        config.update(CONFIG_POR_TICKER[ticker])
    MEUS_PAPEIS.append({
        "ticker": ticker,
        "nome": ticker,
        **config
    })

# Pesos dos fatores
PESOS_FATORES = {
    "quality": 0.30,
    "low_vol": 0.25,
    "value": 0.20,
    "dividend": 0.15,
    "momentum": 0.10
}

# ==============================================================================
# FUNÇÕES DE COMUNICAÇÃO
# ==============================================================================

def enviar_telegram(msg):
    """Envia mensagem para o Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        dados = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        resposta = requests.post(url, json=dados, timeout=15)
        return resposta.status_code == 200
    except Exception as e:
        logger.error(f"❌ Erro ao enviar Telegram: {e}")
        return False

# ==============================================================================
# FUNÇÕES DE DIVIDENDOS
# ==============================================================================

def estimar_dividendo(ticker):
    """Estima próximo dividendo baseado na média dos últimos 5 anos"""
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        dividendos = acao.dividends
        
        if dividendos.empty:
            return 0, 0, 0, 0, 0
        
        hoje = datetime.now()
        cinco_anos_atras = hoje - timedelta(days=5*365)
        
        dividendos_por_ano = {}
        for data, valor in dividendos.items():
            if hasattr(data, 'tzinfo'):
                data = data.replace(tzinfo=None)
            if data >= cinco_anos_atras:
                ano = data.year
                dividendos_por_ano[ano] = dividendos_por_ano.get(ano, 0) + valor
        
        info = acao.info
        lpa_atual = info.get('trailingEps', 0)
        
        if lpa_atual <= 0:
            return 0, 0, 0, 0, 0
        
        payouts = []
        for ano, total_dividendos in dividendos_por_ano.items():
            payout = total_dividendos / lpa_atual
            payouts.append(payout)
        
        payout_medio = sum(payouts) / len(payouts) if payouts else 0.5
        payout_medio = min(payout_medio, 1.0)
        
        dividendo_anual = lpa_atual * payout_medio
        
        confianca = 0.5
        if lpa_atual > 0:
            confianca += 0.2
        if 0.30 <= payout_medio <= 0.80:
            confianca += 0.2
        if len(dividendos) >= 20:
            confianca += 0.1
        confianca = min(confianca, 1.0)
        
        doze_meses_atras = hoje - timedelta(days=365)
        pagamentos_12m = sum(
            1 for d in dividendos.index 
            if (d.replace(tzinfo=None) if hasattr(d, 'tzinfo') else d) >= doze_meses_atras
        )
        
        if pagamentos_12m >= 4:
            frequencia = 4
        elif pagamentos_12m >= 2:
            frequencia = 2
        else:
            frequencia = 1
        
        dividendo_por_pagamento = dividendo_anual / frequencia
        
        return dividendo_anual, payout_medio, lpa_atual, confianca, dividendo_por_pagamento
    
    except Exception as e:
        logger.error(f"❌ Erro ao estimar dividendo {ticker}: {e}")
        return 0, 0, 0, 0, 0

# ==============================================================================
# FUNÇÕES DE RECOMPRAS (CVM DADOS ABERTOS)
# ==============================================================================

def baixar_programas_recompra_cvm():
    """
    Baixa lista oficial de programas de recompra da CVM
    Fonte: https://dados.cvm.gov.br/dataset/cia_aberta-eventos-recompra_acoes
    """
    global CACHE_RECOMPRAS
    
    hoje = datetime.now()
    if CACHE_RECOMPRAS["dados"] is not None and CACHE_RECOMPRAS["data"] is not None:
        if (hoje - CACHE_RECOMPRAS["data"]).total_seconds() < 86400:
            logger.debug("✅ Usando cache de recompras CVM")
            return CACHE_RECOMPRAS["dados"]
    
    try:
        url = "https://dados.cvm.gov.br/dados/mercado/empresas/listadas/eventos/recompra_acoes.csv"
        
        logger.info("📥 Baixando programas de recompra da CVM...")
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        df = pd.read_csv(StringIO(response.text), sep=';', encoding='latin-1', low_memory=False)
        
        CACHE_RECOMPRAS["dados"] = df
        CACHE_RECOMPRAS["data"] = hoje
        
        logger.info(f"✅ {len(df)} programas de recompra carregados")
        
        return df
    
    except Exception as e:
        logger.error(f"❌ Erro ao baixar recompras CVM: {e}")
        
        if CACHE_RECOMPRAS["dados"] is not None:
            logger.warning("⚠️ Usando cache antigo como fallback")
            return CACHE_RECOMPRAS["dados"]
        
        return None

def detectar_recompra(ticker, programas_cvm=None):
    """
    Verifica se ticker tem programa de recompra ATIVO na CVM
    """
    try:
        if programas_cvm is None:
            programas_cvm = baixar_programas_recompra_cvm()
        
        if programas_cvm is None:
            logger.warning(f"⚠️ Sem dados CVM para {ticker}")
            return None
        
        programas_ativos = programas_cvm[programas_cvm['STATUS_PROGRAMA'] == 'ATIVO']
        
        ticker_upper = ticker.upper()
        
        for idx, programa in programas_ativos.iterrows():
            denom = str(programa.get('DENOM_SOCIAL', '')).upper()
            
            if ticker_upper[:4] in denom or ticker_upper in denom:
                try:
                    dt_fim = pd.to_datetime(programa.get('DT_FIM_PROGRAMA'))
                    dias_restantes = (dt_fim - datetime.now()).days
                except:
                    dias_restantes = None
                
                try:
                    qtd_max = float(programa.get('QTDE_MAX_ACOES', 0))
                except:
                    qtd_max = 0
                
                try:
                    valor_max = float(programa.get('VALOR_MAX_PROGRAMA', 0))
                except:
                    valor_max = 0
                
                return {
                    'ticker': ticker,
                    'status': 'Programa Ativo CVM',
                    'empresa': programa.get('DENOM_SOCIAL', ticker),
                    'dt_inicio': programa.get('DT_INICIO_PROGRAMA'),
                    'dt_fim': programa.get('DT_FIM_PROGRAMA'),
                    'dias_restantes': dias_restantes,
                    'qtd_max_acoes': qtd_max,
                    'valor_max': valor_max,
                    'confianca': 'Alta',
                    'fonte': 'CVM Dados Abertos'
                }
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Erro ao detectar recompra {ticker}: {e}")
        return None

# ==============================================================================
# FUNÇÕES DE ANÁLISE FUNDAMENTISTA
# ==============================================================================

def analisar_ativo(ticker):
    """Analisa um ativo e retorna dados fundamentalistas"""
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        preco = info.get('currentPrice', info.get('regularMarketPrice', 0))
        
        dividendos = acao.dividends
        doze_meses_atras = datetime.now() - timedelta(days=365)
        
        dividendos_12m = sum(
            valor for data, valor in dividendos.items()
            if (data.replace(tzinfo=None) if hasattr(data, 'tzinfo') else data) >= doze_meses_atras
        ) if not dividendos.empty else 0
        
        dividend_yield = dividendos_12m / preco if preco > 0 else 0
        
        div_anual, payout, lpa, confianca, proximo = estimar_dividendo(ticker)
        
        eps = info.get('trailingEps', 0)
        payout_ratio = min(dividendos_12m / eps, 1.0) if eps > 0 else 0
        
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
    """Calcula score de Factor Investing (0-100)"""
    
    # Quality (30%)
    roe = dados.get("roe", 0)
    payout = dados.get("payout_ratio", 0)
    margem = dados.get("margem", 0)
    divida = dados.get("divida_equity", 0)
    crescimento = dados.get("crescimento", 0)
    
    score_roe = 100 if roe > 0.20 else 80 if roe > 0.15 else 60 if roe > 0.10 else 40 if roe > 0.05 else 20
    score_payout = 100 if 0.30 <= payout <= 0.60 else 80 if 0.20 <= payout <= 0.70 else 60 if 0.10 <= payout <= 0.80 else 40
    score_margem = 100 if margem > 0.20 else 80 if margem > 0.15 else 60 if margem > 0.10 else 40 if margem > 0.05 else 20
    score_divida = 100 if divida < 0.5 else 80 if divida < 1.0 else 60 if divida < 1.5 else 40 if divida < 2.0 else 20
    score_crescimento = 100 if crescimento > 0.15 else 80 if crescimento > 0.10 else 60 if crescimento > 0.05 else 40 if crescimento > 0 else 20
    
    score_quality = score_roe * 0.30 + score_payout * 0.20 + score_margem * 0.20 + score_divida * 0.20 + score_crescimento * 0.10
    
    # Low Vol (25%)
    beta = dados.get("beta", 1.0)
    score_beta = 100 if beta < 0.8 else 80 if beta < 1.0 else 60 if beta < 1.2 else 40 if beta < 1.5 else 20
    
    try:
        volatilidade = historico['Close'].pct_change().std() * np.sqrt(252) if len(historico) > 0 else 0.5
    except:
        volatilidade = 0.5
    
    score_vol = 100 if volatilidade < 0.20 else 80 if volatilidade < 0.30 else 60 if volatilidade < 0.40 else 40 if volatilidade < 0.50 else 20
    
    try:
        drawdown = (historico['Close'].max() - historico['Close'].iloc[-1]) / historico['Close'].max() if len(historico) > 0 else 0.5
    except:
        drawdown = 0.5
    
    score_dd = 100 if drawdown < 0.10 else 80 if drawdown < 0.20 else 60 if drawdown < 0.30 else 40 if drawdown < 0.40 else 20
    
    score_low_vol = score_beta * 0.40 + score_vol * 0.30 + score_dd * 0.30
    
    # Value (20%)
    pe = dados.get("pe_ratio", 0)
    pvp = dados.get("pb_ratio", 0)
    ev_ebitda = dados.get("ev_ebitda", 0)
    
    p_l_justo = config.get("p_l_justo", 8.0)
    p_vp_justo = config.get("p_vp_justo", 1.2)
    
    score_pe = 100 if pe > 0 and pe < p_l_justo * 0.5 else 80 if pe > 0 and pe < p_l_justo * 0.75 else 60 if pe > 0 and pe < p_l_justo else 40 if pe > 0 and pe < p_l_justo * 1.25 else 20
    score_pvp = 100 if pvp > 0 and pvp < p_vp_justo * 0.5 else 80 if pvp > 0 and pvp < p_vp_justo * 0.75 else 60 if pvp > 0 and pvp < p_vp_justo else 40 if pvp > 0 and pvp < p_vp_justo * 1.25 else 20
    score_ev = 100 if ev_ebitda > 0 and ev_ebitda < 5 else 80 if ev_ebitda > 0 and ev_ebitda < 8 else 60 if ev_ebitda > 0 and ev_ebitda < 12 else 40 if ev_ebitda > 0 and ev_ebitda < 15 else 20
    
    score_value = score_pe * 0.40 + score_pvp * 0.30 + score_ev * 0.30
    
    # Dividend (15%)
    dy = dados.get("dividend_yield", 0)
    score_dy = 100 if dy > 0.10 else 80 if dy > 0.08 else 60 if dy > 0.06 else 40 if dy > 0.04 else 20
    
    dy_medio = config.get("dy_medio", 0.06)
    score_consistencia = 100 if dy >= dy_medio else 80 if dy >= dy_medio * 0.8 else 60
    
    score_dividend = score_dy * 0.50 + score_payout * 0.30 + score_consistencia * 0.20
    
    # Momentum (10%)
    try:
        retorno_6m = (historico['Close'].iloc[-1] - historico['Close'].iloc[0]) / historico['Close'].iloc[0] if len(historico) > 0 else 0
    except:
        retorno_6m = 0
    
    score_retorno = 100 if retorno_6m > 0.30 else 80 if retorno_6m > 0.15 else 60 if retorno_6m > 0 else 40 if retorno_6m > -0.15 else 20
    
    try:
        distancia_topo = (historico['Close'].iloc[-1] - historico['Close'].max()) / historico['Close'].max() if len(historico) > 0 else 0
    except:
        distancia_topo = 0
    
    score_dist = 100 if distancia_topo > -0.10 else 80 if distancia_topo > -0.20 else 60 if distancia_topo > -0.30 else 40 if distancia_topo > -0.40 else 20
    
    score_momentum = score_retorno * 0.60 + score_dist * 0.40
    
    # Score Total
    score_total = score_quality * PESOS_FATORES["quality"] + score_low_vol * PESOS_FATORES["low_vol"] + score_value * PESOS_FATORES["value"] + score_dividend * PESOS_FATORES["dividend"] + score_momentum * PESOS_FATORES["momentum"]
    
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
    """Função principal do bot"""
    
    logger.info("="*60)
    logger.info(f"🤖 RADAR IDIV v7.0 - {len(MEUS_PAPEIS)} ativos")
    logger.info("="*60)
    
    # Baixa programas de recompra da CVM (uma vez só)
    programas_cvm = baixar_programas_recompra_cvm()
    
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
    
    # Verifica rotinas
    hoje_semana = datetime.now().weekday()
    hoje_dia = datetime.now().day
    
    e_segunda = hoje_semana == 0
    e_primeiro_dia = hoje_dia <= 3
    
    # Loop principal
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        logger.info(f"📊 Analisando {ticker}...")
        
        dados = analisar_ativo(ticker)
        if not dados:
            logger.warning(f"⚠️ Sem dados para {ticker}")
            continue
        
        acao = yf.Ticker(f"{ticker}.SA")
        historico = acao.history(period="6mo")
        
        # Detecta recompras (CVM)
        recompra = detectar_recompra(ticker, programas_cvm)
        if recompra:
            todas_recompras.append(recompra)
            logger.info(f"✅ {ticker}: Programa ativo até {recompra['dt_fim']}")
        
        # Verifica data COM
        if dados.get("proximo_dividendo", 0) > 0 and dados.get("ex_dividend_date"):
            data_com = datetime.fromtimestamp(dados["ex_dividend_date"])
            dias_para_data_com = (data_com - datetime.now()).days
            
            if 0 <= dias_para_data_com <= 15:
                dados_data_com.append({
                    **dados,
                    "data_com": data_com.strftime("%d/%m/%Y"),
                    "dias": dias_para_data_com
                })
        
        # Calcula score (mensal)
        if e_primeiro_dia:
            score = calcular_score(dados, historico, papel)
            dados["score"] = score
            
            if score["score_total"] >= 70:
                alertas.append(
                    f"🟢 *SCORE ALTO - {ticker}*\n"
                    f"Score: {score['score_total']:.0f}/100 ({score['classificacao']})"
                )
        
        # Alerta de DY (semanal)
        if e_segunda and dados["dividend_yield"] > 0.06:
            alertas.append(
                f"🟢 *DY ATRAENTE - {ticker}*\n"
                f"Dividend Yield: {dados['dividend_yield']:.2%}"
            )
        
        todos_dados.append(dados)
    
    # Envia tabela de data COM
    if dados_data_com:
        msg = "💰 *DATA COM PRÓXIMA*\n"
        msg += "Fonte: Estimativa Payout × LPA\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Data COM':<11} | {'Dias':<6} | {'Estimado':<10} | {'DY':<7}\n"
        msg += f"{'-'*47}\n"
        
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
    
    # Envia tabela de recompras
    if todas_recompras:
        msg = "🔁 *PROGRAMAS DE RECOMPRA ATIVOS*\n"
        msg += "Fonte: CVM Dados Abertos\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Empresa':<25} | {'Fim':<10} | {'Dias':<6} | {'Valor':<12}\n"
        msg += f"{'-'*65}\n"
        
        for r in todas_recompras:
            ticker = r['ticker']
            empresa = r.get('empresa', ticker)[:25]
            dt_fim = r.get('dt_fim', 'N/A')
            if dt_fim and dt_fim != 'N/A':
                try:
                    dt_fim = pd.to_datetime(dt_fim).strftime('%d/%m/%Y')
                except:
                    dt_fim = 'N/A'
            
            dias = r.get('dias_restantes', 0)
            if dias is not None:
                dias_str = f"{dias:>4}d"
            else:
                dias_str = "N/A"
            
            valor = r.get('valor_max', 0)
            if valor > 0:
                if valor >= 1e9:
                    valor_str = f"R$ {valor/1e9:.2f}B"
                elif valor >= 1e6:
                    valor_str = f"R$ {valor/1e6:.2f}M"
                else:
                    valor_str = f"R$ {valor/1e3:.2f}K"
            else:
                valor_str = "N/A"
            
            msg += (
                f"{ticker:<7} | "
                f"{empresa:<25} | "
                f"{dt_fim:<10} | "
                f"{dias_str:<6} | "
                f"{valor_str:<12}\n"
            )
        
        msg += "```\n"
        msg += "\n🟢 Programas oficiais registrados na CVM!"
        enviar_telegram(msg)
    
    # Envia alertas
    for alerta in alertas:
        enviar_telegram(alerta)
    
    # Envia resumo
    if todos_dados:
        msg = "📊 *RESUMO DIÁRIO*\n"
        msg += hoje + "\n\n"
        msg += "```\n"
        msg += f"{'Ativo':<7} | {'Preço':<8} | {'DY':<7} | {'P/L':<6} | {'P/VP':<6} | {'Status':<7}\n"
        msg += f"{'-'*47}\n"
        
        for d in sorted(todos_dados, key=lambda x: x.get('dividend_yield', 0), reverse=True):
            if d['dividend_yield'] > 0.06:
                icone = "🟢"
            elif d['dividend_yield'] > 0.04:
                icone = "🟡"
            else:
                icone = "🔴"
            
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
    
    # Mensagem final
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
