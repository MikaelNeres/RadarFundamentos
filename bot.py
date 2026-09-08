import requests
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore') # Ignora avisos do pandas

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

def executar_radar_dividendos():
    print("Iniciando varredura no Fundamentus...")
    
    agora = datetime.now()
    hoje_str = agora.strftime('%Y-%m-%d')
    mes_ano = agora.strftime("%b/%y").upper()
    
    enviar_alerta_telegram(f"🤖 *Radar IDIV | {mes_ano}*\nVarredura de Proventos iniciada no Fundamentus...")
    
    # Cabeçalho para "enganar" o site e mostrar que somos um navegador normal
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    contador_alertas = 0
    
    for papel in MEUS_PAPEIS:
        ticker = papel["ticker"]
        nome_empresa = papel["nome"]
        url = f"https://www.fundamentus.com.br/proventos.php?papel={ticker}&tipo=2"
        
        try:
            resposta = requests.get(url, headers=headers, timeout=10)
            
            # Se a página carregar com sucesso
            if resposta.status_code == 200:
                # O Pandas lê todas as tabelas HTML da página magicamente
                tabelas = pd.read_html(resposta.text, decimal=',', thousands='.')
                
                if tabelas:
                    df_proventos = tabelas[0] # A primeira tabela é a de proventos
                    
                    # Padroniza nomes das colunas
                    df_proventos.columns = ['DATA_COM', 'VALOR', 'TIPO', 'DATA_PAGAMENTO', 'QTD_ACOES']
                    
                    # Converte a coluna DATA_COM para formato de data manipulável
                    df_proventos['DATA_COM_FMT'] = pd.to_datetime(df_proventos['DATA_COM'], format='%d/%m/%Y', errors='coerce')
                    
                    # Filtra apenas proventos cuja Data COM seja igual ou maior que hoje (oportunidades em aberto)
                    proventos_futuros = df_proventos[df_proventos['DATA_COM_FMT'] >= pd.to_datetime(hoje_str)]
                    
                    for index, provento in proventos_futuros.iterrows():
                        valor = provento['VALOR']
                        tipo = provento['TIPO']
                        data_com = provento['DATA_COM']
                        data_pag = provento['DATA_PAGAMENTO']
                        
                        alerta_formatado = (
                            f"#{ticker} | {mes_ano} | {nome_empresa}\n\n"
                            f"💰 *PROVENTO ANUNCIADO:*\n"
                            f"✅ *Tipo:* {tipo}\n"
                            f"💵 *Valor:* R$ {valor:.4f} por ação\n"
                            f"📅 *Data COM:* {data_com}\n"
                            f"🗓️ *Data Pagamento:* {data_pag}\n\n"
                            f"Fonte: Fundamentus"
                        )
                        
                        enviar_alerta_telegram(alerta_formatado)
                        contador_alertas += 1
                        
        except Exception as e:
            print(f"Erro ao raspar {ticker}: {e}")
            
    print(f"Varredura concluída. {contador_alertas} proventos futuros encontrados.")
    if contador_alertas == 0:
        enviar_alerta_telegram("✅ *Radar IDIV:* Nenhuma Data COM futura mapeada hoje para a carteira.")

if __name__ == "__main__":
    executar_radar_dividendos()
