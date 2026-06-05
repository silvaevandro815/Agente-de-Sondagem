import logging
import unicodedata
import urllib.parse
from config import MAX_RESULTADOS_POR_CIDADE

logger = logging.getLogger('AgenteSondagem.Maps')

def sanitizar_telefone(telefone: str) -> str:
    """Sanitiza o telefone para o formato 55+DDD+Numero."""
    if not telefone:
        return ""
    numeros = ''.join(filter(str.isdigit, telefone))
    if not numeros:
        return ""
    if numeros.startswith('0800') or numeros.startswith('4004'):
        logger.warning(f"Número especial detectado (0800/4004): {telefone}")
    if numeros.startswith('0'):
        numeros = numeros[1:]
    if not numeros.startswith('55'):
        numeros = '55' + numeros
    # Adiciona o 9 para celulares se necessário
    if len(numeros) == 12 and numeros.startswith('55'):
        ddd = numeros[2:4]
        prefixo = numeros[4]
        if prefixo in ['6', '7', '8', '9']:
            numeros = '55' + ddd + '9' + numeros[4:]
    return numeros

def sanitizar_cidade(cidade: str) -> str:
    """Remove acentos e formata a cidade para a URL."""
    return ''.join(
        c.lower() for c in unicodedata.normalize('NFD', cidade)
        if unicodedata.category(c) != 'Mn'
    )

def buscar_clinicas(page, cidade: str) -> list:
    """Busca clínicas médicas no Google Maps e extrai informações."""
    logger.info(f"🔍 Buscando clínicas médicas em: {cidade}")
    cidade_sanitizada = sanitizar_cidade(cidade)
    busca = f"clinicas medicas em {cidade_sanitizada}"
    busca_encoded = urllib.parse.quote(busca)
    url = f"https://www.google.com/maps/search/{busca_encoded}/"

    try:
        page.goto(url, timeout=60000)
        page.wait_for_timeout(5000)
    except Exception as e:
        logger.error(f"Erro ao carregar Google Maps: {e}")
        return []

    clinicas = []
    nomes_vistos = set()  # Anti-duplicatas

    try:
        # Scroll na lista de resultados para carregar mais clínicas
        feed_selector = 'div[role="feed"]'
        for scroll_round in range(5):  # 5 rounds de scroll
            try:
                page.evaluate(f'''
                    const feed = document.querySelector('{feed_selector}');
                    if (feed) feed.scrollTop = feed.scrollHeight;
                ''')
                page.wait_for_timeout(2000)
            except Exception:
                break

        links = page.locator("a[href*='/maps/place/']").all()
        logger.info(f"Encontrados {len(links)} resultados. Processando até {MAX_RESULTADOS_POR_CIDADE}.")

        for link in links[:MAX_RESULTADOS_POR_CIDADE]:
            try:
                link.click()
                page.wait_for_timeout(3000)

                # Nome do Local
                nome = "Nome Indisponível"
                nome_locators = page.locator("h1.fontHeadlineLarge, div.fontHeadlineLarge, h1").all()
                for loc in nome_locators:
                    texto = loc.inner_text().strip()
                    texto_lower = texto.lower()
                    if texto and texto_lower not in ["resultados", "results"] and \
                       not any(p in texto_lower for p in ["patrocinado", "anúncio", "anuncio", "sponsored"]):
                        nome = texto
                        break

                # Anti-duplicatas
                if nome == "Nome Indisponível" or nome in nomes_vistos:
                    continue
                nomes_vistos.add(nome)

                # Telefone e Site
                telefone = ""
                site = ""
                endereco = ""

                botoes = page.locator("button[data-item-id]").all()
                for el in botoes:
                    item_id = el.get_attribute("data-item-id") or ""
                    if item_id.startswith("phone:"):
                        telefone = item_id.replace("phone:tel:", "")
                    if item_id.startswith("authority:"):
                        site = el.inner_text()
                        if site and not site.startswith("http"):
                            site = "https://" + site
                    if item_id.startswith("address"):
                        try:
                            endereco = el.inner_text().strip()
                        except Exception:
                            pass

                # Site — extração robusta via links
                links_oficiais = page.locator('a[data-value="Website"], a.lcr4fd, a[data-item-id="authority"]').all()
                for link_el in links_oficiais:
                    href = link_el.get_attribute("href")
                    if href and not href.startswith("/") and "/maps/" not in href and "/aclk" not in href:
                        site = href
                        break

                if not site or "google.com" in site or "/aclk" in site:
                    links_gerais = page.locator("a[href]").all()
                    for link_el in links_gerais:
                        href = link_el.get_attribute("href") or ""
                        href_lower = href.lower()
                        if href_lower and not href_lower.startswith("/") and \
                           "/maps/" not in href_lower and "/search/" not in href_lower and \
                           "google.com" not in href_lower and "/aclk" not in href_lower:
                            if any(ext in href_lower for ext in [".com", ".med.br", ".net", ".org", ".br"]):
                                site = href
                                break

                if site and ("/aclk" in site or not (site.startswith("http://") or site.startswith("https://"))):
                    site = None

                # Rating e avaliações do Google
                avaliacao_google = None
                total_avaliacoes = None
                try:
                    rating_el = page.locator('div.fontDisplayLarge, span.fontDisplayLarge').first
                    if rating_el.count() > 0:
                        rating_text = rating_el.inner_text().strip().replace(',', '.')
                        avaliacao_google = float(rating_text)
                except Exception:
                    pass

                try:
                    reviews_el = page.locator('span[aria-label*="avaliações"], span[aria-label*="reviews"]').first
                    if reviews_el.count() > 0:
                        reviews_text = reviews_el.get_attribute("aria-label") or ""
                        total_avaliacoes = int(''.join(filter(str.isdigit, reviews_text)))
                except Exception:
                    pass

                clinicas.append({
                    "nome": nome,
                    "telefone": telefone,
                    "site": site,
                    "endereco": endereco,
                    "avaliacao_google": avaliacao_google,
                    "total_avaliacoes": total_avaliacoes,
                })
                logger.info(f"  📋 {nome} | Tel: {telefone} | Rating: {avaliacao_google}")

            except Exception as e:
                logger.error(f"Erro ao processar item do mapa: {e}")

    except Exception as e:
        logger.error(f"Erro durante extração do Maps: {e}")

    logger.info(f"Total de clínicas capturadas em {cidade}: {len(clinicas)}")
    return clinicas
