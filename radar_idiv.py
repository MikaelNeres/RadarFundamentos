import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
from pathlib import Path

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================

class Config:  # ← Removido @dataclass
    TOKEN: str = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
    CHAT_ID: str = '566929604'
    TIMEOUT: int = 15
    MAX_RETRIES: int = 3
    CACHE_TTL: int = 300
    RATE_LIMIT_DELAY: float = 0.5
    
    MEUS_PAPEIS: List[Dict[str, str]] = [
    # Utilities
    {"ticker": "CMIG4", "nome": "CEMIG"},
    {"ticker": "CPFE3", "nome": "CPFL ENERGIA"},
    {"ticker": "EQTL3", "nome": "EQUATORIAL"},
    {"ticker": "TAEE11", "nome": "TAESA"},
    
    # Bancos
    {"ticker": "BBAS3", "nome": "BANCO DO BRASIL"},
    {"ticker": "SANB11", "nome": "SANTANDER BR"},
    {"ticker": "BBSE3", "nome": "BBSEGURIDADE"},
    {"ticker": "PSSA3", "nome": "PORTO SEGURO"},
    
    # Seguros
    {"ticker": "BBSE3", "nome": "BBSEGURIDADE"},
    {"ticker": "PSSA3", "nome": "PORTO SEGURO"},
    {"ticker": "IRBR3", "nome": "IRBBRASIL"},
    
    # Saneamento
    {"ticker": "SAPR11", "nome": "SANEPAR"},
    {"ticker": "SBSP3", "nome": "SABESP"},
    
    # Energia
    {"ticker": "ISAE4", "nome": "ISA ENERGIA"},
    {"ticker": "CPFE3", "nome": "CPFL ENERGIA"},
    
    # Outros
    {"ticker": "ABCB4", "nome": "ABC BRASIL"},
    {"ticker": "BRAP4", "nome": "BRADESPAR"},
    {"ticker": "CSNA3", "nome": "SID NACIONAL"},
    {"ticker": "GGBR4", "nome": "GERDAU"},
    {"ticker": "VBBR3", "nome": "VIBRA ENERGIA"},
    {"ticker": "LOGG3", "nome": "LOG PROPERTIES"},
    {"ticker": "RADL3", "nome": "RAIADROGASIL"},
    {"ticker": "CYRE3", "nome": "CYRELA"},
    {"ticker": "MRVE3", "nome": "MRV"},
    {"ticker": "TEND3", "nome": "TENDA"},
    {"ticker": "DXCO3", "nome": "DEXCO"},
    {"ticker": "PETR4", "nome": "PETROBRAS PN"},
    {"ticker": "VALE3", "nome": "VALE"},
    {"ticker": "ABCB4", "nome": "BANCO ABC BRASIL"},
    {"ticker": "BBAS3", "nome": "BANCO DO BRASIL"},
    {"ticker": "FIQE3", "nome": "UNIFIQUE"},
    {"ticker": "SAUD3", "nome": "BRADSAÚDE"},
    {"ticker": "DEXP3", "nome": "DEXCO"},
    ]

cfg = Config()

# ==============================================================================
# CACHE EM MEMÓRIA (Evita requests repetidos)
# ==============================================================================
class SimpleCache:
    def __init__(self, ttl: int = 300):
        self._cache: Dict[str, tuple] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[any]:
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now().timestamp() - timestamp < self.ttl:
                return data
            del self._cache[key]
        return None
    
    def set(self, key: str, data: any):
        self._cache[key] = (data, datetime.now().timestamp())
    
    def clear(self):
        self._cache.clear()

cache = SimpleCache(ttl=cfg.CACHE_TTL)

# ==============================================================================
# TELEGRAM (Async)
# ==============================================================================
class TelegramBot:
    def __init__(self, token: str, chat_id: str, session: aiohttp.ClientSession):
        self.token = token
        self.chat_id = chat_id
        self.session = session
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    async def send_message(self, text: str, ticker: Optional[str] = None, parse_mode: str = "Markdown"):
        """Envia mensagem para o Telegram com retry automático"""
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
                    {"text": f"📈 Fundamentus {ticker}", "url": f"https://fundamentus.com.br/proventos.php?papel={ticker.lower()}"}
                ]]
            }
        
        for tentativa in range(cfg.MAX_RETRIES):
            try:
                async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.info(f"✅ Telegram enviado (ticker: {ticker or 'N/A'})")
                        return True
                    logger.warning(f"⚠️ Telegram status {resp.status}")
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout Telegram (tentativa {tentativa + 1}/{cfg.MAX_RETRIES})")
            except Exception as e:
                logger.error(f"❌ Erro Telegram: {e}")
            
            if tentativa < cfg.MAX_RETRIES - 1:
                await asyncio.sleep(1 * (tentativa + 1))  # Backoff linear
        
        return False

# ==============================================================================
# SCRAPER FUNDAMENTUS (Async + Session Reuse)
# ==============================================================================
class FundamentusScraper:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = "https://fundamentus.com.br"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        }
    
    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML com retry e rate limiting"""
        cache_key = f"html:{url}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"📦 Cache hit: {url}")
            return cached
        
        await asyncio.sleep(cfg.RATE_LIMIT_DELAY)  # Rate limiting
        
        for tentativa in range(cfg.MAX_RETRIES):
            try:
                async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=cfg.TIMEOUT)) as resp:
                    if resp.status == 200:
                        html = await resp.text(encoding='utf-8')
                        cache.set(cache_key, html)
                        logger.debug(f"✅ Fetch OK: {url}")
                        return html
                    logger.warning(f"⚠️ Status {resp.status} para {url}")
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout (tentativa {tentativa + 1}/{cfg.MAX_RETRIES})")
            except Exception as e:
                logger.error(f"❌ Erro fetch {url}: {e}")
            
            if tentativa < cfg.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** tentativa)  # Backoff exponencial
        
        return None
    
    def _parse_tabela_proventos(self, html: str) -> List[Dict]:
        """Extrai tabela de proventos do HTML do Fundamentus"""
        proventos = []
        
        # Busca a tabela de proventos (estrutura típica do Fundamentus)
        # Nota: Ajuste os seletores conforme a estrutura real do HTML
        import re
        
        # Padrão para extrair linhas da tabela de proventos
        # Exemplo: <tr><td>15/09/2024</td><td>R$ 0,50</td><td>Dividendo</td>...</tr>
        padrao_linha = r'<tr[^>]*>.*?<td[^>]*>(\d{2}/\d{2}/\d{4}).*?</td>.*?<td[^>]*>R\$\s*([\d,.]+).*?</td>'
        
        matches = re.findall(padrao_linha, html, re.DOTALL)
        
        for data_com, valor_str in matches:
            try:
                # Converte "1.234,56" para 1234.56
                valor_limpo = valor_str.replace('.', '').replace(',', '.')
                proventos.append({
                    "data_com": data_com,
                    "valor": float(valor_limpo),
                    "tipo": "Dividendo"  # Pode ser extraído do HTML se necessário
                })
            except (ValueError, IndexError) as e:
                logger.debug(f"⚠️ Erro parse provento: {e}")
        
        return proventos[:10]  # Últimos 10 proventos
    
    def _parse_fatos_relevantes(self, html: str, ticker: str) -> List[Dict]:
        """Extrai fatos relevantes (recompras, insiders) do HTML"""
        fatos = []
        palavras_chave_recompra = ['recompra', 'buyback', 'aquisição de ações próprias', 'cancelamento de ações']
        palavras_chave_insider = ['negociação', 'diretor', 'conselho', 'insider', 'participação']
        
        import re
        
        # Padrão para fatos relevantes
        # Exemplo: <tr><td>10/09/2024</td><td>FR</td><td>Programa de Recompra...</td><td><a href="...">Download</a></td></tr>
        padrao_fato = r'<tr[^>]*>.*?<td[^>]*>(\d{2}/\d{2}/\d{4}.*?)</td>.*?<td[^>]*>(FR|CO|FA).*?</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*><a[^>]*href="([^"]+)".*?>.*?</a>.*?</td>'
        
        matches = re.findall(padrao_fato, html, re.DOTALL)
        
        for data, tipo, descricao, link in matches:
            descricao_lower = descricao.lower()
            categoria = None
            
            if any(p in descricao_lower for p in palavras_chave_recompra):
                categoria = "RECOMPRA"
            elif any(p in descricao_lower for p in palavras_chave_insider):
                categoria = "INSIDER"
            
            if categoria:
                fatos.append({
                    "data": data.split()[0],  # Só a data, sem hora
                    "tipo": tipo,
                    "descricao": descricao.strip(),
                    "categoria": categoria,
                    "link": f"{self.base_url}/{link}" if link.startswith('/') else link
                })
        
        return fatos[:5]  # Últimos 5 fatos relevantes
    
    async def buscar_proventos(self, ticker: str) -> List[Dict]:
        """Busca proventos (dividendos) de um ticker"""
        url = f"{self.base_url}/proventos.php?papel={ticker.upper()}&interface=classic"
        logger.info(f"🔍 Buscando proventos: {ticker}")
        
        html = await self._fetch_page(url)
        if not html:
            logger.warning(f"⚠️ HTML vazio para {ticker}")
            return []
        
        return self._parse_tabela_proventos(html)
    
    async def buscar_fatos_relevantes(self, ticker: str) -> List[Dict]:
        """Busca fatos relevantes (recompras, insiders) de um ticker"""
        url = f"{self.base_url}/fatos_relevantes.php?papel={ticker.upper()}"
        logger.info(f"🔍 Buscando fatos relevantes: {ticker}")
        
        html = await self._fetch_page(url)
        if not html:
            return []
        
        return self._parse_fatos_relevantes(html, ticker)

# ==============================================================================
# RADAR DE DIVIDENDOS
# ==============================================================================
class RadarDividendos:
    def __init__(self, scraper: FundamentusScraper, telegram: TelegramBot):
        self.scraper = scraper
        self.telegram = telegram
    
    async def executar(self, papeis: List[Dict[str, str]]):
        """Varre todos os papéis em paralelo"""
        logger.info("🚀 Iniciando radar de dividendos...")
        mes_ano = datetime.now().strftime("%b/%y").upper()
        
        await self.telegram.send_message(
            f"🤖 *Radar IDIV | {mes_ano}*\n"
            f"Varredura de proventos iniciada..."
        )
        
        # Busca todos os proventos em paralelo
        tasks = [self.scraper.buscar_proventos(papel["ticker"]) for papel in papeis]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_alertas = 0
        
        for i, papel in enumerate(papeis):
            ticker = papel["ticker"]
            nome = papel["nome"]
            
            if isinstance(resultados[i], Exception):
                logger.error(f"❌ Erro ao buscar {ticker}: {resultados[i]}")
                continue
            
            proventos = resultados[i]
            
            # Filtra proventos dos últimos 30 dias (anúncios recentes)
            hoje = datetime.now()
            proventos_recentes = []
            
            for prov in proventos:
                try:
                    data_com = datetime.strptime(prov["data_com"], "%d/%m/%Y")
                    if (hoje - data_com).days <= 30:  # Últimos 30 dias
                        proventos_recentes.append(prov)
                except ValueError:
                    continue
            
            # Envia alertas
            for prov in proventos_recentes:
                msg = (
                    f"#{ticker} | {mes_ano} | {nome}\n\n"
                    f"💰 *PROVENTO ANUNCIADO:*\n"
                    f"💵 *Valor:* R$ {prov['valor']:.4f} por ação\n"
                    f"📅 *Data COM:* {prov['data_com']}\n"
                    f"📊 *Tipo:* {prov.get('tipo', 'Dividendo')}"
                )
                
                await self.telegram.send_message(msg, ticker)
                total_alertas += 1
        
        logger.info(f"✅ Radar dividendos: {total_alertas} alertas enviados")
        
        if total_alertas == 0:
            await self.telegram.send_message(
                "✅ *Radar IDIV:*\n"
                "Nenhum novo dividendo anunciado nas últimas 24h para os ativos monitorados."
            )

# ==============================================================================
# RADAR DE RECOMPRAS E INSIDERS
# ==============================================================================
class RadarRecomprasInsiders:
    def __init__(self, scraper: FundamentusScraper, telegram: TelegramBot):
        self.scraper = scraper
        self.telegram = telegram
        self.arquivo_cache = Path("alertas_enviados.txt")
        self._carregar_cache()
    
    def _carregar_cache(self):
        """Carrega links já enviados do arquivo"""
        self.alertas_enviados = set()
        if self.arquivo_cache.exists():
            with open(self.arquivo_cache, "r", encoding="utf-8") as f:
                self.alertas_enviados = set(f.read().splitlines())
            logger.info(f"📦 Cache carregado: {len(self.alertas_enviados)} alertas")
    
    def _registrar_alerta(self, link: str):
        """Registra alerta enviado"""
        self.alertas_enviados.add(link)
        with open(self.arquivo_cache, "a", encoding="utf-8") as f:
            f.write(f"{link}\n")
    
    def _ja_enviado(self, link: str) -> bool:
        return link in self.alertas_enviados
    
    async def executar(self, papeis: List[Dict[str, str]]):
        """Varre todos os papéis em paralelo"""
        logger.info("🚀 Iniciando radar de recompras e insiders...")
        
        # Busca todos os fatos relevantes em paralelo
        tasks = [self.scraper.buscar_fatos_relevantes(papel["ticker"]) for papel in papeis]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_recompras = 0
        total_insiders = 0
        
        for i, papel in enumerate(papeis):
            ticker = papel["ticker"]
            nome = papel["nome"]
            
            if isinstance(resultados[i], Exception):
                logger.error(f"❌ Erro ao buscar fatos de {ticker}: {resultados[i]}")
                continue
            
            fatos = resultados[i]
            
            for fato in fatos:
                if fato["categoria"] == "RECOMPRA" and not self._ja_enviado(fato["link"]):
                    msg = (
                        f"🚨 *RECOMPRA DETECTADA:* #{ticker}\n\n"
                        f"📅 *Data:* {fato['data']}\n"
                        f"📄 *Fato:* {fato['descricao'][:200]}...\n\n"
                        f"💡 *Impacto:* Redução da base acionária → LPA maior\n"
                        f"🔗 [Ler comunicado]({fato['link']})"
                    )
                    
                    await self.telegram.send_message(msg, ticker)
                    self._registrar_alerta(fato["link"])
                    total_recompras += 1
                
                elif fato["categoria"] == "INSIDER" and not self._ja_enviado(fato["link"]):
                    msg = (
                        f"👁️ *MOVIMENTAÇÃO DE INSIDER:* #{ticker}\n\n"
                        f"📅 *Data:* {fato['data']}\n"
                        f"📄 *Fato:* {fato['descricao'][:200]}...\n\n"
                        f"💡 *Sinal:* Insiders conhecem a empresa melhor que ninguém\n"
                        f"🔗 [Ler comunicado]({fato['link']})"
                    )
                    
                    await self.telegram.send_message(msg, ticker)
                    self._registrar_alerta(fato["link"])
                    total_insiders += 1
        
        logger.info(f"✅ Radar recompras: {total_recompras} | Insiders: {total_insiders}")

# ==============================================================================
# ORQUESTRADOR PRINCIPAL
# ==============================================================================
class BotInvestimentos:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.telegram: Optional[TelegramBot] = None
        self.scraper: Optional[FundamentusScraper] = None
    
    async def inicializar(self):
        """Inicializa sessões HTTP e componentes"""
        logger.info("🔧 Inicializando bot...")
        
        # Session HTTP reutilizável (connection pooling)
        connector = aiohttp.TCPConnector(
            limit=10,  # Máximo de conexões simultâneas
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        self.session = aiohttp.ClientSession(connector=connector)
        self.telegram = TelegramBot(cfg.TOKEN, cfg.CHAT_ID, self.session)
        self.scraper = FundamentusScraper(self.session)
        
        logger.info("✅ Bot inicializado")
    
    async def fechar(self):
        """Fecha sessões HTTP"""
        if self.session:
            await self.session.close()
            logger.info("🔒 Sessões fechadas")
    
    async def executar_rotina(self):
        """Executa toda a rotina de monitoramento"""
        try:
            await self.inicializar()
            
            # Executa radares em paralelo
            radar_div = RadarDividendos(self.scraper, self.telegram)
            radar_rec = RadarRecomprasInsiders(self.scraper, self.telegram)
            
            await asyncio.gather(
                radar_div.executar(cfg.MEUS_PAPEIS),
                radar_rec.executar(cfg.MEUS_PAPEIS)
            )
            
            logger.info("✅ Rotina finalizada com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro crítico na rotina: {e}", exc_info=True)
        finally:
            await self.fechar()

# ==============================================================================
# PONTO DE ENTRADA
# ==============================================================================
async def main():
    bot = BotInvestimentos()
    await bot.executar_rotina()

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🤖 RADAR IDIV - Bot de Investimentos B3")
    logger.info("=" * 60)
    
    asyncio.run(main())
