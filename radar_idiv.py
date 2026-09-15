"""
🤖 RADAR IDIV - Bot Telegram para Monitoramento de Ativos B3
Fonte: Fundamentus.com.br
Versão: Debug Aprimorada
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from pathlib import Path
import re

# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG,  # Nível detalhado para debug
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
    MAX_RETRIES: int = 3
    CACHE_TTL: int = 300
    RATE_LIMIT_DELAY: float = 0.5
    
    # Lista ampliada de ativos (IDIV + seus favoritos)
    MEUS_PAPEIS: List[Dict[str, str]] = [
        # Seus originais
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
        
        # Adicionados do IDIV
        {"ticker": "CPFE3", "nome": "CPFL ENERGIA"},
        {"ticker": "ENBR3", "nome": "ENERGIAS BR"},
        {"ticker": "EQTL3", "nome": "EQUATORIAL"},
        {"ticker": "TAEE11", "nome": "TAESA"},
        {"ticker": "TRPL4", "nome": "TRAN PAULISTA"},
        {"ticker": "SANB11", "nome": "SANTANDER BR"},
        {"ticker": "BBSE3", "nome": "BBSEGURIDADE"},
        {"ticker": "PSSA3", "nome": "PORTO SEGURO"},
        {"ticker": "SBSP3", "nome": "SABESP"},
        {"ticker": "BRAP4", "nome": "BRADESPAR"},
        {"ticker": "CSNA3", "nome": "SID NACIONAL"},
        {"ticker": "USIM5", "nome": "USIMINAS"},
        {"ticker": "PETR4", "nome": "PETROBRAS PN"},
        {"ticker": "VALE3", "nome": "VALE"},
    ]

cfg = Config()

# ==============================================================================
# CACHE EM MEMÓRIA
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

cache = SimpleCache(ttl=cfg.CACHE_TTL)

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
                await asyncio.sleep(1 * (tentativa + 1))
        
        return False

# ==============================================================================
# SCRAPER FUNDAMENTUS - VERSÃO DEBUG
# ==============================================================================
class FundamentusScraper:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = "https://fundamentus.com.br"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    async def _fetch_page(self, url: str, salvar_html: bool = False, ticker: str = "") -> Optional[str]:
        """Fetch HTML com retry, rate limiting e opção de salvar para debug"""
        cache_key = f"html:{url}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"📦 Cache hit: {url}")
            return cached
        
        await asyncio.sleep(cfg.RATE_LIMIT_DELAY)
        
        for tentativa in range(cfg.MAX_RETRIES):
            try:
                async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=cfg.TIMEOUT)) as resp:
                    if resp.status == 200:
                        html = await resp.text(encoding='utf-8')
                        cache.set(cache_key, html)
                        
                        # Salva HTML para debug (apenas no primeiro ticker)
                        if salvar_html and ticker:
                            arquivo_html = Path(f"debug_{ticker.lower()}.html")
                            with open(arquivo_html, "w", encoding="utf-8") as f:
                                f.write(html)
                            logger.info(f"💾 HTML salvo em: {arquivo_html}")
                        
                        logger.debug(f"✅ Fetch OK: {url} ({len(html)} chars)")
                        return html
                    logger.warning(f"⚠️ Status {resp.status} para {url}")
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout (tentativa {tentativa + 1}/{cfg.MAX_RETRIES})")
            except Exception as e:
                logger.error(f"❌ Erro fetch {url}: {e}")
            
            if tentativa < cfg.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** tentativa)
        
        return None
    
    def _parse_tabela_proventos(self, html: str, ticker: str = "") -> List[Dict]:
        """Extrai proventos usando MÚLTIPLOS padrões de regex (fallback)"""
        proventos = []
        
        logger.info(f"🔍 Parse proventos para {ticker} - HTML size: {len(html)} chars")
        
        # ======================================================================
        # PADRÃO 1: Tabela clássica do Fundamentus
        # ======================================================================
        logger.debug("📊 Tentando Padrão 1: Tabela clássica...")
        
        # Busca a seção de proventos
        padrao_secao = r'(?:Proventos|Dividendos|JCP)[^<]*(?:</h[^>]*>|</div[^>]*>)'
        secao_match = re.search(padrao_secao, html, re.IGNORECASE | re.DOTALL)
        
        if secao_match:
            logger.debug("✅ Seção de proventos encontrada")
            
            # Extrai datas e valores da seção
            padrao_data_valor = r'(\d{2}/\d{2}/\d{4})[^0-9]{0,100}?R\$\s*([\d.,]+)'
            matches = re.findall(padrao_data_valor, html, re.IGNORECASE)
            
            for data_com, valor_str in matches[:10]:
                try:
                    valor_limpo = valor_str.replace('.', '').replace(',', '.')
                    valor = float(valor_limpo)
                    
                    if valor > 0.001:  # Filtra valores irrisórios
                        proventos.append({
                            "data_com": data_com,
                            "valor": valor,
                            "tipo": "Dividendo"
                        })
                        logger.debug(f"  💰 {data_com} | R$ {valor:.4f}")
                except (ValueError, IndexError) as e:
                    logger.debug(f"  ⚠️ Erro parse {data_com}: {e}")
        
        # ======================================================================
        # PADRÃO 2: Busca genérica por datas + valores monetários
        # ======================================================================
        if not proventos:
            logger.debug("📊 Tentando Padrão 2: Busca genérica...")
            
            # Busca TODAS as datas no HTML
            todas_datas = re.findall(r'(\d{2}/\d{2}/\d{4})', html)
            logger.debug(f"  📅 Datas encontradas: {len(todas_datas)}")
            
            # Busca TODOS os valores R$ no HTML
            todos_valores = re.findall(r'R\$\s*([\d.,]+)', html)
            logger.debug(f"  💰 Valores R$ encontrados: {len(todos_valores)}")
            
            # Tenta parear datas e valores próximos
            for i, data in enumerate(todas_datas[:20]):
                if i < len(todos_valores):
                    try:
                        valor_str = todos_valores[i]
                        valor_limpo = valor_str.replace('.', '').replace(',', '.')
                        valor = float(valor_limpo)
                        
                        if 0.01 <= valor <= 100:  # Faixa razoável para dividendos
                            proventos.append({
                                "data_com": data,
                                "valor": valor,
                                "tipo": "Dividendo"
                            })
                            logger.debug(f"  💰 {data} | R$ {valor:.4f}")
                    except (ValueError, IndexError):
                        pass
        
        # ======================================================================
        # PADRÃO 3: Extrai de tabelas HTML
        # ======================================================================
        if not proventos:
            logger.debug("📊 Tentando Padrão 3: Tabelas HTML...")
            
            # Busca tabelas
            tabelas = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
            logger.debug(f"  📋 Tabelas encontradas: {len(tabelas)}")
            
            for tabela in tabelas:
                # Extrai linhas
                linhas = re.findall(r'<tr[^>]*>(.*?)</tr>', tabela, re.DOTALL)
                
                for linha in linhas:
                    # Extrai células
                    celulas = re.findall(r'<td[^>]*>(.*?)</td>', linha, re.DOTALL)
                    
                    if len(celulas) >= 2:
                        # Limpa HTML
                        celulas_texto = [re.sub(r'<[^>]+>', '', c).strip() for c in celulas]
                        
                        # Busca data em alguma célula
                        for j, celula in enumerate(celulas_texto):
                            data_match = re.search(r'(\d{2}/\d{2}/\d{4})', celula)
                            if data_match:
                                data_com = data_match.group(1)
                                
                                # Busca valor R$ nas células seguintes
                                for k in range(j+1, min(j+3, len(celulas_texto))):
                                    valor_match = re.search(r'R\$\s*([\d.,]+)', celulas_texto[k])
                                    if valor_match:
                                        try:
                                            valor_str = valor_match.group(1)
                                            valor_limpo = valor_str.replace('.', '').replace(',', '.')
                                            valor = float(valor_limpo)
                                            
                                            if 0.01 <= valor <= 100:
                                                proventos.append({
                                                    "data_com": data_com,
                                                    "valor": valor,
                                                    "tipo": "Dividendo"
                                                })
                                                logger.debug(f"  💰 {data_com} | R$ {valor:.4f} (tabela)")
                                        except (ValueError, IndexError):
                                            pass
        
        logger.info(f"✅ Total proventos encontrados: {len(proventos)}")
        return proventos[:10]  # Máximo 10
    
    async def buscar_proventos(self, ticker: str, salvar_debug: bool = False) -> List[Dict]:
        """Busca proventos de um ticker"""
        url = f"{self.base_url}/proventos.php?papel={ticker.upper()}&interface=classic"
        logger.info(f"🔍 Buscando proventos: {ticker}")
        
        html = await self._fetch_page(url, salvar_html=salvar_debug, ticker=ticker)
        if not html:
            logger.warning(f"⚠️ HTML vazio para {ticker}")
            return []
        
        return self._parse_tabela_proventos(html, ticker)
    
    async def buscar_fatos_relevantes(self, ticker: str) -> List[Dict]:
        """Busca fatos relevantes (recompras, insiders)"""
        url = f"{self.base_url}/fatos_relevantes.php?papel={ticker.upper()}"
        logger.info(f"🔍 Buscando fatos relevantes: {ticker}")
        
        html = await self._fetch_page(url)
        if not html:
            return []
        
        return self._parse_fatos_relevantes(html, ticker)
    
    def _parse_fatos_relevantes(self, html: str, ticker: str) -> List[Dict]:
        """Extrai fatos relevantes do HTML"""
        fatos = []
        palavras_chave_recompra = ['recompra', 'buyback', 'aquisição de ações próprias', 'cancelamento de ações']
        palavras_chave_insider = ['negociação', 'diretor', 'conselho', 'insider', 'participação significativa']
        
        # Busca fatos relevantes
        padrao_fato = r'(\d{2}/\d{2}/\d{4})[^0-9]{0,50}?(FR|CO|FA)[^0-9]{0,100}?(?:Download|Comunicado)[^0-9]{0,100}?href="([^"]+)"'
        
        matches = re.findall(padrao_fato, html, re.IGNORECASE | re.DOTALL)
        
        for data, tipo, link in matches[:5]:
            descricao = f"Fato Relevante {tipo}"  # Simplificado
            descricao_lower = descricao.lower()
            
            categoria = None
            if any(p in descricao_lower for p in palavras_chave_recompra):
                categoria = "RECOMPRA"
            elif any(p in descricao_lower for p in palavras_chave_insider):
                categoria = "INSIDER"
            
            if categoria:
                fatos.append({
                    "data": data,
                    "tipo": tipo,
                    "descricao": descricao,
                    "categoria": categoria,
                    "link": f"{self.base_url}/{link}" if link.startswith('/') else link
                })
        
        return fatos

# ==============================================================================
# RADAR DE DIVIDENDOS
# ==============================================================================
class RadarDividendos:
    def __init__(self, scraper: FundamentusScraper, telegram: TelegramBot):
        self.scraper = scraper
        self.telegram = telegram
    
    async def executar(self, papeis: List[Dict[str, str]], salvar_debug_html: bool = False):
        """Varre todos os papéis"""
        logger.info("🚀 Iniciando radar de dividendos...")
        mes_ano = datetime.now().strftime("%b/%y").upper()
        
        await self.telegram.send_message(
            f"🤖 *Radar IDIV | {mes_ano}*\n"
            f"Varredura de {len(papeis)} ativos iniciada..."
        )
        
        total_alertas = 0
        total_encontrados = 0
        
        for i, papel in enumerate(papeis):
            ticker = papel["ticker"]
            nome = papel["nome"]
            
            # Salva HTML apenas no primeiro ticker para debug
            salvar = salvar_debug_html and (i == 0)
            
            proventos = await self.scraper.buscar_proventos(ticker, salvar_debug=salvar)
            total_encontrados += len(proventos)
            
            if proventos:
                logger.info(f"✅ {ticker}: {len(proventos)} proventos encontrados")
            else:
                logger.warning(f"⚠️ {ticker}: Nenhum provento encontrado")
            
            # Filtra proventos dos últimos 60 dias (ampliado para debug)
            hoje = datetime.now()
            proventos_recentes = []
            
            for prov in proventos:
                try:
                    data_com = datetime.strptime(prov["data_com"], "%d/%m/%Y")
                    dias_atras = (hoje - data_com).days
                    
                    if 0 <= dias_atras <= 60:  # Últimos 60 dias
                        prov["dias_atras"] = dias_atras
                        proventos_recentes.append(prov)
                except ValueError:
                    continue
            
            # Envia alertas
            for prov in proventos_recentes:
                msg = (
                    f"#{ticker} | {mes_ano} | {nome}\n\n"
                    f"💰 *PROVENTO ENCONTRADO:*\n"
                    f"💵 *Valor:* R$ {prov['valor']:.4f} por ação\n"
                    f"📅 *Data COM:* {prov['data_com']}\n"
                    f"📊 *Dias atrás:* {prov.get('dias_atras', 'N/A')} dias\n"
                    f"📊 *Tipo:* {prov.get('tipo', 'Dividendo')}"
                )
                
                await self.telegram.send_message(msg, ticker)
                total_alertas += 1
        
        logger.info(f"✅ Radar dividendos: {total_alertas} alertas / {total_encontrados} encontrados")
        
        # Mensagem de status
        if total_alertas == 0:
            await self.telegram.send_message(
                f"ℹ️ *Status da Varredura:*\n\n"
                f"📊 Ativos varridos: {len(papeis)}\n"
                f"🔍 Proventos encontrados: {total_encontrados}\n"
                f"⚠️ Nenhum provento com Data COM nos últimos 60 dias\n\n"
                f"💡 *Nota:* Verifique os logs para detalhes."
            )
        else:
            await self.telegram.send_message(
                f"✅ *Varredura Concluída!*\n\n"
                f"📊 Ativos varridos: {len(papeis)}\n"
                f"🔍 Total proventos: {total_encontrados}\n"
                f"📣 Alertas enviados: {total_alertas}"
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
        self.alertas_enviados = set()
        if self.arquivo_cache.exists():
            with open(self.arquivo_cache, "r", encoding="utf-8") as f:
                self.alertas_enviados = set(f.read().splitlines())
            logger.info(f"📦 Cache carregado: {len(self.alertas_enviados)} alertas")
    
    def _registrar_alerta(self, link: str):
        self.alertas_enviados.add(link)
        with open(self.arquivo_cache, "a", encoding="utf-8") as f:
            f.write(f"{link}\n")
    
    async def executar(self, papeis: List[Dict[str, str]]):
        """Varre todos os papéis"""
        logger.info("🚀 Iniciando radar de recompras e insiders...")
        
        total_recompras = 0
        total_insiders = 0
        
        for papel in papeis:
            ticker = papel["ticker"]
            
            fatos = await self.scraper.buscar_fatos_relevantes(ticker)
            
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
        logger.info("🔧 Inicializando bot...")
        
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        self.session = aiohttp.ClientSession(connector=connector)
        self.telegram = TelegramBot(cfg.TOKEN, cfg.CHAT_ID, self.session)
        self.scraper = FundamentusScraper(self.session)
        
        logger.info("✅ Bot inicializado")
    
    async def fechar(self):
        if self.session:
            await self.session.close()
            logger.info("🔒 Sessões fechadas")
    
    async def executar_rotina(self, salvar_debug_html: bool = True):
        """Executa toda a rotina"""
        try:
            await self.inicializar()
            
            radar_div = RadarDividendos(self.scraper, self.telegram)
            radar_rec = RadarRecomprasInsiders(self.scraper, self.telegram)
            
            await asyncio.gather(
                radar_div.executar(cfg.MEUS_PAPEIS, salvar_debug_html=salvar_debug_html),
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
    # Salva HTML de debug na primeira execução
    await bot.executar_rotina(salvar_debug_html=True)

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🤖 RADAR IDIV - Bot de Investimentos B3")
    logger.info("🔍 Versão DEBUG - Salvando HTML para análise")
    logger.info("=" * 60)
    
    asyncio.run(main())
