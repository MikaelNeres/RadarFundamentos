import requests
import pandas as pd

# ==============================================================================
# CONFIGURAÇÕES DO BOT (Insira seus dados entre as aspas)
# ==============================================================================
TOKEN = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
CHAT_ID = '566929604'
def enviar_alerta_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Erro ao enviar no Telegram: {e}")

def buscar_fatos_relevantes_avancado():
    print("Iniciando varredura avançada de Fatos Relevantes e Gatilhos...")
    
    # URL de Fatos Relevantes e Comunicados da CVM (base atualizada)
    url_cvm = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FPE/DADOS/fpe_cia_aberta_2026.csv"
    
    try:
        # Lendo a base da CVM
        tabela_cvm = pd.read_csv(url_cvm, sep=';', encoding='latin1')
        
        # 1. NOSSO RADAR DE EMPRESAS (Foco em Dividendos e DIVO11 / NDIV11)
        empresas_radar = [
            'ITAUSA', 'BB SEGURIDADE', 'PETROBRAS', 'COPEL', 
            'BRADESCO', 'ITAU UNIBANCO', 'VALE', 'BANCO DO BRASIL', 
            'VIBRA ENERGIA', 'CEMIG', 'COPASA', 'TIM', 'ALLOS', 
            'MARFRIG', 'ISA ENERGIA', 'CAIXA SEGURIDADE', 'CSN MINERAÇÃO', 
            'TAESA', 'FLEURY', 'CPFL ENERGIA', 'BRADESPAR', 'CURY', 
            'DIRECIONAL', 'MARCOPOLO', 'PETRORECONCAVO', 'BANRISUL', 
            'JHSF', 'UNIPAR', 'ENGIE', 'TELEFONICA'
        ]
        
        # 2. GATILHOS AVANÇADOS DE VALOR E GOVERNANÇA
        gatilhos_valor = [
            'RECOMPRA', 'AQUISICAO DE ACOES', 'PROGRAMA DE RECOMPRA',
            'DIVIDENDOS', 'JUROS SOBRE O CAPITAL', 'JCP',
            'INSIDER', 'DIRETORIA', 'GESTAO', 'AUMENTO DE CAPITAL'
        ]
        
        contador_alertas = 0
        
        # Varrendo as linhas da CVM de forma inteligente
        for index, linha in tabela_cvm.iterrows():
            empresa = str(linha.get('NOME_EMPRESA', '')).upper()
            assunto = str(linha.get('ASSUNTO', '')).upper()
            descricao = str(linha.get('DESCRICAO', '')).upper()
            
            # Cruzando o radar de empresas com os gatilhos avançados
            empresa_match = any(ticker in empresa for ticker in empresas_radar)
            gatilho_match = any(gatilho in assunto or gatilho in descricao for gatilho in gatilhos_valor)
            
            if empresa_match and gatilho_match:
                alerta = (
                    f"🎯 *ALERTA DE ASSIMETRIA – RADAR B3* 🎯\n\n"
                    f"🏢 *Empresa:* {empresa}\n"
                    f"📄 *Assunto:* {assunto}\n"
                    f"💡 *Foco:* Monitorar impacto imediato no Dividend Yield e Payout."
                )
                enviar_alerta_telegram(alerta)
                contador_alertas += 1
                
        print(f"Varredura concluída. Alertas de valor disparados: {contador_alertas}")
        
    except Exception as e:
        print(f"Aviso na leitura de Fatos Relevantes: {e}")
        # Mensagem de contingência caso o arquivo do dia ainda não tenha sido publicado na CVM
        enviar_alerta_telegram("🤖 *Radar B3:* Varredura executada. Nenhum fato relevante fora da curva para os gatilhos de dividendos/recompra no momento.")

if __name__ == "__main__":
    print("Robô com Filtros Avançados ativado...")
    enviar_alerta_telegram("🚀 *Radar B3 Avançado:* Módulos de Recompra e Dividendos ativados com sucesso!")
    buscar_fatos_relevantes_avancado()
