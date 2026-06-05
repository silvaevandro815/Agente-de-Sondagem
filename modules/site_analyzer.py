import logging
import re
import requests
from config import (
    IA_AVANCADA_SIGNATURES,
    CHAT_HUMANO_SIGNATURES,
    WHATSAPP_SIGNATURES,
    DEFAULT_USER_AGENT
)

logger = logging.getLogger('AgenteSondagem.SiteAnalyzer')

# Regex para extrair redes sociais
SOCIAL_PATTERNS = {
    'instagram': re.compile(r'https?://(?:www\.)?instagram\.com/[\w.]+/?', re.IGNORECASE),
    'facebook': re.compile(r'https?://(?:www\.)?(?:facebook\.com|fb\.com)/[\w.]+/?', re.IGNORECASE),
    'linkedin': re.compile(r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[\w\-]+/?', re.IGNORECASE),
    'youtube': re.compile(r'https?://(?:www\.)?youtube\.com/(?:@|channel/|c/)[\w\-]+/?', re.IGNORECASE),
    'tiktok': re.compile(r'https?://(?:www\.)?tiktok\.com/@[\w.]+/?', re.IGNORECASE),
}

# Links genéricos que devem ser ignorados
LINKS_GENERICOS = [
    'instagram.com/p/', 'instagram.com/reel/', 'instagram.com/stories/',
    'facebook.com/sharer', 'facebook.com/share', 'facebook.com/dialog',
    'linkedin.com/sharing', 'youtube.com/watch',
]


def analisar_site(site_url: str) -> dict:
    """Analisa um site para detectar chatbots, IA e redes sociais."""
    resultado = {
        'tem_chatbot': False,
        'tem_ia_avancada': False,
        'tecnologias_detectadas': [],
        'link_instagram': None,
        'link_facebook': None,
        'link_linkedin': None,
        'link_youtube': None,
        'link_tiktok': None,
        'tem_whatsapp': False,
    }

    if not site_url or "google.com" in site_url:
        return resultado

    if not site_url.startswith("http"):
        site_url = "https://" + site_url

    logger.info(f"🔍 Analisando site: {site_url}")

    try:
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        response = requests.get(site_url, headers=headers, timeout=15, allow_redirects=True)

        if response.status_code != 200:
            logger.warning(f"Site retornou status {response.status_code}: {site_url}")
            return resultado

        html_lower = response.text.lower()

        # ===== DETECÇÃO DE IA AVANÇADA =====
        for provider, signatures in IA_AVANCADA_SIGNATURES.items():
            if any(sig.lower() in html_lower for sig in signatures):
                resultado['tem_ia_avancada'] = True
                resultado['tem_chatbot'] = True
                resultado['tecnologias_detectadas'].append(f"IA:{provider}")
                logger.info(f"  🤖 IA Avançada detectada: {provider}")

        # ===== DETECÇÃO DE CHAT HUMANO =====
        for provider, signatures in CHAT_HUMANO_SIGNATURES.items():
            if any(sig.lower() in html_lower for sig in signatures):
                resultado['tem_chatbot'] = True
                resultado['tecnologias_detectadas'].append(f"Chat:{provider}")
                logger.info(f"  💬 Chat humano detectado: {provider}")

        # ===== DETECÇÃO DE WHATSAPP =====
        if any(sig.lower() in html_lower for sig in WHATSAPP_SIGNATURES):
            resultado['tem_whatsapp'] = True
            resultado['tecnologias_detectadas'].append("WhatsApp")
            logger.info(f"  📱 WhatsApp detectado")

        # ===== EXTRAÇÃO DE REDES SOCIAIS =====
        for rede, pattern in SOCIAL_PATTERNS.items():
            matches = pattern.findall(response.text)
            for match in matches:
                # Filtrar links genéricos
                if any(generico in match.lower() for generico in LINKS_GENERICOS):
                    continue
                campo = f'link_{rede}'
                if resultado[campo] is None:
                    resultado[campo] = match.rstrip('/')
                    logger.info(f"  🌐 {rede.capitalize()}: {match}")
                break

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout ao acessar: {site_url}")
    except requests.exceptions.ConnectionError:
        logger.warning(f"Erro de conexão com: {site_url}")
    except Exception as e:
        logger.error(f"Erro inesperado ao analisar site {site_url}: {e}")

    # Converte lista de tecnologias para string
    resultado['tecnologias_detectadas'] = ', '.join(resultado['tecnologias_detectadas']) if resultado['tecnologias_detectadas'] else None

    return resultado
