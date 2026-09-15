"""
🤖 RADAR IDIV - Bot Telegram
Fontes: Fundamentus, StatusInvest, Yahoo Finance (fallback)
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import re

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
    TIMEOUT: int = 20
    MAX_RETRIES: int = 2
    
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
                    {"text": f"📈 {ticker}", "url": f"https://statusinvest.com.br/acoes/{ticker.lower()}"}
                ]]
            }
        
        try:
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                logger.info(f"✅ Telegram: {ticker or 'OK'}")
                return True
        except Exception as e:
            logger.error(f"❌ Telegram: {e}")
        return False

# ==============================================================================
# MULTI-FONTE SCRAPER
# ==============================================================================
class MultiFonteScraper:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9',
        }
    
    async def buscar_proventos(self, ticker: str) -> List[Dict]:
        """Busca proventos usando múltiplas fontes com fallback"""
        logger.info(f"🔍 Buscando proventos: {ticker}")
        
        # Fonte 1: StatusInvest
        proventos = await self._buscar_statusinvest(ticker)
        if proventos:
            logger.info(f"✅ StatusInvest: {len(proventos)} proventos")
            return proventos
        
        # Fonte 2: Fundamentus
        proventos = await self._buscar_fundamentus(ticker)
        if proventos:
            logger.info(f"✅ Fundamentus: {len(proventos)} proventos")
            return proventos
        
        # Fonte 3: Yahoo Finance
        proventos = await self._buscar_yahoo(ticker)
        if proventos:
            logger.info(f"✅ Yahoo: {len(proventos)} proventos")
            return proventos
        
        logger.warning(f"⚠️ Nenhuma fonte retornou dados para {ticker}")
        return []
    
    async def _buscar_statusinvest(self, ticker: str) -> List[Dict]:
        """Scraping StatusInvest"""
        try:
            url = f"https://statusinvest.com.br/acoes/{ticker.lower()}"
            
            async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=cfg.TIMEOUT)) as resp:
                if resp.status != 200:
                    return []
                
                html = await resp.text(encoding='utf-8')
                return self._parse_proventos_html(html, ticker, "StatusInvest")
        except Exception as e:
            logger.debug(f"⚠️ StatusInvest falhou: {e}")
            return []
    
    async def _buscar_fundamentus(self, ticker: str) -> List[Dict]:
        """Scraping Fundamentus"""
        try:
            url = f"https://fundamentus.com.br/proventos.php?papel={ticker}&interface=classic"
            
            async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=cfg.TIMEOUT)) as resp:
                if resp.status != 200:
                    return []
                
                html = await resp.text(encoding='utf-8')
                return self._parse_proventos_html(html, ticker, "Fundamentus")
        except Exception as e:
            logger.debug(f"⚠️ Fundamentus falhou: {e}")
            return []
    
    async def _buscar_yahoo(self, ticker: str) -> List[Dict]:
        """Yahoo Finance via yfinance (se instalado)"""
        try:
            import yfinance as yf
            acao = yf.Ticker(f"{ticker}.SA")
            dividendos = acao.dividends
            
            if dividendos.empty:
                return []
            
            proventos = []
            for data, valor in dividendos.items():
                proventos.append({
                    "data_com": data.strftime("%d/%m/%Y"),
                    "valor": float(valor),
                    "tipo": "Dividendo",
                    "fonte": "Yahoo"
                })
            
            return proventos[-10:]
        except Exception as e:
            logger.debug(f"⚠️ Yahoo falhou: {e}")
            return []
    
    def _parse_proventos_html(self, html: str, ticker: str, fonte: str) -> List[Dict]:
        """Parse genérico de HTML"""
        proventos = []
        
        # Busca todas as datas e valores R$
        datas = re.findall(r'(\d{2}/\d{2}/\d{4})', html)
        valores = re.findall(r'R\$\s*([\d.,]+)', html)
        
        logger.debug(f"  {fonte}: {len(datas)} datas, {len(valores)} valores")
        
        # Tenta parear datas e valores próximos
        for i in range(min(len(datas), len(valores), 20)):
            try:
                valor_str = valores[i]
                valor_limpo = valor_str.replace('.', '').replace(',', '.')
                valor = float(valor_limpo)
                
                if 0.01 <= valor <= 100:
                    proventos.append({
                        "data_com": datas[i],
                        "valor": valor,
                        "tipo": "Dividendo",
                        "fonte": fonte
                    })
            except (ValueError, IndexError):
                pass
        
        return proventos[:10]

# ==============================================================================
# RADAR DE DIVIDENDOS
# ==============================================================================
class RadarDividendos:
    def __init__(self, scraper: MultiFonteScraper, telegram: TelegramBot):
        self.scraper = scraper
        self.telegram = telegram
    
    async def executar(self, papeis: List[Dict[str, str]]):
        logger.info("🚀 Iniciando radar de dividendos...")
        mes_ano = datetime.now().strftime("%b/%y").upper()
        
        await self.telegram.send_message(
            f"🤖 *Radar IDIV | {mes_ano}*\n"
            f"Varredura de {len(papeis)} ativos iniciada..."
        )
        
        total_alertas = 0
        total_encontrados = 0
        
        for papel in papeis:
            ticker = papel["ticker"]
            nome = papel["nome"]
            
            proventos = await self.scraper.buscar_proventos(ticker)
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
                    f"💰 *PROVENTO ENCONTRADO [{prov['fonte']}]*\n"
                    f"💵 *Valor:* R$ {prov['valor']:.4f} por ação\n"
                    f"📅 *Data COM:* {prov['data_com']}\n"
                    f"📊 *Dias atrás:* {prov.get('dias_atras', 'N/A')} dias"
                )
                
                await self.telegram.send_message(msg, ticker)
                total_alertas += 1
        
        logger.info(f"✅ Radar: {total_alertas} alertas / {total_encontrados} encontrados")
        
        if total_alertas == 0:
            await self.telegram.send_message(
                f"ℹ️ *Status:*\n\n"
                f"📊 Ativos: {len(papeis)}\n"
                f"🔍 Encontrados: {total_encontrados}\n"
                f"⚠️ Nenhum provento nos últimos 60 dias"
            )
        else:
            await self.telegram.send_message(
                f"✅ *Concluído!*\n\n"
                f"📊 Ativos: {len(papeis)}\n"
                f"🔍 Total: {total_encontrados}\n"
                f"📣 Alertas: {total_alertas}"
            )

# ==============================================================================
# ORQUESTRADOR
# ==============================================================================
class BotInvestimentos:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.telegram: Optional[TelegramBot] = None
        self.scraper: Optional[MultiFonteScraper] = None
    
    async def inicializar(self):
        logger.info("🔧 Inicializando...")
        
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        self.session = aiohttp.ClientSession(connector=connector)
        self.telegram = TelegramBot(cfg.TOKEN, cfg.CHAT_ID, self.session)
        self.scraper = MultiFonteScraper(self.session)
        
        logger.info("✅ Inicializado")
    
    async def fechar(self):
        if self.session:
            await self.session.close()
    
    async def executar_rotina(self):
        try:
            await self.inicializar()
            
            radar = RadarDividendos(self.scraper, self.telegram)
            await radar.executar(cfg.MEUS_PAPEIS)
            
            logger.info("✅ Finalizado")
            
        except Exception as e:
            logger.error(f"❌ Erro: {e}", exc_info=True)
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
    logger.info("🤖 RADAR IDIV - Multi-Fonte")
    logger.info("=" * 60)
    
    asyncio.run(main())
