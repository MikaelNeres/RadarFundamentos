import requests
import pandas as pd

# ==============================================================================
# CONFIGURAÇÕES DO BOT (Insira seus dados entre as aspas)
# ==============================================================================
# Defina aqui a sua lista de papéis e empresas que deseja acompanhar no radar
MEUS_PAPEIS = [
    {"ticker": "CMIG4", "nome": "CEMIG"},
    {"ticker": "SAPR11", "nome": "SANEPAR"},
    {"ticker": "ISAE4", "nome": "ISA ENERGIA BRASIL"},
    {"ticker": "ABCB4", "nome": "BANCO ABC BRASIL"},
    {"ticker": "LOGG3", "nome": "LOG COMMERCIAL PROPERTIES"},
    {"ticker": "BBAS3", "nome": "BANCO DO BRASIL"},
    {"ticker": "FIQE3", "nome": "UNIFIQUE"}, # (ou ativos equivalentes da sua carteira)
    {"ticker": "GGBR4", "nome": "GERDAU"},
    {"ticker": "VBBR3", "nome": "VIBRA ENERGIA"},
    {"ticker": "SAUD3", "nome": "BRADSAÚDE"},
    {"ticker": "DEXP3", "nome": "DEXCO"},
    
    # As maiores gigantes e vacas leiteiras do IDIV para completar o top 30
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
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro no Telegram: {e}")

def executar_radar():
    print("Iniciando varredura personalizada por Ticker...")
    
    # URL dos Fatos Relevantes da CVM (FPE)
    url_cvm = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FPE/DADOS/fpe_cia_aberta_2026.csv"
    
    try:
        tabela_cvm = pd.read_csv(url_cvm, sep=';', encoding='latin1')
        
        mes_ano_atual = datetime.now().strftime("%b/%y").upper() # Ex: AGO/26
        contador_alertas = 0
        
        for index, linha in tabela_cvm.iterrows():
            assunto = str(linha.get('ASSUNTO', '')).upper()
            descricao = str(linha.get('DESCRICAO_DOCUMENTO', '')).upper()
            empresa_cvm = str(linha.get('NOME_EMPRESA', '')).upper()
            
            # Verifica cada papel da sua lista configurada
            for papel in MEUS_PAPEIS:
                ticker = papel["ticker"]
                nome_empresa = papel["nome"]
                
                # Critério de match por nome ou indicação do ativo na base da CVM
                if nome_empresa in empresa_cvm or ticker in assunto:
                    # Formata o alerta exatamente no padrão desejado
                    alerta_formatado = (
                        f"#{ticker} | {mes_ano_atual} | {nome_empresa}\n\n"
                        f"BUYBACK / FATO RELEVANTE:\n"
                        f"✅ {assunto}\n"
                        f"📄 {descricao[:150]}...\n\n"
                        f"Fonte: CVM"
                    )
                    
                    enviar_alerta_telegram(alerta_formatado)
                    contador_alertas += 1
                    
        print(f"Varredura concluída. Alertas enviados: {contador_alertas}")
        
    except Exception as e:
        print(f"Erro na execução do radar: {e}")

if __name__ == "__main__":
    executar_radar()
