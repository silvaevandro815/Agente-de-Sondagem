import os
import time
import logging
from datetime import datetime
from supabase import create_client, Client
from playwright.sync_api import sync_playwright
import requests
from bs4 import BeautifulSoup
import unicodedata
import urllib.parse

# ==========================================
# CONFIGURAÇÃO DE LOGS
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# CREDENCIAIS E VARIÁVEIS DE AMBIENTE
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CIDADES_ALVO = os.getenv("CIDADES_ALVO", "São Paulo, SP").split(";")
INTERVALO_HORAS = int(os.getenv("INTERVALO_HORAS", 1))

def init_supabase() -> Client | None:
    """Inicializa e retorna o cliente Supabase."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            logger.error(f"Erro ao conectar com Supabase: {e}")
    else:
        logger.warning("Credenciais do Supabase não encontradas. O script continuará, mas não salvará no banco.")
    return None

def salvar_no_supabase(supabase: Client, dados: dict):
    """Salva um dicionário de dados na tabela prospeccao_agencia."""
    if not supabase:
        logger.info(f"Modo Teste - Dados capturados: {dados}")
        return
        
    try:
        data, count = supabase.table("prospeccao_agencia").upsert(dados, on_conflict='telefone').execute()
        logger.info(f"Sucesso ao salvar/atualizar clínica: {dados.get('nome')}")
    except Exception as e:
        logger.error(f"Erro ao salvar no Supabase: {e}")

def sanitizar_telefone(telefone: str) -> str:
    """Sanitiza o telefone para o formato 55+DDD+Numero."""
    if not telefone:
        return ""
        
    # Remove caracteres não numéricos
    numeros = ''.join(filter(str.isdigit, telefone))
    if not numeros:
        return ""
        
    # Verifica se é 0800 ou 4004 antes de alterar
    if numeros.startswith('0800') or numeros.startswith('4004'):
        logger.warning(f"Aviso: O número {telefone} é um telefone especial (0800/4004) e provavelmente falhará no Handoff do WhatsApp.")
        
    # Remove '0' inicial (ex: 032988887777 -> 32988887777)
    if numeros.startswith('0'):
        numeros = numeros[1:]
        
    # Verifica se já possui o DDI 55
    if not numeros.startswith('55'):
        numeros = '55' + numeros
        
    return numeros

def sanitizar_cidade(cidade: str) -> str:
    """Remove acentos e formata a cidade para a URL."""
    return ''.join(c.lower() for c in unicodedata.normalize('NFD', cidade) if unicodedata.category(c) != 'Mn')

def buscar_clinicas(page, cidade):
    """Busca clínicas médicas no Google Maps e extrai as informações básicas."""
    logger.info(f"Buscando clínicas médicas em: {cidade}")
    # Formata e sanitiza a URL de busca
    cidade_sanitizada = sanitizar_cidade(cidade)
    busca = f"clinicas medicas em {cidade_sanitizada}"
    busca_encoded = urllib.parse.quote(busca)
    url = f"https://www.google.com/maps/search/{busca_encoded}/"
    
    try:
        page.goto(url, timeout=60000)
        page.wait_for_timeout(5000) # Espera renderizar os resultados
    except Exception as e:
        logger.error(f"Erro ao carregar Google Maps: {e}")
        return []

    clinicas = []
    
    try:
        # Busca pelos links dos locais na barra lateral
        links = page.locator("a[href*='/maps/place/']").all()
        logger.info(f"Foram encontrados {len(links)} resultados (podem incluir duplicadas). Limitando a 15 para análise.")
        
        # Limita a 15 resultados por ciclo para não demorar tanto
        for link in links[:15]:
            try:
                link.click()
                page.wait_for_timeout(3000) # Espera abrir as informações do local
                
                page.wait_for_timeout(2000) # Força espera para o DOM carregar completamente os botões
                
                # Nome do Local
                nome_locators = page.locator("h1.fontHeadlineLarge, div.fontHeadlineLarge, h1").all()
                nome = "Nome Indisponível"
                for loc in nome_locators:
                    texto = loc.inner_text().strip()
                    texto_lower = texto.lower()
                    if texto and texto_lower not in ["resultados", "results"] and not any(palavra in texto_lower for palavra in ["patrocinado", "anúncio", "anuncio", "sponsored"]):
                        nome = texto
                        break
                
                # Telefone e Site
                telefone = ""
                site = ""
                
                botoes = page.locator("button[data-item-id]").all()
                for el in botoes:
                    item_id = el.get_attribute("data-item-id")
                    if not item_id:
                        continue
                    if item_id.startswith("phone:"):
                        telefone = item_id.replace("phone:tel:", "")
                    if item_id.startswith("authority:"):
                        site = el.inner_text()
                        if site and not site.startswith("http"):
                            site = "https://" + site
                            
                # Tentar extrair o Site de forma mais robusta via link
                # 1. Prioriza links que o Google identifica como site oficial
                links_oficiais = page.locator('a[data-value="Website"], a.lcr4fd, a[data-item-id="authority"]').all()
                for link_el in links_oficiais:
                    href = link_el.get_attribute("href")
                    if href and not href.startswith("/") and "/maps/" not in href and "/aclk" not in href:
                        site = href
                        break
                        
                # 2. Fallback: busca por domínios comuns em todos os links da página
                if not site or "google.com" in site or "/aclk" in site:
                    links_gerais = page.locator("a[href]").all()
                    for link_el in links_gerais:
                        href = link_el.get_attribute("href")
                        href_lower = href.lower() if href else ""
                        if href_lower and not href_lower.startswith("/") and "/maps/" not in href_lower and "/search/" not in href_lower and "google.com" not in href_lower and "/aclk" not in href_lower:
                            if ".com" in href_lower or ".med.br" in href_lower or ".net" in href_lower or ".org" in href_lower or ".br" in href_lower:
                                site = href
                                break
                        
                # Filtro rigoroso para anúncios do Google Maps e URLs inválidas
                if site:
                    if "/aclk" in site or not (site.startswith("http://") or site.startswith("https://")):
                        site = None
                
                if nome != "Nome Indisponível":
                    clinicas.append({
                        "nome": nome,
                        "telefone": telefone,
                        "site": site
                    })
                    logger.info(f"Capturado: {nome} | Tel: {telefone} | Site: {site}")
                    
            except Exception as e:
                logger.error(f"Erro ao processar um item específico do mapa: {e}")
                
    except Exception as e:
        logger.error(f"Erro durante a extração de listagem do Maps: {e}")
        
    return clinicas

def analisar_site(site_url):
    """Acessa o site para verificar presença de Chatbot/WhatsApp e busca pelo Instagram."""
    if not site_url or "google.com" in site_url:
        return False, None
        
    if not site_url.startswith("http"):
        site_url = "http://" + site_url
            
    logger.info(f"Analisando site: {site_url}")
    tem_chatbot = False
    link_instagram = None
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        response = requests.get(site_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            html_text = response.text.lower()
            
            # Verificação de IA / WhatsApp
            keywords = ["whatsapp", "wa.me", "chat", "bot", "zopim", "tawk", "intercom"]
            if any(keyword in html_text for keyword in keywords):
                tem_chatbot = True
                
            # Busca link do instagram
            for a in soup.find_all('a', href=True):
                href = a['href']
                if "instagram.com" in href.lower():
                    link_instagram = href
                    break
                    
    except requests.exceptions.RequestException as e:
        logger.warning(f"Não foi possível acessar o site {site_url}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao analisar site {site_url}: {e}")
        
    return tem_chatbot, link_instagram

def analisar_instagram(page, link_instagram):
    """Acessa o Instagram e tenta buscar a data da última postagem."""
    if not link_instagram:
        return None
        
    logger.info(f"Analisando perfil do Instagram: {link_instagram}")
    try:
        page.goto(link_instagram, timeout=30000)
        page.wait_for_timeout(4000) # Espera para renderizar DOM
        
        # O DOM do Instagram muda frequentemente e limita acesso sem login.
        # Tentamos encontrar o elemento 'time'
        time_elements = page.locator("time").all()
        if time_elements:
            data_postagem = time_elements[0].get_attribute("datetime")
            logger.info(f"Encontrada última postagem em: {data_postagem}")
            return data_postagem
        else:
            logger.info("Não foi possível encontrar a data da última postagem (Pode estar bloqueado sem login).")
            return None
            
    except Exception as e:
        logger.warning(f"Erro ao acessar Instagram {link_instagram}: {e}")
        return None

def executar_varredura():
    """Função principal que orquestra todo o fluxo."""
    logger.info("=== Iniciando nova varredura de prospecção ===")
    supabase = init_supabase()
    
    with sync_playwright() as p:
        # Usamos navegador headless para maior eficiência
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        
        for cidade in CIDADES_ALVO:
            cidade = cidade.strip()
            if not cidade:
                continue
                
            clinicas = buscar_clinicas(page, cidade)
            
            for clinica in clinicas:
                tem_chatbot, link_instagram = analisar_site(clinica.get('site'))
                data_postagem = analisar_instagram(page, link_instagram)
                
                telefone_sanitizado = sanitizar_telefone(clinica.get('telefone'))
                
                # Monta objeto final
                dados = {
                    "nome": clinica.get('nome'),
                    "telefone": telefone_sanitizado,
                    "link_site": clinica.get('site'),
                    "status_chatbot": tem_chatbot,
                    "link_instagram": link_instagram,
                    "data_ultima_postagem": data_postagem,
                    "cidade": cidade,
                    "data_captura": datetime.now().isoformat(),
                    "status_prospeccao": "pendente"
                }
                
                # Salva no banco de dados Supabase
                salvar_no_supabase(supabase, dados)
                
        browser.close()
    logger.info("=== Varredura concluída com sucesso ===")

if __name__ == "__main__":
    logger.info("=========================================")
    logger.info("🤖 Agente de Sondagem Iniciado")
    logger.info(f"📍 Cidades Alvo: {', '.join(CIDADES_ALVO)}")
    logger.info(f"⏳ Intervalo configurado: {INTERVALO_HORAS} hora(s)")
    logger.info("=========================================")
    
    # Loop Infinito de Execução
    while True:
        try:
            executar_varredura()
        except Exception as e:
            logger.error(f"Ocorreu um erro crítico durante o ciclo de varredura: {e}")
            
        logger.info(f"Aguardando {INTERVALO_HORAS} hora(s) até a próxima varredura...")
        time.sleep(INTERVALO_HORAS * 3600)
