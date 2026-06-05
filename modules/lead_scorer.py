import logging

logger = logging.getLogger('AgenteSondagem.Scorer')


def calcular_score(dados: dict) -> int:
    """
    Calcula o lead score (0-100) baseado nos dados coletados.
    Quanto MAIOR o score, melhor o lead para oferecer serviços de IA.
    """
    score = 50  # Base

    # ===== CRITÉRIOS POSITIVOS (lead é uma boa oportunidade) =====

    # Sem IA avançada = lead ideal
    if not dados.get('tem_ia_avancada', False):
        score += 25
    else:
        score -= 30  # Já possui IA, menor oportunidade

    # Apenas WhatsApp básico = precisa de upgrade
    if dados.get('tem_whatsapp', False) and not dados.get('tem_ia_avancada', False):
        score += 10

    # Sem nenhum chatbot = lead perfeito
    if not dados.get('status_chatbot', False) and not dados.get('tem_ia_avancada', False):
        score += 10

    # Tem site próprio = investe em presença digital
    if dados.get('link_site'):
        score += 5

    # Tem Instagram = presença nas redes
    if dados.get('link_instagram'):
        score += 5

    # Tem Facebook = presença nas redes
    if dados.get('link_facebook'):
        score += 3

    # Boa avaliação no Google (>= 4.0)
    avaliacao = dados.get('avaliacao_google')
    if avaliacao and avaliacao >= 4.0:
        score += 5
    elif avaliacao and avaliacao >= 3.0:
        score += 2

    # Volume de avaliações (clínica estabelecida)
    total = dados.get('total_avaliacoes')
    if total and total >= 100:
        score += 5
    elif total and total >= 30:
        score += 3

    # Dono identificado via CNPJ
    if dados.get('socios'):
        score += 10

    # ===== CRITÉRIOS NEGATIVOS =====

    # Sem telefone = difícil contatar
    if not dados.get('telefone'):
        score -= 15

    # Avaliação muito baixa = clínica problemática
    if avaliacao and avaliacao < 2.5:
        score -= 10

    # Limita entre 0 e 100
    score = max(0, min(100, score))

    logger.info(f"  📊 Lead Score: {score}/100 para {dados.get('nome', 'N/A')}")
    return score
