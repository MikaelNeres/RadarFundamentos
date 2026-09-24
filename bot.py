"""
🤖 RADAR IDIV v19.0 - Monitoramento Fundamentalista
Foco: E/Y + Upside + Payout (simplificado)
"""

import yfinance as yf, requests, logging, pandas as pd, numpy as np
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

TOKEN, CHAT_ID = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE', '566929604'

# ==============================================================================
# SEUS ATIVOS (35)
# ==============================================================================

MEUS_ATIVOS = [
    "CMIG4", "BBAS3", "SAPR11", "ISAE4", "ABCB4", "LOGG3", "FIQE3", "GGBR4",
    "VBBR3", "SAUD3", "DEXP3", "ITSA4", "PETR4", "BBSE3", "ITUB4", "BBDC4",
    "CPLE3", "VALE3", "CSMG3", "TIMS3", "VIVT3", "CXSE3", "KLBN11", "TAEE11",
    "EGIE3", "CPFE3", "CMIN3", "BMGB4", "ALOS3", "WEGE3", "AURE3", "PASS3",
    "PSSA3", "RANI3", "KLBN4"
]

# Configurações P/L justo por ativo
CONFIG = {
    "BBAS3":{"p_l":6.0}, "ABCB4":{"p_l":5.0}, "VBBR3":{"p_l":7.0},
    "PETR4":{"p_l":5.0}, "VALE3":{"p_l":6.0}, "ITUB4":{"p_l":9.0},
    "BBDC4":{"p_l":7.0}, "CMIG4":{"p_l":7.0}, "TAEE11":{"p_l":10.0},
    "CPLE3":{"p_l":8.0}, "CPFE3":{"p_l":9.0}, "EGIE3":{"p_l":10.0}
}
PADRAO = {"p_l":8.0}

# ==============================================================================
# FUNÇÕES BÁSICAS
# ==============================================================================

def enviar(msg):
    try: return requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id":CHAT_ID,"text":msg,"parse_mode":"Markdown"}, timeout=15).status_code==200
    except: return False

def analisar(ticker):
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        preco = info.get('currentPrice',0)
        lpa = info.get('trailingEps',0)
        ey = lpa/preco if preco>0 and lpa>0 else 0
        
        pe = info.get('trailingPE',0)
        pe_justo = CONFIG.get(ticker,PADRAO).get('p_l',8.0)
        upside = (pe_justo-pe)/pe if pe>0 else 0
        
        divs = acao.dividends
        doze_meses = datetime.now()-timedelta(days=365)
        div_12m = sum(v for d,v in divs.items() if (d.replace(tzinfo=None) if hasattr(d,'tzinfo') else d)>=doze_meses) if not divs.empty else 0
        payout = div_12m/lpa if lpa>0 else 0
        
        fcf = info.get('freeCashflow',0)
        shares = info.get('sharesOutstanding',0)
        fcf_acao = fcf/shares if shares>0 and fcf>0 else 0
        
        roe = info.get('returnOnEquity',0)
        score = min(100, max(0, int(roe*300 + (1 if fcf_acao>0 else 0)*20 + (1 if payout<0.60 else 0)*20)))
        
        status = "🟢" if ey>0.15 and upside>0.30 and payout<0.60 else "🟡" if ey>0.12 and upside>0.20 and payout<1.00 else "🔴"
        
        return {"ticker":ticker,"preco":preco,"ey":ey,"upside":upside,"payout":payout,"fcf_acao":fcf_acao,"score":score,"status":status,"div_12m":div_12m}
    except: return None

def verificar_sustentabilidade(ticker):
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        
        lpa = info.get('trailingEps',0)
        divs = acao.dividends
        doze_meses = datetime.now()-timedelta(days=365)
        div_12m = sum(v for d,v in divs.items() if (d.replace(tzinfo=None) if hasattr(d,'tzinfo') else d)>=doze_meses) if not divs.empty else 0
        
        payout = div_12m/lpa if lpa>0 else 0
        
        fcf = info.get('freeCashflow',0)
        shares = info.get('sharesOutstanding',0)
        fcf_acao = fcf/shares if shares>0 else 0
        
        cobertura = fcf_acao/div_12m if div_12m>0 and fcf_acao>0 else 0
        
        if payout < 0.60 and fcf_acao > div_12m: status = "🟢"
        elif payout < 1.00 and fcf_acao > 0: status = "🟡"
        elif payout >= 1.00 or fcf_acao <= 0: status = "🔴"
        else: status = "⚪"
        
        return {'ticker':ticker,'payout':payout,'cobertura':cobertura,'status':status}
    except: return None

# ==============================================================================
# MAIN
# ==============================================================================

def main():
    hoje = datetime.now()
    hoje_str = hoje.strftime("%d/%m/%Y")
    hoje_semana = hoje.weekday()
    
    if hoje_semana >= 5:
        logger.info("⚠️ Fim de semana - sem monitoramento")
        return
    
    enviar(f"🤖 *Radar IDIV* | {hoje_str}\nIniciando monitoramento de {len(MEUS_ATIVOS)} ativos...")
    
    resultados, dados_com = [], []
    
    for ticker in MEUS_ATIVOS:
        logger.info(f"📊 Analisando {ticker}...")
        dados = analisar(ticker)
        if not dados: continue
        
        # Data COM
        if dados.get("div_12m",0)>0:
            acao = yf.Ticker(f"{ticker}.SA")
            ex_div = acao.info.get('exDividendDate')
            if ex_div:
                data_com = datetime.fromtimestamp(ex_div)
                dias = (data_com-hoje).days
                if 0<=dias<=15:
                    dados_com.append({"ticker":ticker,"data":data_com.strftime("%d/%m"),"dias":dias,"div":dados['div_12m'],"dy":dados['ey']})
        
        resultados.append(dados)
    
    # Data COM
    if dados_com:
        msg = f"💰 *DATA COM*\n{hoje_str}\n\n```\n{'Ativo':<7} | {'Data':<8} | {'Dias':<6} | {'Est. Div':<10} | {'DY':<7}\n{'-'*45}\n"
        for d in sorted(dados_com, key=lambda x:x["dias"]):
            msg += f"{d['ticker']:<7} | {d['data']:<8} | {d['dias']:>5} | R$ {d['div']:>6.4f} | {d['dy']*100:>6.1f}%\n"
        msg += "```"
        enviar(msg)
    
    # Top 10
    if resultados:
        resultados.sort(key=lambda x:(x['ey']+x['upside']), reverse=True)
        
        msg = f"📊 *TOP 10*\n{hoje_str}\n\n```\n{'#':<3} | {'Ativo':<7} | {'E/Y':<7} | {'Upside':<8} | {'Payout':<8} | {'Score':<6} | {'Status':<6}\n{'-'*55}\n"
        
        for i,d in enumerate(resultados[:10],1):
            payout_status = "🟢" if d['payout']<0.60 else "🟡" if d['payout']<1.00 else "🔴"
            msg += f"{i:<3} | {d['ticker']:<7} | {d['ey']*100:>6.1f}% | +{d['upside']*100:>6.1f}% | {d['payout']*100:>6.0f}% {payout_status} | {d['score']:>5.0f} | {d['status']:<6}\n"
        
        msg += "```\n\n🟢 E/Y>15% + Upside>30% + Payout<60%\n🟡 E/Y>12% + Upside>20% + Payout<100%\n🔴 Abaixo disso\n\n💡 E/Y=LPA/Preço | Upside=Múltiplos | Payout=Sust."
        enviar(msg)
    
    # Sustentabilidade (dia 15)
    if hoje.day == 15:
        sus_resultados = []
        for ticker in MEUS_ATIVOS:
            sus = verificar_sustentabilidade(ticker)
            if sus and sus['status'] != "⚪":
                sus_resultados.append(sus)
        
        if sus_resultados:
            sus_resultados.sort(key=lambda x:x['payout'])
            
            msg = f"📊 *SUSTENTABILIDADE*\n{hoje_str}\n\n```\n{'#':<3} | {'Ticker':<7} | {'Payout':<8} | {'Cob':<8} | {'Status':<6}\n{'-'*40}\n"
            
            for i,r in enumerate(sus_resultados[:10],1):
                cob_str = f"{r['cobertura']:.1f}x" if r['cobertura']>0 else "N/D"
                msg += f"{i:<3} | {r['ticker']:<7} | {r['payout']*100:>6.0f}%  | {cob_str:<8} | {r['status']:<6}\n"
            
            msg += f"```\n\n🟢 Payout < 60% + FCF cobre\n🟡 Payout 60-100% + FCF > 0\n🔴 Payout > 100% ou FCF < 0\n\n{len(sus_resultados)}/{len(MEUS_ATIVOS)} analisados"
            enviar(msg)
    
    logger.info(f"✅ Enviado: {len(resultados)} ativos")

if __name__ == "__main__":
    main()
