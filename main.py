import os
import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import logger, CIDADES_ALVO, INTERVALO_HORAS
from modules.supabase_client import init_supabase, salvar_lead, verificar_lead_existente
from modules.maps_scraper import buscar_clinicas, sanitizar_telefone
from modules.site_analyzer import analisar_site
from modules.cnpj_lookup import buscar_cnpj_por_nome
from modules.lead_scorer import calcular_score

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    logger.error("Playwright não instalado. Execute: pip install playwright && playwright install chromium")
    sys.exit(1)

# ==========================================
# GRACEFUL SHUTDOWN
# ==========================================
_shutdown = False

def signal_handler(sig, frame):
    global _shutdown
    logger.info("🛑 Sinal de encerramento recebido. Finalizando após o ciclo atual...")
    _shutdown = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ==========================================
# HEALTH CHECK
# ==========================================
HEALTH_FILE = "/tmp/healthcheck"

def atualizar_healthcheck():
    """Atualiza o arquivo de healthcheck para o Docker."""
    try:
        Path(HEALTH_FILE).write_text(datetime.now().isoformat())
    except Exception:
        pass

# ==========================================
# PIPELINE PRINCIPAL
# ==========================================
def processar_clinica(page, clinica: dict, cidade: str, supabase) -> dict:
    """Pipeline completo de processamento de uma clínica."""
    nome = clinica.get('nome', 'N/A')
    logger.info(f"\n{'='*50}")
    logger.info(f"Processando: {nome}")
    logger.info(f"{'='*50}")

    # 1. Sanitizar telefone
    telefone = sanitizar_telefone(clinica.get('telefone', ''))
    if not telefone:
        logger.warning(f"  ⚠️ Sem telefone válido para: {nome}")

    # 2. Verificar se lead já existe (evita reprocessamento)
    if telefone and verificar_lead_existente(supabase, telefone):
        logger.info(f"  ⏭️ Lead já existe no banco: {nome}")
        return None

    # 3. Analisar site (chatbot, IA, redes sociais)
    site_data = analisar_site(clinica.get('site'))

    # 4. Buscar dados do CNPJ (donos/sócios)
    cnpj_data = buscar_cnpj_por_nome(nome)

    # 5. Montar dados completos
    dados = {
        "nome": nome,
        "telefone": telefone,
        "link_site": clinica.get('site'),
        "endereco": clinica.get('endereco'),
        "avaliacao_google": clinica.get('avaliacao_google'),
        "total_avaliacoes": clinica.get('total_avaliacoes'),
        "cidade": cidade,
        "data_captura": datetime.now().isoformat(),
        "status_prospeccao": "pendente",
        # Dados do site
        "status_chatbot": site_data.get('tem_chatbot', False),
        "tem_ia_avancada": site_data.get('tem_ia_avancada', False),
        "tecnologias_detectadas": site_data.get('tecnologias_detectadas'),
        "link_instagram": site_data.get('link_instagram'),
        "link_facebook": site_data.get('link_facebook'),
        "link_linkedin": site_data.get('link_linkedin'),
        "link_youtube": site_data.get('link_youtube'),
        "link_tiktok": site_data.get('link_tiktok'),
        # Dados do CNPJ
        "cnpj": cnpj_data.get('cnpj') if cnpj_data else None,
        "razao_social": cnpj_data.get('razao_social') if cnpj_data else None,
        "socios": cnpj_data.get('socios') if cnpj_data else None,
    }

    # Adicionar tem_whatsapp aos dados para scoring
    dados['tem_whatsapp'] = site_data.get('tem_whatsapp', False)

    # 6. Calcular Lead Score
    dados['lead_score'] = calcular_score(dados)

    # Remover campo auxiliar que não vai pro banco
    dados.pop('tem_whatsapp', None)

    return dados


def executar_varredura():
    """Função principal que orquestra todo o fluxo de varredura."""
    logger.info("\n" + "=" * 60)
    logger.info("🤖 INICIANDO NOVA VARREDURA DE PROSPECÇÃO")
    logger.info("=" * 60)

    supabase = init_supabase()
    stats = {"total": 0, "novos": 0, "existentes": 0, "erros": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        for cidade in CIDADES_ALVO:
            if _shutdown:
                logger.info("Encerramento solicitado. Parando varredura...")
                break

            logger.info(f"\n🏙️ Processando cidade: {cidade}")
            clinicas = buscar_clinicas(page, cidade)

            for clinica in clinicas:
                if _shutdown:
                    break

                stats['total'] += 1
                try:
                    dados = processar_clinica(page, clinica, cidade, supabase)
                    if dados:
                        salvar_lead(supabase, dados)
                        stats['novos'] += 1
                    else:
                        stats['existentes'] += 1
                except Exception as e:
                    stats['erros'] += 1
                    logger.error(f"Erro ao processar clínica: {e}")

        browser.close()

    # Resumo do ciclo
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 RESUMO DA VARREDURA")
    logger.info(f"  Total processados: {stats['total']}")
    logger.info(f"  Novos leads salvos: {stats['novos']}")
    logger.info(f"  Leads já existentes: {stats['existentes']}")
    logger.info(f"  Erros: {stats['erros']}")
    logger.info(f"{'='*60}")

    atualizar_healthcheck()


if __name__ == "__main__":
    logger.info("=========================================")
    logger.info("🤖 Agente de Sondagem v2.0 — Iniciado")
    logger.info(f"📍 Cidades Alvo: {', '.join(CIDADES_ALVO)}")
    logger.info(f"⏳ Intervalo: {INTERVALO_HORAS} hora(s)")
    logger.info("=========================================")

    # Primeiro ciclo imediato
    atualizar_healthcheck()

    while not _shutdown:
        try:
            executar_varredura()
        except Exception as e:
            logger.error(f"❌ Erro crítico no ciclo de varredura: {e}")

        if _shutdown:
            break

        logger.info(f"💤 Aguardando {INTERVALO_HORAS} hora(s) até a próxima varredura...")
        # Sleep interruptível
        for _ in range(INTERVALO_HORAS * 3600):
            if _shutdown:
                break
            time.sleep(1)

    logger.info("👋 Agente de Sondagem encerrado com sucesso.")
