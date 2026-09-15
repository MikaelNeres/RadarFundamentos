"""
🤖 RADAR IDIV - Bot Telegram para Monitoramento de Ativos B3
Fonte: Sites de RI (Relações com Investidores)
Foco: CMIG4, BBAS3, SAPR11
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import re

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
class Config:
    TOKEN: str = '8734276492:AAGR92m7XYBWo_Ac5SHvbVBQL9K40ErIsrE'
    CHAT_ID: str = '566929604'
    TIMEOUT: int = 15
    MAX_RETRIES: int = 3
    
    # URLs oficiais de RI das 3 empresas
    URLS_RI = {
        "CMIG4": {
            "nome": "CEMIG",
            "proventos": "https://ri.cemig.com.br/dividendos/",
            "fatos": "https://ri.cemig.com.br/fatos-relevantes/",
        },
        "BBAS3": {
            "nome": "BANCO DO BRASIL",
            "proventos": "https://ri.bb.com.br/informacoes-do-acionista/proventos/",
            "fatos": "https://ri.bb.com.br/informacoes-ao-mercado/fatos-relevantes/",
        },
        "SAPR11": {
            "nome": "SANEPAR",
            "proventos": "https://www.sanepar.com.br/ri/proventos/",
            "fatos": "https://www.sanepar.com.br/ri/fatos-relevantes/",
        },
    }

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
                    {"text": f"📈 RI {ticker}", "url": cfg.URLS_RI[ticker]["proventos"]}
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
# SCRAPER DE RI
# ==============================================================================
class RIScraper:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        }
    
    async def buscar_proventos(self, ticker: str) -> List[Dict]:
        """Busca proventos diretamente no site de RI"""
        
        if ticker not in cfg.URLS_RI:
            logger.warning(f"⚠️ RI não cadastrado para {ticker}")
            return []
        
        url = cfg.URLS_RI[ticker]["proventos"]
        logger.info(f"🔍 [RI] Buscando proventos: {ticker}")
        
        for tentativa in range(cfg.MAX_RETRIES):
            try:
                async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=cfg.TIMEOUT)) as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ [RI] Status {resp.status} para {ticker}")
                        return []
                    
                    html = await resp.text(encoding='utf-8')
                    logger.info(f"✅ [RI] HTML baixado: {len(html)} chars")
                    
                    # Salva HTML para debug
                    with open(f"debug_ri_{ticker.lower()}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    logger.info(f"💾 HTML salvo: debug_ri_{ticker.lower()}.html")
                    
                    proventos = self._parse_proventos(html, ticker)
                    logger.info(f"✅ [RI] {ticker}: {len(proventos)} proventos encontrados")
                    return proventos
                    
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout (tentativa {tentativa + 1}/{cfg.MAX_RETRIES})")
            except Exception as e:
                logger.error(f"❌ [RI] Erro ao buscar {ticker}: {e}")
            
            if tentativa < cfg.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** tentativa)
        
        return []
    
    def _parse_proventos(self, html: str, ticker: str) -> List[Dict]:
        """Parse de proventos - Múltiplos padrões de fallback"""
        proventos = []
        
        logger.debug(f"🔍 Parse proventos para {ticker}")
        
        # ======================================================================
        # PADRÃO 1: Tabela HTML (mais comum em RIs)
        # ======================================================================
        tabelas = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
        
        for tabela in tabelas:
            linhas = re.findall(r'<tr[^>]*>(.*?)</tr>', tabela, re.DOTALL)
            
            for linha in linhas:
                celulas = re.findall(r'<td[^>]*>(.*?)</td>', linha, re.DOTALL)
                
                if len(celulas) >= 3:
                    # Limpa HTML das células
                    celulas_texto = [re.sub(r'<[^>]+>', '', c).strip() for c in celulas]
                    
                    # Busca data no formato DD/MM/AAAA
                    for j, celula in enumerate(celulas_texto):
                        data_match = re.search(r'(\d{2}/\d{2}/\d{4})', celula)
                        
                        if data_match:
                            data_com = data_match.group(1)
                            
                            # Busca valor R$ nas células seguintes
                            for k in range(j+1, min(j+4, len(celulas_texto))):
                                valor_match = re.search(r'R\$\s*([\d.,]+)', celulas_texto[k])
                                
                                if valor_match:
                                    try:
                                        valor_str = valor_match.group(1)
                                        valor_limpo = valor_str.replace('.', '').replace(',', '.')
                                        valor = float(valor_limpo)
                                        
                                        if 0.01 <= valor <= 100:  # Faixa razoável
                                            proventos.append({
                                                "data_com": data_com,
                                                "valor": valor,
                                                "tipo": "Dividendo",
                                                "fonte": "RI"
                                            })
                                            logger.debug(f"  💰 {data_com} | R$ {valor:.4f}")
                                    except (ValueError, IndexError):
                                        pass
        
        # ======================================================================
        # PADRÃO 2: Busca genérica por datas + valores
        # ======================================================================
        if not proventos:
            logger.debug("🔍 Tentando padrão genérico...")
            
            # Busca todas as datas
            datas = re.findall(r'(\d{2}/\d{2}/\d{4})', html)
            
            # Busca todos os valores R$
            valores = re.findall(r'R\$\s*([\d.,]+)', html)
            
            # Tenta parear
            for i in range(min(len(datas), len(valores))):
                try:
                    valor_str = valores[i]
                    valor_limpo = valor_str.replace('.', '').replace(',', '.')
                    valor = float(valor_limpo)
                    
                    if 0.01 <= valor <= 100:
                        proventos.append({
                            "data_com": datas[i],
                            "valor": valor,
                            "tipo": "Dividendo",
                            "fonte": "RI"
                        })
                        logger.debug(f"  💰 {datas[i]} | R$ {valor:.4f} (genérico)")
                except (ValueError, IndexError):
                    pass
        
        return proventos[:10]  # Máximo 10
    
    async def buscar_fatos_relevantes(self, ticker: str) -> List[Dict]:
        """Busca fatos relevantes (recompras, insiders)"""
        
        if ticker not in cfg.URLS_RI:
            return []
        
        url = cfg.URLS_RI[ticker]["fatos"]
        logger.info(f"🔍 [RI] Buscando fatos relevantes: {ticker}")
        
        try:
            async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=cfg.TIMEOUT)) as resp:
                if resp.status != 200:
                    return []
                
                html = await resp.text(encoding='utf-8')
                return self._parse_fatos(html, ticker, url)
                
        except Exception as e:
            logger.error(f"❌ [RI] Erro fatos relevantes {ticker}: {e}")
            return []
    
    def _parse_fatos(self, html: str, ticker: str, url: str) -> List[Dict]:
        """Parse de fatos relevantes"""
        fatos = []
        
        palavras_chave = {
            "recompra": "RECOMPRA",
            "buyback": "RECOMPRA",
            "ações próprias": "RECOMPRA",
            "diretor": "INSIDER",
            "conselho": "INSIDER",
            "participação": "INSIDER",
        }
        
        # Busca datas + descrições
        padrao = r'(\d{2}/\d{2}/\d{4})[^0-9]{0,200}?(recompra|buyback|diretor|conselho|participação)'
        matches = re.findall(padrao, html, re.IGNORECASE)
        
        for data, palavra in matches[:5]:
            categoria = palavras_chave.get(palavra.lower(), "OUTRO")
            
            fatos.append({
                "data": data,
                "tipo": "FR",
                "descricao": f"Fato relevante: {palavra}",
                "categoria": categoria,
                "link": url,
                "fonte": "RI"
            })
        
        return fatos

# ==============================================================================
# RADAR DE DIVIDENDOS
# ==============================================================================
class RadarDividendos:
    def __init__(self, scraper: RIScraper, telegram: TelegramBot):
        self.scraper = scraper
        self.telegram = telegram
    
    async def executar(self, tickers: List[str]):
        """Varre tickers de RI"""
        logger.info("🚀 Iniciando radar de dividendos (RI)...")
        mes_ano = datetime.now().strftime("%b/%y").upper()
        
        await self.telegram.send_message(
            f"🤖 *Radar IDIV | {mes_ano}*\n"
            f"Varredura de {len(tickers)} ativos (RI) iniciada..."
        )
        
        total_alertas = 0
        total_encontrados = 0
        
        for ticker in tickers:
            nome = cfg.URLS_RI[ticker]["nome"]
            
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
                    f"💰 *PROVENTO ENCONTRADO [RI]*\n"
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
                f"📊 Ativos varridos: {len(tickers)}\n"
                f"🔍 Proventos encontrados: {total_encontrados}\n"
                f"⚠️ Nenhum provento com Data COM nos últimos 60 dias\n\n"
                f"💡 *Nota:* Verifique os arquivos debug_ri_*.html"
            )
        else:
            await self.telegram.send_message(
                f"✅ *Varredura Concluída!*\n\n"
                f"📊 Ativos varridos: {len(tickers)}\n"
                f"🔍 Total proventos: {total_encontrados}\n"
                f"📣 Alertas enviados: {total_alertas}"
            )

# ==============================================================================
# RADAR DE RECOMPRAS E INSIDERS
# ==============================================================================
class RadarRecomprasInsiders:
    def __init__(self, scraper: RIScraper, telegram: TelegramBot):
        self.scraper = scraper
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
    
    async def executar(self, tickers: List[str]):
        """Varre fatos relevantes"""
        logger.info("🚀 Iniciando radar de recompras e insiders...")
        
        total_alertas = 0
        
        for ticker in tickers:
            fatos = await self.scraper.buscar_fatos_relevantes(ticker)
            
            for fato in fatos:
                if not self._ja_enviado(fato["link"]):
                    if fato["categoria"] == "RECOMPRA":
                        msg = (
                            f"🚨 *RECOMPRA DETECTADA:* #{ticker}\n\n"
                            f"📅 *Data:* {fato['data']}\n"
                            f"📄 *Fato:* {fato['descricao']}\n\n"
                            f"💡 *Impacto:* Redução da base acionária → LPA maior\n"
                            f"🔗 [Ler comunicado]({fato['link']})"
                        )
                        
                        await self.telegram.send_message(msg, ticker)
                        self._registrar_alerta(fato["link"])
                        total_alertas += 1
                    
                    elif fato["categoria"] == "INSIDER":
                        msg = (
                            f"👁️ *MOVIMENTAÇÃO DE INSIDER:* #{ticker}\n\n"
                            f"📅 *Data:* {fato['data']}\n"
                            f"📄 *Fato:* {fato['descricao']}\n\n"
                            f"💡 *Sinal:* Insiders conhecem a empresa melhor\n"
                            f"🔗 [Ler comunicado]({fato['link']})"
                        )
                        
                        await self.telegram.send_message(msg, ticker)
                        self._registrar_alerta(fato["link"])
                        total_alertas += 1
        
        logger.info(f"✅ Radar fatos relevantes: {total_alertas} alertas")
    
    def _ja_enviado(self, link: str) -> bool:
        return link in self.alertas_enviados

# ==============================================================================
# ORQUESTRADOR PRINCIPAL
# ==============================================================================
class BotInvestimentos:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.telegram: Optional[TelegramBot] = None
        self.scraper: Optional[RIScraper] = None
    
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
        self.scraper = RIScraper(self.session)
        
        logger.info("✅ Bot inicializado")
    
    async def fechar(self):
        if self.session:
            await self.session.close()
            logger.info("🔒 Sessões fechadas")
    
    async def executar_rotina(self):
        """Executa toda a rotina"""
        try:
            await self.inicializar()
            
            # Apenas os 3 tickers de RI
            tickers_ri = ["CMIG4", "BBAS3", "SAPR11"]
            
            radar_div = RadarDividendos(self.scraper, self.telegram)
            radar_rec = RadarRecomprasInsiders(self.scraper, self.telegram)
            
            await asyncio.gather(
                radar_div.executar(tickers_ri),
                radar_rec.executar(tickers_ri)
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
    logger.info("🏢 Fonte: Sites de RI (CMIG4, BBAS3, SAPR11)")
    logger.info("=" * 60)
    
    asyncio.run(main())
