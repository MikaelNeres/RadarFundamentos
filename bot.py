import requests
import pandas as pd

# ==============================================================================
# CONFIGURAÇÕES DO BOT (Insira seus dados entre as aspas)
# ==============================================================================
# Defina aqui a sua lista de papéis e empresas que deseja acompanhar no radar
MEUS_PAPEIS = [
    {"ticker": "CAMB3", "nome": "CAMBUCI"},
    {"ticker": "ITSA4", "nome": "ITAUSA"},
    {"ticker": "BBSE3", "nome": "BB SEGURIDADE"},
    {"ticker": "PETR4", "nome": "PETROBRAS"},
    {"ticker": "TAEE11", "nome": "TAESA"},
    {"ticker": "EGIE3", "nome": "ENGIE BRASIL"}
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
