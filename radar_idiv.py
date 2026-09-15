"""
🤖 RADAR IDIV - Bot Telegram
Fonte: Brapi.dev (API gratuita da B3)
Docs: https://brapi.dev
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
class Config:
    TOKEN: str = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
    CHAT_ID: str = '566929604'
    TIMEOUT: int = 15
    
    # Brapi.dev (gratuita, sem auth para testes)
    BRAPI_BASE_URL = "https://brapi.dev/api"
    
    # Seus ativos
    MEUS_PAPEIS = [
        {"ticker": "CMIG4", "nome": "CEMIG"},
        {"ticker": "BBAS3", "nome": "BANCO DO BRASIL"},
        {"ticker": "SAPR11", "nome": "SANEPAR"},
        {"ticker": "ISAE4", "nome": "ISA ENERGIA"},
        {"ticker": "ABCB4", "nome": "ABC BRASIL"},
        {"ticker": "LOGG3", "nome": "LOG PROPERTIES"},
        {"ticker": "FIQE3", "nome": "UNIFIQUE"},
        {"ticker": "GGBR4", "nome": "GERDAU"},
        {"ticker": "VBBR3", "nome": "VIBRA ENERGIA"},
        {"ticker": "SAUD3", "nome": "BRADSAUDE"},
        {"ticker": "DEXP3", "nome": "DEXCO"},
    ]

cfg = Config()

# ==============================================================================
# TELEGRAM
# ==============================================================================
class TelegramBot:
    def __init__(self, token: str, chat_id: str, session: aiohttp.ClientSession):
        self.token = token
        self.chat_id = chat_id
        self.session = session
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    async def send_message(self, text: str, ticker: Optional[str] = None, parse_mode: str = "Markdown"):
        url = f"{self.base_url}/sendMessage"
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        if ticker:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": f"📈 {ticker}", "url": f"https://brapi.dev/quote/{ticker}"}
                ]]
            }
        
        try:
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    logger.info(f"✅ Telegram enviado")
                    return True
        except Exception as e:
            logger.error(f"❌ Erro Telegram: {e}")
        
        return False

# ==============================================================================
# BRAPI DEV API
# ==============================================================================
class BrapiAPI:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = cfg.BRAPI_BASE_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
    
    async def buscar_proventos(self, ticker: str) -> List[Dict]:
        """Busca dividendos via Brapi.dev"""
        logger.info(f"🔍 [Brapi] Buscando proventos: {ticker}")
        
        # Endpoint de dividendos
        url = f"{self.base_url}/v2/quote/{ticker}?dividends=true"
        
        try:
            async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=cfg.TIMEOUT)) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ [Brapi] Status {resp.status} para {ticker}")
                    return []
                
                data = await resp.json()
                
                # Estrutura da resposta: { "results": { "dividends": [...] } }
                resultados = data.get('results', {})
                dividendos = resultados.get('dividends', [])
                
                logger.info(f"✅ [Brapi] {len(dividendos)} dividendos encontrados para {ticker}")
                
                # Formata proventos
                proventos = []
                for div in dividendos:
                    try:
                        # Brapi retorna: { "date": "2024-09-10", "amount": 0.35 }
                        data_str = div.get('date', '')
                        valor = float(div.get('amount', 0))
                        
                        if data_str and valor > 0:
                            # Converte "2024-09-10" para "10/09/2024"
                            data_obj = datetime.strptime(data_str, "%Y-%m-%d")
                            data_com = data_obj.strftime("%d/%m/%Y")
                            
                            proventos.append({
                                "data_com": data_com,
                                "valor": valor,
                                "tipo": "Dividendo",
                                "fonte": "Brapi"
                            })
                    except (ValueError, KeyError) as e:
                        logger.debug(f"⚠️ Erro parse div: {e}")
                
                return proventos[:10]
                
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout Brapi para {ticker}")
            return []
        except Exception as e:
            logger.error(f"❌ [Brapi] Erro: {e}")
            return []
    
    async def buscar_fatos_relevantes(self, ticker: str) -> List[Dict]:
        """Busca fatos relevantes via Brapi (limitado)"""
        logger.info(f"🔍 [Brapi] Buscando fatos: {ticker}")
        
        # Brapi não tem endpoint direto de fatos relevantes
        # Usamos notícias como fallback
        url = f"{self.base_url}/v2/quote/{ticker}?news=true"
        
        try:
            async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=cfg.TIMEOUT)) as resp:
                if resp.status != 200:
                    return []
                
                data = await resp.json()
                noticias = data.get('results', {}).get('news', [])
                
                # Filtra notícias sobre recompras/insiders
                palavras_chave = {
                    "recompra": "RECOMPRA",
                    "buyback": "RECOMPRA",
                    "ações próprias": "RECOMPRA",
                    "diretor": "INSIDER",
                    "conselho": "INSIDER",
                }
                
                fatos = []
                for noticia in noticias[:10]:
                    titulo = noticia.get('title', '').lower()
                    
                    for palavra, categoria in palavras_chave.items():
                        if palavra in titulo:
                            fatos.append({
                                "data": datetime.now().strftime("%d/%m/%Y"),
                                "tipo": "FR",
                                "descricao": noticia.get('title', ''),
                                "categoria": categoria,
                                "link": noticia.get('link', ''),
                                "fonte": "Brapi"
                            })
                            break
                
                return fatos[:5]
                
        except Exception as e:
            logger.error(f"❌ [Brapi] Erro fatos: {e}")
            return []

# ==============================================================================
# RADAR DE DIVIDENDOS
# ==============================================================================
class RadarDividendos:
    def __init__(self, api: BrapiAPI, telegram: TelegramBot):
        self.api = api
        self.telegram = telegram
    
    async def executar(self, papeis: List[Dict[str, str]]):
        logger.info("🚀 Iniciando radar de dividendos (Brapi)...")
        mes_ano = datetime.now().strftime("%b/%y").upper()
        
        await self.telegram.send_message(
            f"🤖 *Radar IDIV | {mes_ano}*\n"
            f"Varredura de {len(papeis)} ativos (API Brapi) iniciada..."
        )
        
        total_alertas = 0
        total_encontrados = 0
        
        for papel in papeis:
            ticker = papel["ticker"]
            nome = papel["nome"]
            
            proventos = await self.api.buscar_proventos(ticker)
            total_encontrados += len(proventos)
            
            # Filtra últimos 60 dias
            hoje = datetime.now()
            proventos_recentes = []
            
            for prov in proventos:
                try:
                    data_com = datetime.strptime(prov["data_com"], "%d/%m/%Y")
                    dias_atras = (hoje - data_com).days
                    
                    if 0 <= dias_atras <= 60:
                        prov["dias_atras"] = dias_atras
                        proventos_recentes.append(prov)
                except ValueError:
                    continue
            
            # Envia alertas
            for prov in proventos_recentes:
                msg = (
                    f"#{ticker} | {mes_ano} | {nome}\n\n"
                    f"💰 *PROVENTO ENCONTRADO [Brapi]*\n"
                    f"💵 *Valor:* R$ {prov['valor']:.4f} por ação\n"
                    f"📅 *Data COM:* {prov['data_com']}\n"
                    f"📊 *Dias atrás:* {prov.get('dias_atras', 'N/A')} dias\n"
                    f"📊 *Tipo:* {prov.get('tipo', 'Dividendo')}"
                )
                
                await self.telegram.send_message(msg, ticker)
                total_alertas += 1
        
        logger.info(f"✅ Radar dividendos: {total_alertas} alertas / {total_encontrados} encontrados")
        
        if total_alertas == 0:
            await self.telegram.send_message(
                f"ℹ️ *Status da Varredura:*\n\n"
                f"📊 Ativos varridos: {len(papeis)}\n"
                f"🔍 Proventos encontrados: {total_encontrados}\n"
                f"⚠️ Nenhum provento com Data COM nos últimos 60 dias\n\n"
                f"💡 *Nota:* API Brapi retorna apenas dividendos históricos"
            )
        else:
            await self.telegram.send_message(
                f"✅ *Varredura Concluída!*\n\n"
                f"📊 Ativos varridos: {len(papeis)}\n"
                f"🔍 Total proventos: {total_encontrados}\n"
                f"📣 Alertas enviados: {total_alertas}"
            )

# ==============================================================================
# RADAR DE RECOMPRAS
# ==============================================================================
class RadarRecompras:
    def __init__(self, api: BrapiAPI, telegram: TelegramBot):
        self.api = api
        self.telegram = telegram
        self.arquivo_cache = "alertas_enviados.txt"
        self._carregar_cache()
    
    def _carregar_cache(self):
        self.alertas_enviados = set()
        if os.path.exists(self.arquivo_cache):
            with open(self.arquivo_cache, "r", encoding="utf-8") as f:
                self.alertas_enviados = set(f.read().splitlines())
    
    def _registrar_alerta(self, link: str):
        self.alertas_enviados.add(link)
        with open(self.arquivo_cache, "a", encoding="utf-8") as f:
            f.write(f"{link}\n")
    
    async def executar(self, papeis: List[Dict[str, str]]):
        logger.info("🚀 Iniciando radar de recompras...")
        
        total_alertas = 0
        
        for papel in papeis:
            ticker = papel["ticker"]
            
            fatos = await self.api.buscar_fatos_relevantes(ticker)
            
            for fato in fatos:
                if not self._ja_enviado(fato["link"]):
                    if fato["categoria"] == "RECOMPRA":
                        msg = (
                            f"🚨 *RECOMPRA DETECTADA:* #{ticker}\n\n"
                            f"📅 *Data:* {fato['data']}\n"
                            f"📄 *Fato:* {fato['descricao'][:200]}...\n\n"
                            f"💡 *Impacto:* Redução da base → LPA maior\n"
                            f"🔗 [Ler mais]({fato['link']})"
                        )
                        
                        await self.telegram.send_message(msg, ticker)
                        self._registrar_alerta(fato["link"])
                        total_alertas += 1
        
        logger.info(f"✅ Radar recompras: {total_alertas} alertas")
    
    def _ja_enviado(self, link: str) -> bool:
        return link in self.alertas_enviados

# ==============================================================================
# ORQUESTRADOR
# ==============================================================================
class BotInvestimentos:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.telegram: Optional[TelegramBot] = None
        self.api: Optional[BrapiAPI] = None
    
    async def inicializar(self):
        logger.info("🔧 Inicializando bot...")
        
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        self.session = aiohttp.ClientSession(connector=connector)
        self.telegram = TelegramBot(cfg.TOKEN, cfg.CHAT_ID, self.session)
        self.api = BrapiAPI(self.session)
        
        logger.info("✅ Bot inicializado (Brapi.dev)")
    
    async def fechar(self):
        if self.session:
            await self.session.close()
            logger.info("🔒 Sessões fechadas")
    
    async def executar_rotina(self):
        try:
            await self.inicializar()
            
            radar_div = RadarDividendos(self.api, self.telegram)
            radar_rec = RadarRecompras(self.api, self.telegram)
            
            await asyncio.gather(
                radar_div.executar(cfg.MEUS_PAPEIS),
                radar_rec.executar(cfg.MEUS_PAPEIS)
            )
            
            logger.info("✅ Rotina finalizada")
            
        except Exception as e:
            logger.error(f"❌ Erro crítico: {e}", exc_info=True)
        finally:
            await self.fechar()

# ==============================================================================
# MAIN
# ==============================================================================
async def main():
    bot = BotInvestimentos()
    await bot.executar_rotina()

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🤖 RADAR IDIV - API Brapi.dev")
    logger.info("📍 Fonte: https://brapi.dev")
    logger.info("=" * 60)
    
    asyncio.run(main())
