import requests
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURAÇÕES DO BOT
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604' # Confirme se está preenchido corretamente

MEUS_PAPEIS = [
    {"ticker": "CMIG4", "nome": "CEMIG"},
    {"ticker": "SAPR11", "nome": "SANEPAR"},
    {"ticker": "ISAE4", "nome": "ISA ENERGIA BRASIL"},
    {"ticker": "ABCB4", "nome": "BANCO ABC BRASIL"},
    {"ticker": "LOGG3", "nome": "LOG COMMERCIAL PROPERTIES"},
    {"ticker": "BBAS3", "nome": "BANCO DO BRASIL"},
    {"ticker": "FIQE3", "nome": "UNIFIQUE"},
    {"ticker": "GGBR4", "nome": "GERDAU"},
    {"ticker": "VBBR3", "nome": "VIBRA ENERGIA"},
    {"ticker": "SAUD3", "nome": "BRADSAÚDE"},
    {"ticker": "DEXP3", "nome": "DEXCO"},
]

def enviar_telegram(mensagem, ticker=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if ticker:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": f"📈 Status Invest {ticker}", "url": f"https://statusinvest.com.br/acoes/{ticker.lower()}"}
            ]]
        }
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Telegram status para {ticker or 'Geral'}: {r.status_code}")
    except Exception as e:
        print(f"Erro Telegram: {e}")

def raspar_fundamentus(url, colunas):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Acessando URL: {url} | Status HTTP: {r.status_code}")
        if r.status_code == 200:
            tabelas = pd.read_html(r.text, decimal=',', thousands='.')
            if tabelas and len(tabelas[0]) > 0:
                df = tabelas[0]
                df.columns = colunas
                return df
    except Exception as e:
        print(f"Erro ao raspar {url}: {e}")
    return None

def executar_radar():
    mes_ano = datetime.now().strftime("%b/%y").upper()
    total_alertas = 0
    
    enviar_telegram(f"🤖 *Radar IDIV | {mes_ano}*\nIniciando varredura completa (Proventos, Insiders e Recompras)...")

    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        nome = papel["nome"]
        
        # 1. PROVENTOS
        df_prov = raspar_fundamentus(
            f"https://www.fundamentus.com.br/proventos.php?papel={ticker}&tipo=2", 
            ['DATA_COM', 'VALOR', 'TIPO', 'DATA_PAGAMENTO', 'QTD']
        )
        if df_prov is not None and not df_prov.empty:
            p = df_prov.iloc[0]
            msg = (
                f"#{ticker} | {mes_ano} | {nome}\n\n"
                f"💰 *PROVENTO RECENTE:*\n"
                f"✅ {p['TIPO']}: R$ {p['VALOR']} | Data COM: {p['DATA_COM']}"
            )
            enviar_telegram(msg, ticker)
            total_alertas += 1

        # 2. INSIDERS (Movimentação de diretores/controladores)
        df_ins = raspar_fundamentus(
            f"https://www.fundamentus.com.br/insiders.php?papel={ticker}&tipo=1", 
            ['DATA', 'QTD', 'VALOR_TOTAL', 'PRECO_MEDIO']
        )
        if df_ins is not None and not df_ins.empty:
            i = df_ins.iloc[0]
            if str(i['DATA']) != 'nan' and str(i['QTD']) != '0':
                msg = (
                    f"#{ticker} | {mes_ano} | {nome}\n\n"
                    f"👥 *MOVIMENTAÇÃO DE INSIDERS:*\n"
                    f"📅 Data: {i['DATA']} | Qtd: {i['QTD']} | Vlr: R$ {i['VALOR_TOTAL']}"
                )
                enviar_telegram(msg, ticker)
                total_alertas += 1

        # 3. RECOMPRAS (Última operação ou programa)
        df_rec = raspar_fundamentus(
            f"https://www.fundamentus.com.br/recompras.php?papel={ticker}&tipo=1", 
            ['DATA', 'QTD', 'VALOR_TOTAL', 'PRECO_MEDIO']
        )
        if df_rec is not None and not df_rec.empty:
            r_op = df_rec.iloc[0]
            if str(r_op['DATA']) != 'nan' and str(r_op['QTD']) != '0':
                msg = (
                    f"#{ticker} | {mes_ano} | {nome}\n\n"
                    f"🔄 *PROGRAMA DE RECOMPRA:*\n"
                    f"📅 Data: {r_op['DATA']} | Qtd: {r_op['QTD']} | Vlr: R$ {r_op['VALOR_TOTAL']}"
                )
                enviar_telegram(msg, ticker)
                total_alertas += 1

    enviar_telegram(f"✅ *Varredura Completa Concluída!*\nTotal de alertas disparados: {total_alertas}")
    print(f"Ciclo finalizado. Total de avisos: {total_alertas}")

if __name__ == "__main__":
    executar_radar()

    print(f"Varredura concluída. {total_alertas} avisos enviados.")

if __name__ == "__main__":
    executar_radar()
