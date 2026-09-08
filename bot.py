import io
import zipfile
import requests
import pandas as pd
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÕES DO BOT
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604' # ⚠️ Não esqueça de colocar seu ID numérico aqui!

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

def enviar_alerta_telegram_com_botoes(mensagem, ticker=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    # Adiciona os botões de ação apenas quando for um alerta de ativo
    if ticker:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": f"📈 Ver Status {ticker}", "url": f"https://statusinvest.com.br/acoes/{ticker.lower()}"},
                    {"text": "📊 Portal CVM", "url": "https://sistemas.cvm.gov.br/patron/pa_index.asp"}
                ]
            ]
        }
        
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro no Telegram: {e}")

def carregar_dados_cvm(ano):
    # A URL dinâmica oficial da CVM compactada em ZIP
    url_zip = f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"
    print(f"Baixando dados da CVM (IPE) para o ano de {ano}...")
    
    try:
        resposta = requests.get(url_zip, timeout=30)
        if resposta.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(resposta.content)) as z:
                nome_arquivo_csv = z.namelist()[0] 
                with z.open(nome_arquivo_csv) as f:
                    return pd.read_csv(f, sep=';', encoding='latin1', low_memory=False)
        else:
            print(f"Erro HTTP da CVM: {resposta.status_code}")
            return None
    except Exception as e:
        print(f"Erro de processamento: {e}")
        return None

def executar_radar():
    print("Iniciando varredura automatizada...")
    agora = datetime.now()
    ano_atual = agora.strftime("%Y")
    mes_ano_atual = agora.strftime("%b/%y").upper()
    
    # RECIBO: Mensagem inicial de verificação sem botões
    enviar_alerta_telegram_com_botoes(f"🤖 *Radar IDIV | {mes_ano_atual}*\nConexão estabelecida com a CVM. Buscando Fatos Relevantes de {ano_atual}...")
    
    tabela_cvm = carregar_dados_cvm(ano_atual)
    
    if tabela_cvm is not None:
        # Padroniza as colunas da CVM para evitar erros de leitura
        tabela_cvm.columns = [col.upper() for col in tabela_cvm.columns]
        
        # Filtro de palavras-chave para focar no que importa
        gatilhos = ['DIVIDENDO', 'PROVENTO', 'RECOMPRA', 'JCP', 'JUROS SOBRE']
        contador_alertas = 0
        
        for index, linha in tabela_cvm.iterrows():
            empresa_cvm = str(linha.get('NOME_COMPANHIA', linha.get('NOME_EMPRESA', ''))).upper()
            assunto = str(linha.get('ASSUNTO', '')).upper()
            link = str(linha.get('LINK_DOWNLOAD', '')).strip()
            
            for papel in MEUS_PAPEIS:
                ticker = papel["ticker"]
                nome_empresa = papel["nome"]
                
                # Checa se a empresa está na nossa lista e se o assunto engatilha proventos/recompras
                if nome_empresa in empresa_cvm and any(g in assunto for g in gatilhos):
                    alerta_formatado = (
                        f"#{ticker} | {mes_ano_atual} | {nome_empresa}\n\n"
                        f"BUYBACK / FATO RELEVANTE:\n"
                        f"✅ {assunto}\n"
                        f"🔗 [Acessar Documento Oficial]({link})\n\n"
                        f"Fonte: CVM"
                    )
                    enviar_alerta_telegram_com_botoes(alerta_formatado, ticker)
                    contador_alertas += 1
                    
        print(f"Varredura concluída com {contador_alertas} alertas enviados.")
    else:
        print("Falha ao puxar os dados. Tente novamente mais tarde.")

if __name__ == "__main__":
    executar_radar()
