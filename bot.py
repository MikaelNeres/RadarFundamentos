"""
🤖 RADAR IDIV v14.0 - Monitoramento Fundamentalista
Foco: Dividendos, Data COM, Factor Investing
Fontes: Yahoo Finance
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

import yfinance as yf
import requests
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Configuração de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURAÇÕES DO TELEGRAM
# ==============================================================================

TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604'

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
# CONFIGURAÇÕES DE VALOR JUSTO
# ==============================================================================

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
        logger.error(f"❌ Erro Telegram: {e}")
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
        cinco_anos = hoje - timedelta(days=5*365)
        
        div_por_ano = {}
        for data, valor in dividendos.items():
            if hasattr(data, 'tzinfo'):
                data = data.replace(tzinfo=None)
            if data >= cinco_anos:
                ano = data.year
                div_por_ano[ano] = div_por_ano.get(ano, 0) + valor
        
        info = acao.info
        lpa = info.get('trailingEps', 0)
        
        if lpa <= 0:
            return 0, 0, 0, 0, 0
        
        payouts = [div / lpa for div in div_por_ano.values()]
        payout_medio = sum(payouts) / len(payouts) if payouts else 0.5
        payout_medio = min(payout_medio, 1.0)
        
        div_anual = lpa * payout_medio
        
        confianca = 0.5
        if lpa > 0:
            confianca += 0.2
        if 0.30 <= payout_medio <= 0.80:
            confianca += 0.2
        if len(dividendos) >= 20:
            confianca += 0.1
        confianca = min(confianca, 1.0)
        
        doze_meses = hoje - timedelta(days=365)
        pagamentos = sum(
            1 for d in dividendos.index
            if (d.replace(tzinfo=None) if hasattr(d, 'tzinfo') else d) >= doze_meses
        )
        
        frequencia = 4 if pagamentos >= 4 else 2 if pagamentos >= 2 else 1
        proximo = div_anual / frequencia
        
        return div_anual, payout_medio, lpa, confianca, proximo
    
    except Exception as e:
        logger.error(f"❌ Erro estimar dividendo {ticker}: {e}")
        return 0, 0, 0, 0, 0

# ==============================================================================
# FUNÇÕES DE ANÁLISE FUNDAMENTISTA
# ==============================================================================

def analisar_ativo(ticker):
    """Analisa ativo com MM200"""
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        preco = info.get('currentPrice', info.get('regularMarketPrice', 0))
        
        # ==========================================================================
        # DIVIDENDOS ATUAIS
        # ==========================================================================
        dividendos = acao.dividends
        doze_meses = datetime.now() - timedelta(days=365)
        
        div_12m = sum(
            v for d, v in dividendos.items()
            if (d.replace(tzinfo=None) if hasattr(d, 'tzinfo') else d) >= doze_meses
        ) if not dividendos.empty else 0
        
        dy = div_12m / preco if preco > 0 else 0
        
        # ==========================================================================
        # MÉDIA 200 DIAS
        # ==========================================================================
        media_200d = info.get('twoHundredDayAverage', 0)
        
        if media_200d <= 0:
            try:
                hist = acao.history(period="1y")
                if len(hist) >= 200:
                    media_200d = hist['Close'].iloc[-200:].mean()
                elif len(hist) > 0:
                    media_200d = hist['Close'].mean()
            except:
                media_200d = 0
        
        if media_200d > 0:
            distancia_media_200d = (preco - media_200d) / media_200d
        else:
            distancia_media_200d = 0
        
        # ==========================================================================
        # DADOS FUNDAMENTALISTAS
        # ==========================================================================
        div_anual, payout, lpa, confianca, proximo = estimar_dividendo(ticker)
        eps = info.get('trailingEps', 0)
        payout_ratio = min(div_12m / eps, 1.0) if eps > 0 else 0
        
        return {
            "ticker": ticker,
            "nome": info.get('longName', ticker),
            "preco": preco,
            "dividend_yield": dy,
            "dividendos_12m": div_12m,
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
            "upside": (info.get('targetMeanPrice', 0) - preco) / preco if preco > 0 and info.get('targetMeanPrice', 0) > 0 else 0,
            
            "media_200d": media_200d,
            "distancia_media_200d": distancia_media_200d,
        }
    
    except Exception as e:
        logger.error(f"❌ Erro analisar {ticker}: {e}")
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
    cresc = dados.get("crescimento", 0)
    
    score_roe = 100 if roe > 0.20 else 80 if roe > 0.15 else 60 if roe > 0.10 else 40 if roe > 0.05 else 20
    score_payout = 100 if 0.30 <= payout <= 0.60 else 80 if 0.20 <= payout <= 0.70 else 60 if 0.10 <= payout <= 0.80 else 40
    score_margem = 100 if margem > 0.20 else 80 if margem > 0.15 else 60 if margem > 0.10 else 40 if margem > 0.05 else 20
    score_divida = 100 if divida < 0.5 else 80 if divida < 1.0 else 60 if divida < 1.5 else 40 if divida < 2.0 else 20
    score_cresc = 100 if cresc > 0.15 else 80 if cresc > 0.10 else 60 if cresc > 0.05 else 40 if cresc > 0 else 20
    
    score_quality = score_roe * 0.30 + score_payout * 0.20 + score_margem * 0.20 + score_divida * 0.20 + score_cresc * 0.10
    
    # Low Vol (25%)
    beta = dados.get("beta", 1.0)
    score_beta = 100 if beta < 0.8 else 80 if beta < 1.0 else 60 if beta < 1.2 else 40 if beta < 1.5 else 20
    
    try:
        vol = historico['Close'].pct_change().std() * np.sqrt(252) if len(historico) > 0 else 0.5
    except:
        vol = 0.5
    
    score_vol = 100 if vol < 0.20 else 80 if vol < 0.30 else 60 if vol < 0.40 else 40 if vol < 0.50 else 20
    
    try:
        dd = (historico['Close'].max() - historico['Close'].iloc[-1]) / historico['Close'].max() if len(historico) > 0 else 0.5
    except:
        dd = 0.5
    
    score_dd = 100 if dd < 0.10 else 80 if dd < 0.20 else 60 if dd < 0.30 else 40 if dd < 0.40 else 20
    
    score_low_vol = score_beta * 0.40 + score_vol * 0.30 + score_dd * 0.30
    
    # Value (20%)
    pe = dados.get("pe_ratio", 0)
    pvp = dados.get("pb_ratio", 0)
    ev = dados.get("ev_ebitda", 0)
    
    p_l_justo = config.get("p_l_justo", 8.0)
    p_vp_justo = config.get("p_vp_justo", 1.2)
    
    score_pe = 100 if pe > 0 and pe < p_l_justo * 0.5 else 80 if pe > 0 and pe < p_l_justo * 0.75 else 60 if pe > 0 and pe < p_l_justo else 40 if pe > 0 and pe < p_l_justo * 1.25 else 20
    
    score_pvp = 100 if pvp > 0 and pvp < p_vp_justo * 0.5 else 80 if pvp > 0 and pvp < p_vp_justo * 0.75 else 60 if pvp > 0 and pvp < p_vp_justo else 40 if pvp > 0 and pvp < p_vp_justo * 1.25 else 20
    
    score_ev = 100 if ev > 0 and ev < 5 else 80 if ev > 0 and ev < 8 else 60 if ev > 0 and ev < 12 else 40 if ev > 0 and ev < 15 else 20
    
    score_value = score_pe * 0.40 + score_pvp * 0.30 + score_ev * 0.30
    
    # Dividend (15%)
    dy = dados.get("dividend_yield", 0)
    score_dy = 100 if dy > 0.10 else 80 if dy > 0.08 else 60 if dy > 0.06 else 40 if dy > 0.04 else 20
    
    dy_medio = config.get("dy_medio", 0.06)
    score_consist = 100 if dy >= dy_medio else 80 if dy >= dy_medio * 0.8 else 60
    
    score_dividend = score_dy * 0.50 + score_payout * 0.30 + score_consist * 0.20
    
    # Momentum (10%)
    try:
        ret = (historico['Close'].iloc[-1] - historico['Close'].iloc[0]) / historico['Close'].iloc[0] if len(historico) > 0 else 0
    except:
        ret = 0
    
    score_ret = 100 if ret > 0.30 else 80 if ret > 0.15 else 60 if ret > 0 else 40 if ret > -0.15 else 20
    
    try:
        dist = (historico['Close'].iloc[-1] - historico['Close'].max()) / historico['Close'].max() if len(historico) > 0 else 0
    except:
        dist = 0
    
    score_dist = 100 if dist > -0.10 else 80 if dist > -0.20 else 60 if dist > -0.30 else 40 if dist > -0.40 else 20
    
    score_momentum = score_ret * 0.60 + score_dist * 0.40
    
    # Score Total
    score_total = (
        score_quality * 0.30 +
        score_low_vol * 0.25 +
        score_value * 0.20 +
        score_dividend * 0.15 +
        score_momentum * 0.10
    )
    
    # Classificação
    if score_total >= 80:
        classif = "🟢 EXCELENTE"
    elif score_total >= 70:
        classif = "🟡 MUITO BOM"
    elif score_total >= 60:
        classif = "🟠 BOM"
    elif score_total >= 50:
        classif = "🔴 REGULAR"
    else:
        classif = "⚫ RUIM"
    
    return {
        "score_total": score_total,
        "classificacao": classif,
        "fatores": {
            "quality": score_quality,
            "low_vol": score_low_vol,
            "value": score_value,
            "dividend": score_dividend,
            "momentum": score_momentum
        }
    }

# ==============================================================================
# FUNÇÃO PRINCIPAL
# ==============================================================================

def main():
    """Função principal do bot"""
    
    logger.info("="*60)
    logger.info(f"🤖 RADAR IDIV v14.0 - {len(MEUS_PAPEIS)} ativos")
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
    dados_com_score = []
    
    # Verifica rotinas
    hoje_semana = datetime.now().weekday()
    hoje_dia = datetime.now().day
    
    e_segunda = hoje_semana == 0
    e_primeiro_dia = hoje_dia <= 3
    
    # ==========================================================================
    # LOOP PRINCIPAL
    # ==========================================================================
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        logger.info(f"📊 Analisando {ticker}...")
        
        dados = analisar_ativo(ticker)
        if not dados:
            logger.warning(f"⚠️ Sem dados para {ticker}")
            continue
        
        # Pega histórico 6 meses
        acao = yf.Ticker(f"{ticker}.SA")
        historico = acao.history(period="6mo")
        
        # Data COM
        if dados.get("proximo_dividendo", 0) > 0 and dados.get("ex_dividend_date"):
            data_com = datetime.fromtimestamp(dados["ex_dividend_date"])
            dias = (data_com - datetime.now()).days
            
            if 0 <= dias <= 15:
                dados_data_com.append({
                    **dados,
                    "data_com": data_com.strftime("%d/%m/%Y"),
                    "dias": dias
                })
        
        # Score (mensal - primeiros 3 dias)
        if e_primeiro_dia:
            score = calcular_score(dados, historico, papel)
            dados["score"] = score
            dados_com_score.append({**dados, "score": score})
            
            if score["score_total"] >= 70:
                alertas.append(
                    f"🟢 *SCORE ALTO - {ticker}*\n"
                    f"Score: {score['score_total']:.0f}/100 ({score['classificacao']})"
                )
        
        # Alerta DY (semanal - segundas)
        if e_segunda and dados["dividend_yield"] > 0.06:
            alertas.append(
                f"🟢 *DY ATRAENTE - {ticker}*\n"
                f"Dividend Yield: {dados['dividend_yield']:.2%}"
            )
        
        todos_dados.append(dados)
    
    # ==========================================================================
    # ENVIA TABELA DATA COM (DIARIAMENTE)
    # ==========================================================================
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
    
    # ==========================================================================
    # ENVIA ALERTAS
    # ==========================================================================
    for alerta in alertas:
        enviar_telegram(alerta)
    
    # ==========================================================================
    # ENVIA RESUMO DIÁRIO (TOP 10 MAIS ATRAENTES)
    # ==========================================================================
    if todos_dados:
        # Ordena por score (se tiver) ou por DY (se não tiver score)
        if dados_com_score:
            # Dias 1-3: usa score para ordenar
            todos_ordenados = sorted(todos_dados, key=lambda x: x.get('score', {}).get('score_total', 0), reverse=True)
        else:
            # Outros dias: usa DY para ordenar
            todos_ordenados = sorted(todos_dados, key=lambda x: x.get('dividend_yield', 0), reverse=True)
        
        # Pega apenas Top 10 mais atraentes
        top_10 = todos_ordenados[:10]
        
        msg = "📊 *RESUMO DIÁRIO*\n"
        msg += hoje + "\n"
        msg += "Top 10 Mais Atraentes\n\n"
        msg += "```\n"
        msg += f"{'#':<3} | {'Ativo':<7} | {'Preço':<8} | {'DY':<7} | {'MM200':<8} | {'Status':<7}\n"
        msg += f"{'-'*50}\n"
        
        for i, d in enumerate(top_10, 1):
            ticker = d.get('ticker', 'N/A')
            preco = d.get('preco', 0)
            dy = d.get('dividend_yield', 0)
            distancia = d.get('distancia_media_200d', 0)
            pe = d.get('pe_ratio', 0)
            
            # Ícone DY
            if dy > 0.06:
                icone = "🟢"
            elif dy > 0.04:
                icone = "🟡"
            else:
                icone = "🔴"
            
            # MM200 simplificada
            dist_pct = distancia * 100
            if distancia > 0.20:
                mm200 = f"+{dist_pct:.0f}% 🔴"
            elif distancia > 0:
                mm200 = f"+{dist_pct:.0f}%"
            elif distancia > -0.20:
                mm200 = f"{dist_pct:.0f}%"
            else:
                mm200 = f"{dist_pct:.0f}% 🟢"
            
            # Status
            if dy > 0.06 and pe < 8 and distancia < 0:
                status = "🟢 Buy"
            elif dy > 0.04:
                status = "🟡 Hold"
            else:
                status = "🔴 Sell"
            
            msg += (
                f"{i:<3} | "
                f"{ticker:<7} | "
                f"R$ {preco:>5.2f} | "
                f"{dy*100:>6.1f}% {icone} | "
                f"{mm200:<8} | "
                f"{status:<7}\n"
            )
        
        msg += "```\n"
        
        # Adiciona Top 10 Score apenas nos dias 1-3
        if dados_com_score:
            msg += "\n🏆 *TOP 10 SCORE*\n"
            msg += "Do mais atrativo para o menos atrativo\n\n"
            msg += "```\n"
            msg += f"{'#':<3} | {'Ativo':<7} | {'Score':<6} | {'Classif.':<12}\n"
            msg += f"{'-'*32}\n"
            
            ranking = sorted(dados_com_score, key=lambda x: x.get('score', {}).get('score_total', 0), reverse=True)[:10]
            
            for i, d in enumerate(ranking, 1):
                ticker = d.get('ticker', 'N/A')
                score = d.get('score', {}).get('score_total', 0)
                classif = d.get('score', {}).get('classificacao', 'N/A')[:12]
                
                msg += (
                    f"{i:<3} | "
                    f"{ticker:<7} | "
                    f"{score:>5.0f} | "
                    f"{classif:<12}\n"
                )
            
            msg += "```\n"
            msg += "\n📊 Quality 30% | Low Vol 25% | Value 20% | Dividend 15% | Momentum 10%"
        
        msg += "\n\n🟢 DY > 6%  |  🟡 DY 4-6%  |  🔴 DY < 4%"
        msg += "\nMM200 = vs Média 200d | 🟢 Abaixo = Oportunidade"
        enviar_telegram(msg)
    
    # ==========================================================================
    # MENSAGEM FINAL
    # ==========================================================================
    enviar_telegram(
        f"✅ *Monitoramento Concluído!*\n\n"
        f"📊 Ativos analisados: {len(todos_dados)}\n"
        f"💰 Data COM: {len(dados_data_com)}\n"
        f"📈 Alertas: {len(alertas)}\n"
        f"🏆 Ranking: {'✅' if dados_com_score else '❌ (apenas dias 1-3)'}"
    )
    
    logger.info(f"✅ Fim: {len(alertas)} alertas enviados")

# ==============================================================================
# EXECUTA
# ==============================================================================

if __name__ == "__main__":
    main()
