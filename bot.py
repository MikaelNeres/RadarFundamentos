import os
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURAÇÕES DO BOT
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604' # Confirme se está correto

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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro no envio do Telegram: {e}")

def executar_radar_vigentes():
    mes_ano = datetime.now().strftime("%b/%y").upper()
    hoje = datetime.now()
    total_alertas = 0
    
    print("Iniciando varredura de proventos vigentes...")
    enviar_telegram(f"🤖 *Radar IDIV | {mes_ano}*\nVarredura de proventos com Data COM vigente iniciada...")

    for papel in MEUS_PAPEIS:
        ticker_base = papel["ticker"]
        nome = papel["nome"]
        ticker_yf = f"{ticker_base}.SA"
        
        try:
            acao = yf.Ticker(ticker_yf)
            dividendos = acao.dividends
            
            if not dividendos.empty:
                # Converte o índice do yfinance para datetime sem fuso horário para comparação segura
                dividendos.index = pd.to_datetime(dividendos.index).tz_localize(None)
                
                # Filtra apenas proventos cuja Data COM seja de hoje em diante (vigentes)
                proventos_vigentes = dividendos[dividendos.index >= hoje]
                
                for data_com, valor in proventos_vigentes.items():
                    data_com_str = data_com.strftime('%d/%m/%Y')
                    
                    msg = (
                        f"#{ticker_base} | {mes_ano} | {nome}\n\n"
                        f"💰 *PROVENTO COM DATA COM VIGENTE:*\n"
                        f"💵 *Valor Declarado:* R$ {valor:.4f} por ação\n"
                        f"📅 *Data COM:* {data_com_str}"
                    )
                    enviar_telegram(msg, ticker_base)
                    total_alertas += 1
                    
        except Exception as e:
            print(f"Erro ao processar {ticker_base}: {e}")
            
    print(f"Varredura concluída. {total_alertas} proventos vigentes encontrados.")
    if total_alertas == 0:
        enviar_telegram("✅ *Radar IDIV:* Nenhuma nova Data COM vigente mapeada para os ativos monitorados no momento.")

# ==============================================================================
# CONTROLE DE ALERTAS (Evita enviar a mesma notícia de recompra duas vezes)
# ==============================================================================
ARQUIVO_CACHE = "recompras_enviadas.txt"

def alerta_ja_enviado(link):
    if not os.path.exists(ARQUIVO_CACHE):
        return False
    with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
        enviados = f.read().splitlines()
    return link in enviados

def registrar_alerta(link):
    with open(ARQUIVO_CACHE, "a", encoding="utf-8") as f:
        f.write(f"{link}\n")

# ==============================================================================
# NOVA FUNÇÃO: RADAR DE RECOMPRAS
# ==============================================================================
def executar_radar_recompras():
    print("Iniciando varredura de programas de recompra...")
    
    # Gatilhos de assimetria que o bot vai procurar
    palavras_chave = ['recompra', 'aquisição de ações', 'cancelamento de ações', 'buyback']
    total_alertas = 0

    for papel in MEUS_PAPEIS:
        ticker_base = papel["ticker"]
        ticker_yf = f"{ticker_base}.SA"
        
        try:
            acao = yf.Ticker(ticker_yf)
            noticias = acao.news # Usa o feed do próprio yfinance que você já tem instalado
            
            for noticia in noticias:
                titulo = noticia.get('title', '')
                link = noticia.get('link', '')
                titulo_lower = titulo.lower()
                
                # Se bater com a palavra-chave e não tiver sido enviado ainda...
                if any(palavra in titulo_lower for palavra in palavras_chave):
                    if not alerta_ja_enviado(link):
                        msg = (
                            f"🚨 *RADAR DE RECOMPRA ATIVADO:* #{ticker_base}\n\n"
                            f"• *Fato Relevante:* {titulo}\n"
                            f"• *Impacto:* Redução da base acionária em circulação.\n"
                            f"• *Estratégia:* Menos sócios na base = Aumento do LPA e potencial de maiores dividendos por cota!\n\n"
                            f"🔗 [Ler comunicado completo]({link})"
                        )
                        enviar_telegram(msg, ticker_base)
                        registrar_alerta(link)
                        total_alertas += 1
                        
        except Exception as e:
            print(f"Erro ao processar notícias de {ticker_base}: {e}")

    print(f"Varredura de recompras concluída. {total_alertas} novos alertas enviados.")

# ==============================================================================
# EXECUÇÃO PRINCIPAL (ATUALIZADA)
# ==============================================================================
if __name__ == "__main__":
    print("Iniciando rotina do Bot de Investimentos...")
    
    # 1. Roda o seu motor atual de Dividendos
    executar_radar_vigentes()
    
    # 2. Roda o novo motor de Recompras e Assimetria
    executar_radar_recompras()
    
    print("Rotina finalizada com sucesso.")
    executar_radar_vigentes()
