"""
🤖 RADAR IDIV v5.0 - Monitoramento Fundamentalista
Fonte: Yahoo Finance + StatusInvest
"""

import yfinance as yf, requests, re, logging, pandas as pd, numpy as np
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

TOKEN, CHAT_ID = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE', '566929604'
HISTORICO_SHARES = {}

MEUS_ATIVOS = ["CMIG4", "BBAS3", "SAPR11", "ISAE4", "ABCB4", "LOGG3", "FIQE3", "GGBR4", "VBBR3", "SAUD3", "DEXP3", "ITSA4", "PETR4", "BBSE3", "ITUB4", "BBDC4", "CPLE3", "VALE3", "CSMG3", "TIMS3", "VIVT3", "CXSE3", "KLBN11", "TAEE11", "EGIE3", "CPFE3", "CMIN3", "BMGB4", "ALOS3", "WEGE3", "AURE3"]

CONFIG_PADRAO = {"p_l_justo": 8.0, "p_vp_justo": 1.2, "dy_medio": 0.06}
CONFIG_POR_TICKER = {"BBAS3": {"p_l_justo": 6.0, "p_vp_justo": 1.0, "dy_medio": 0.08}, "ABCB4": {"p_l_justo": 5.0, "p_vp_justo": 0.9, "dy_medio": 0.09}, "VBBR3": {"p_l_justo": 7.0, "p_vp_justo": 1.5, "dy_medio": 0.09}, "PETR4": {"p_l_justo": 5.0, "p_vp_justo": 1.0, "dy_medio": 0.10}, "VALE3": {"p_l_justo": 6.0, "p_vp_justo": 1.1, "dy_medio": 0.09}, "ITUB4": {"p_l_justo": 9.0, "p_vp_justo": 1.5, "dy_medio": 0.07}, "BBDC4": {"p_l_justo": 7.0, "p_vp_justo": 1.2, "dy_medio": 0.08}}

MEUS_PAPEIS = [{"ticker": t, "nome": t, **{**CONFIG_PADRAO, **CONFIG_POR_TICKER.get(t, {})}} for t in MEUS_ATIVOS]
THRESHOLDS = {"dividend_yield_min": 0.06, "price_target_upside": 0.20, "dividend_cut": -0.20, "margem_seguranca_min": 0.20}
PESOS_FATORES = {"quality": 0.30, "low_vol": 0.25, "value": 0.20, "dividend": 0.15, "momentum": 0.10}

def enviar_telegram(msg):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        return r.status_code == 200
    except: return False

def estimar_dividendo(ticker):
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        divs = acao.dividends
        if divs.empty: return 0, 0, 0, 0, 0
        hoje, cinco_anos = datetime.now(), datetime.now() - timedelta(days=5*365)
        div_por_ano = {}
        for d, v in divs.items():
            if hasattr(d, 'tzinfo'): d = d.replace(tzinfo=None)
            if d >= cinco_anos: div_por_ano[d.year] = div_por_ano.get(d.year, 0) + v
        lpa = acao.info.get('trailingEps', 0)
        if lpa <= 0: return 0, 0, 0, 0, 0
        payouts = [div_por_ano[ano]/lpa for ano in div_por_ano if lpa > 0]
        lpa_med, payout_med = sum([lpa]*len(payouts))/len(payouts) if payouts else lpa, sum(payouts)/len(payouts) if payouts else 0.5
        div_anual = lpa_med * payout_med
        count = sum(1 for d in divs.index if (d.replace(tzinfo=None) if hasattr(d, 'tzinfo') else d) >= hoje - timedelta(days=365))
        freq = 4 if count >= 4 else 2 if count >= 2 else 1
        return div_anual, min(payout_med, 1.0), lpa_med, min(0.5 + (0.2 if lpa_med > 0 else 0) + (0.2 if 0.3 <= payout_med <= 0.8 else 0) + (0.1 if len(divs) >= 20 else 0), 1.0), div_anual / freq
    except: return 0, 0, 0, 0, 0

def buscar_insiders(ticker):
    try:
        from bs4 import BeautifulSoup
        r = requests.get(f"https://statusinvest.com.br/acao/{ticker}/insiders", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            movs = []
            tabela = soup.find('table', {'class': 'table'})
            if tabela:
                for row in tabela.find_all('tr')[1:]:
                    cols = row.find_all('td')
                    if len(cols) >= 5:
                        try: movs.append({'nome': cols[0].text.strip()[:20], 'cargo': cols[1].text.strip()[:15], 'tipo': cols[2].text.strip()[:6], 'quantidade': int(cols[3].text.strip().replace('.', '').replace(',', '')), 'data': cols[4].text.strip()[:10]})
                        except: pass
            return movs if movs else None
    except: pass
    return None

def carregar_insiders_csv():
    try: return pd.read_csv('insiders_manual.csv').to_dict('records')
    except: return []

def salvar_insiders_csv(movs, ticker):
    try:
        existentes = carregar_insiders_csv()
        todas = existentes + [{'ticker': ticker, **m} for m in movs]
        pd.DataFrame(todas).drop_duplicates(subset=['ticker', 'nome', 'data'], keep='last').to_csv('insiders_manual.csv', index=False)
    except: pass

def filtrar_insiders(movs, dias=30):
    if not movs: return []
    limite = datetime.now() - timedelta(days=dias)
    return [m for m in movs if m.get('data') and any(datetime.strptime(m['data'], f) >= limite for f in ['%d/%m/%Y', '%Y-%m-%d', '%d/%m/%y'] if m['data'] and len(m['data']) >= 10) and ('Compra' in m.get('tipo', '') or ('Venda' in m.get('tipo', '') and m.get('quantidade', 0) > 10000))]

def detectar_recompra(ticker):
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        shares = acao.info.get('sharesOutstanding', 0)
        if shares <= 0: return None
        try:
            fin = acao.quarterly_balance_sheet
            if fin is not None and not fin.empty and len(fin.columns) >= 2:
                for idx in fin.index:
                    if 'Common Stock' in idx or 'Capital Stock' in idx:
                        sh = fin.loc[idx]
                        if len(sh) >= 2 and sh.iloc[-1] > 0:
                            var = (sh.iloc[0] - sh.iloc[-1]) / sh.iloc[-1]
                            if var < -0.02: return {'ticker': ticker, 'status': 'Recompra Detectada', 'shares_atual': shares, 'sh_antigo': sh.iloc[-1], 'sh_novo': sh.iloc[0], 'var': var, 'conf': 'Alta' if var < -0.05 else 'Média'}
        except: pass
        if ticker in HISTORICO_SHARES and HISTORICO_SHARES[ticker] > 0:
            var = (shares - HISTORICO_SHARES[ticker]) / HISTORICO_SHARES[ticker]
            if var < -0.01: return {'ticker': ticker, 'status': 'Recompra em Andamento', 'shares_atual': shares, 'sh_antigo': HISTORICO_SHARES[ticker], 'var': var, 'conf': 'Média'}
        HISTORICO_SHARES[ticker] = shares
    except: pass
    return None

def calcular_score(dados, hist, cfg):
    roe = dados.get("roe", 0)
    scores = {"roe": 100 if roe > 0.20 else 80 if roe > 0.15 else 60 if roe > 0.10 else 40 if roe > 0.05 else 20}
    payout = dados.get("payout_ratio", 0)
    scores["payout"] = 100 if 0.30 <= payout <= 0.60 else 80 if 0.20 <= payout <= 0.70 else 60 if 0.10 <= payout <= 0.80 else 40
    margem = dados.get("profit_margins", 0)
    scores["margem"] = 100 if margem > 0.20 else 80 if margem > 0.15 else 60 if margem > 0.10 else 40 if margem > 0.05 else 20
    divida = dados.get("debt_to_equity", 0)
    scores["divida"] = 100 if divida < 0.5 else 80 if divida < 1.0 else 60 if divida < 1.5 else 40 if divida < 2.0 else 20
    cresc = dados.get("revenue_growth", 0)
    scores["cresc"] = 100 if cresc > 0.15 else 80 if cresc > 0.10 else 60 if cresc > 0.05 else 40 if cresc > 0 else 20
    sq = sum(scores.get(k, 50) * w for k, w in [("roe", 0.30), ("payout", 0.20), ("margem", 0.20), ("divida", 0.20), ("cresc", 0.10)])
    
    beta = dados.get("beta", 1.0)
    sbeta = 100 if beta < 0.8 else 80 if beta < 1.0 else 60 if beta < 1.2 else 40 if beta < 1.5 else 20
    try:
        vol = hist['Close'].pct_change().std() * np.sqrt(252) if len(hist) > 0 else 0.5
        svol = 100 if vol < 0.20 else 80 if vol < 0.30 else 60 if vol < 0.40 else 40 if vol < 0.50 else 20
        dd = (hist['Close'].max() - hist['Close'].iloc[-1]) / hist['Close'].max() if len(hist) > 0 else 0.5
        sdd = 100 if dd < 0.10 else 80 if dd < 0.20 else 60 if dd < 0.30 else 40 if dd < 0.40 else 20
    except: svol, sdd = 50, 50
    sl = sbeta * 0.40 + svol * 0.30 + sdd * 0.30
    
    pl = dados.get("pe_ratio", 0)
    plj = cfg.get("p_l_justo", 8.0)
    spl = 100 if pl > 0 and pl < plj*0.5 else 80 if pl > 0 and pl < plj*0.75 else 60 if pl > 0 and pl < plj else 40 if pl > 0 and pl < plj*1.25 else 20
    pvp = dados.get("pb_ratio", 0)
    pvpj = cfg.get("p_vp_justo", 1.2)
    spvp = 100 if pvp > 0 and pvp < pvpj*0.5 else 80 if pvp > 0 and pvp < pvpj*0.75 else 60 if pvp > 0 and pvp < pvpj else 40 if pvp > 0 and pvp < pvpj*1.25 else 20
    ev = dados.get("ev_ebitda", 0)
    sev = 100 if ev > 0 and ev < 5 else 80 if ev > 0 and ev < 8 else 60 if ev > 0 and ev < 12 else 40 if ev > 0 and ev < 15 else 20
    sv = spl * 0.40 + spvp * 0.30 + sev * 0.30
    
    dy = dados.get("dividend_yield", 0)
    sdy = 100 if dy > 0.10 else 80 if dy > 0.08 else 60 if dy > 0.06 else 40 if dy > 0.04 else 20
    sd = sdy * 0.50 + scores["payout"] * 0.30 + (100 if dados.get("five_year_avg_dividend_yield", 0) > 0 and dy >= dados["five_year_avg_dividend_yield"] else 80 if dados.get("five_year_avg_dividend_yield", 0) > 0 and dy >= dados["five_year_avg_dividend_yield"]*0.8 else 60 if dados.get("five_year_avg_dividend_yield", 0) > 0 else 40) * 0.20
    
    try:
        ret = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] if len(hist) > 0 else 0
        sret = 100 if ret > 0.30 else 80 if ret > 0.15 else 60 if ret > 0 else 40 if ret > -0.15 else 20
        dist = (hist['Close'].iloc[-1] - hist['Close'].max()) / hist['Close'].max() if len(hist) > 0 else 0
        sdist = 100 if dist > -0.10 else 80 if dist > -0.20 else 60 if dist > -0.30 else 40 if dist > -0.40 else 20
    except: sret, sdist = 50, 50
    sm = sret * 0.60 + sdist * 0.40
    
    total = sq*PESOS_FATORES["quality"] + sl*PESOS_FATORES["low_vol"] + sv*PESOS_FATORES["value"] + sd*PESOS_FATORES["dividend"] + sm*PESOS_FATORES["momentum"]
    classif = "🟢 EXCELENTE" if total >= 80 else "🟡 MUITO BOM" if total >= 70 else "🟠 BOM" if total >= 60 else "🔴 REGULAR" if total >= 50 else "⚫ RUIM"
    return {"score_total": total, "classificacao": classif, "fatores": {"quality": {"score": sq}, "low_vol": {"score": sl}, "value": {"score": sv}, "dividend": {"score": sd}, "momentum": {"score": sm}}}

def analisar(ticker):
    try:
        acao = yf.Ticker(f"{ticker}.SA")
        info = acao.info
        preco = info.get('currentPrice', info.get('regularMarketPrice', 0))
        divs = acao.dividends
        div_12m = sum(v for d, v in divs.items() if (d.replace(tzinfo=None) if hasattr(d, 'tzinfo') else d) >= datetime.now() - timedelta(days=365)) if not divs.empty else 0
        dy = div_12m / preco if preco > 0 else 0
        div_anual, payout_med, lpa_med, conf, prox = estimar_dividendo(ticker)
        eps = info.get('trailingEps', 0)
        payout = min(div_12m / eps, 1.0) if eps > 0 else 0
        return {"ticker": ticker, "nome": info.get('longName', ticker), "preco_atual": preco, "dividend_yield": dy, "dividendos_12m": div_12m, "proximo_dividendo": prox, "confianca_estimativa": conf, "ex_dividend_date": info.get('exDividendDate'), "payout_ratio": payout, "pe_ratio": info.get('trailingPE', 0), "pb_ratio": info.get('priceToBook', 0), "eps": eps, "price_target_mean": info.get('targetMeanPrice', 0), "beta": info.get('beta', 1.0), "roe": info.get('returnOnEquity', 0), "profit_margins": info.get('profitMargins', 0), "debt_to_equity": info.get('debtToEquity', 0), "revenue_growth": info.get('revenueGrowth', 0), "upside": (info.get('targetMeanPrice', 0) - preco) / preco if preco > 0 and info.get('targetMeanPrice', 0) > 0 else 0}
    except: return None

def main():
    logger.info(f"🤖 RADAR IDIV - {len(MEUS_PAPEIS)} ativos")
    hoje = datetime.now().strftime("%d/%m/%Y")
    enviar_telegram(f"🤖 *Radar IDIV | {hoje}*\nIniciando monitoramento de {len(MEUS_PAPEIS)} ativos...")
    
    todos, data_com, alertas, todas_recompras = [], [], [], []
    segunda = datetime.now().weekday() == 0
    primeiro_dia = datetime.now().day <= 3
    
    for p in MEUS_PAPEIS:
        t = p["ticker"]
        dados = analisar(t)
        if not dados: continue
        
        acao = yf.Ticker(f"{t}.SA")
        hist = acao.history(period="6mo")
        
        # Insiders
        ins = buscar_insiders(t)
        if ins:
            salvar_insiders_csv(ins, t)
            relevantes = filtrar_insiders(ins)
            if relevantes:
                msg = f"🔍 *INSIDER TRADING - {t}*\nÚltimos 30 dias\n\n```\n{'Nome':<20} | {'Cargo':<15} | {'Tipo':<6} | {'Qtd':<10} | {'Data':<10}\n{'-'*66}\n"
                for m in relevantes[:5]: msg += f"{m['nome']:<20} | {m['cargo']:<15} | {m['tipo']:<6} | {m['quantidade']:>10,} | {m['data']:<10}\n"
                compras = len([x for x in relevantes if 'Compra' in x.get('tipo', '')])
                msg += f"```\n\n📊 Sinal: {'🟢 Positivo' if compras > len(relevantes) - compras else '🔴 Negativo' if compras < len(relevantes) - compras else '🟡 Neutro'}"
                alertas.append(msg)
        
        # Recompras
        rec = detectar_recompra(t)
        if rec: todas_recompras.append(rec)
        
        # Data COM
        if dados.get("proximo_dividendo", 0) > 0 and dados.get("ex_dividend_date"):
            dc = datetime.fromtimestamp(dados["ex_dividend_date"])
            dias = (dc - datetime.now()).days
            if 0 <= dias <= 15: data_com.append({**dados, "data_com": dc.strftime("%d/%m/%Y"), "dias": dias})
        
        # Score (mensal)
        if primeiro_dia:
            score = calcular_score(dados, hist, p)
            if score["score_total"] >= 70: alertas.append(f"🟢 *SCORE ALTO - {t}*\nScore: {score['score_total']:.0f}/100 ({score['classificacao']})")
            dados["score"] = score
        
        # DY (semanal)
        if segunda and dados["dividend_yield"] > 0.06: alertas.append(f"🟢 *DY ATRAENTE - {t}*\nDY: {dados['dividend_yield']:.2%}")
        
        todos.append(dados)
    
    # Data COM
    if data_com:
        msg = "💰 *DATA COM PRÓXIMA*\nFonte: Estimativa Payout × LPA\n\n```\n"
        msg += f"{'Ativo':<7} | {'Data COM':<11} | {'Dias':<6} | {'Estimado':<10} | {'DY':<7}\n{'-'*47}\n"
        for d in sorted(data_com, key=lambda x: x["dias"]): msg += f"{d['ticker']:<7} | {d['data_com']:<11} | {d['dias']:>5}  | R$ {d['proximo_dividendo']:>6.4f} | {d['dividend_yield']:>6.2%}\n"
        msg += "```"
        enviar_telegram(msg)
    
    # Recompras (tabela única)
    if todas_recompras:
        msg = "🔁 *RECOMPRAS DETECTADAS*\nVariação de Shares\n\n```\n"
        msg += f"{'Ativo':<7} | {'Status':<22} | {'Variação':<10} | {'Shares':<20}\n{'-'*63}\n"
        for r in todas_recompras:
            var = f"{r['var']:.1%}"
            sh = f"{r['sh_antigo']/1e9:.2f}B→{r['sh_novo']/1e9:.2f}B" if 'sh_novo' in r else f"{r['sh_antigo']/1e9:.2f}B→{r['shares_atual']/1e9:.2f}B"
            msg += f"{r['ticker']:<7} | {r['status']:<22} | {var:<10} | {sh:<20}\n"
        msg += "```\n\n🟢 Recompras reduzem shares e aumentam LPA futuro!"
        enviar_telegram(msg)
    
    # Alertas
    for a in alertas: enviar_telegram(a)
    
    # Resumo
    if todos:
        msg = "📊 *RESUMO DIÁRIO*\n" + hoje + "\n\n```\n"
        msg += f"{'Ativo':<7} | {'Preço':<8} | {'DY':<7} | {'P/L':<6} | {'P/VP':<6} | {'Status':<7}\n{'-'*47}\n"
        for d in sorted(todos, key=lambda x: x.get('dividend_yield', 0), reverse=True):
            icone = "🟢" if d['dividend_yield'] > 0.06 else "🟡" if d['dividend_yield'] > 0.04 else "🔴"
            status = "🟢 Buy" if d['dividend_yield'] > 0.06 and d['pe_ratio'] < 8 else "🟡 Hold" if d['dividend_yield'] > 0.04 else "🔴 Sell"
            msg += f"{d['ticker']:<7} | R$ {d['preco_atual']:>5.2f} | {d['dividend_yield']:>6.1%} {icone} | {d['pe_ratio']:>5.2f} | {d['pb_ratio']:>5.2f} | {status:<7}\n"
        msg += "```\n\n🟢 DY > 6%  |  🟡 DY 4-6%  |  🔴 DY < 4%"
        enviar_telegram(msg)
    
    # Final
    enviar_telegram(f"✅ *Concluído!*\n\n📊 Ativos: {len(todos)}\n💰 Data COM: {len(data_com)}\n🔁 Recompras: {len(todas_recompras)}\n📈 Alertas: {len(alertas)}")
    logger.info(f"✅ Fim: {len(alertas)} alertas")

if __name__ == "__main__":
    main()
