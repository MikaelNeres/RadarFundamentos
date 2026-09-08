import requests
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURAÇÕES DO BOT
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604'

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
    {"ticker": "ITSA4", "nome": "ITAUSA"},
    {"ticker": "BBSE3", "nome": "BB SEGURIDADE"},
    {"ticker": "PETR4", "nome": "PETROBRAS"},
    {"ticker": "ITUB4", "nome": "BANCO ITAU UNIBANCO"},
    {"ticker": "CPLE3", "nome": "COPEL"},
    {"ticker": "BBDC4", "nome": "BRADESCO"},
    {"ticker": "VALE3", "nome": "VALE"},
    {"ticker": "CSMG3", "nome": "COPASA"},
    {"ticker": "TIMS3", "nome": "TIM"},
    {"ticker": "ALOS3", "nome": "ALLOS"},
    {"ticker": "CXSE3", "nome": "CAIXA SEGURIDADE"},
    {"ticker": "CMIN3", "nome": "CSN MINERAÇÃO"},
    {"ticker": "TAEE11", "nome": "TAESA"},
    {"ticker": "FLRY3", "nome": "FLEURY"},
    {"ticker": "CPFE3", "nome": "CPFL ENERGIA"},
    {"ticker": "BRAP4", "nome": "BRADESPAR"},
    {"ticker": "CURY3", "nome": "CURY CONSTRUTORA"},
    {"ticker": "DIRR3", "nome": "DIRECIONAL ENGENHARIA"},
    {"ticker": "POMO4", "nome": "MARCOPOLO"}
]

def enviar_alerta_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro no Telegram: {e}")

def raspar_fundamentus(url, colunas):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            tabelas = pd.read_html(r.text, decimal=',', thousands='.')
            if tabelas and len(tabelas[0]) > 0:
                df = tabelas[0]
                df.columns = colunas
                return df
    except Exception:
        pass
    return None

def executar_radar():
    mes_ano = datetime.now().strftime("%b/%y").upper()
    total_alertas = 0
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        nome = papel["nome"]
        
        # 1. PROVENTOS (Último registro)
        df_prov = raspar_fundamentus(
            f"https://www.fundamentus.com.br/proventos.php?papel={ticker}&tipo=2", 
            ['DATA_COM', 'VALOR', 'TIPO', 'DATA_PAGAMENTO', 'QTD']
        )
        if df_prov is not None and not df_prov.empty:
            p = df_prov.iloc[0] # Pega o mais recente
            msg = (
                f"#{ticker} | {mes_ano} | {nome}\n\n"
                f"💰 *PROVENTO RECENTE:*\n"
                f"✅ {p['TIPO']}: R$ {p['VALOR']} | Data COM: {p['DATA_COM']}"
            )
            enviar_telegram(msg, ticker)
            total_alertas += 1

        # 2. INSIDERS (Última movimentação de diretoria/controladores)
        df_ins = raspar_fundamentus(
            f"https://www.fundamentus.com.br/insiders.php?papel={ticker}&tipo=1", 
            ['DATA', 'QTD', 'VALOR_TOTAL', 'PRECO_MEDIO']
        )
        if df_ins is not None and not df_ins.empty:
            i = df_ins.iloc[0]
            # Dispara apenas se houver movimentação relevante recente
            if str(i['DATA']) != 'nan' and str(i['QTD']) != '0':
                msg = (
                    f"#{ticker} | {mes_ano} | {nome}\n\n"
                    f"👥 *MOVIMENTAÇÃO DE INSIDERS:*\n"
                    f"📅 Data: {i['DATA']} | Qtd: {i['QTD']} | Vlr: R$ {i['VALOR_TOTAL']}"
                )
                enviar_telegram(msg, ticker)
                total_alertas += 1

        # 3. RECOMPRAS (Último programa/operação)
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

    print(f"Varredura concluída. {total_alertas} avisos enviados.")

if __name__ == "__main__":
    executar_radar()
