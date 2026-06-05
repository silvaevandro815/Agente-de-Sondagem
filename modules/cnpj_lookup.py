import logging
import time
import re
import requests
from config import DEFAULT_USER_AGENT, CNAE_CLINICAS

logger = logging.getLogger('AgenteSondagem.CNPJ')

# Rate limiter simples
_last_request_time = 0
_MIN_INTERVAL = 1.5  # 1.5 segundos entre requisições


def _rate_limit():
    """Garante intervalo mínimo entre requisições à API pública."""
    global _last_request_time
    agora = time.time()
    diff = agora - _last_request_time
    if diff < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - diff)
    _last_request_time = time.time()


def buscar_cnpj_por_nome(nome_empresa: str) -> dict | None:
    """
    Busca dados do CNPJ usando a API pública cnpj.ws.
    Retorna dict com razao_social, cnpj, socios, ou None se não encontrar.
    """
    if not nome_empresa:
        return None

    # Limpa o nome para busca
    nome_limpo = re.sub(r'[^\w\s]', '', nome_empresa).strip()
    if len(nome_limpo) < 3:
        return None

    logger.info(f"🔎 Buscando CNPJ para: {nome_limpo}")

    try:
        _rate_limit()
        
        # Tenta buscar via API pública do CNPJ.ws
        url = f"https://publica.cnpj.ws/cnpj?nome={requests.utils.quote(nome_limpo)}"
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            dados = response.json()
            if isinstance(dados, list) and len(dados) > 0:
                primeiro = dados[0]
                return _processar_resultado_cnpj(primeiro)
            elif isinstance(dados, dict) and dados.get('cnpj'):
                return _processar_resultado_cnpj(dados)

        elif response.status_code == 429:
            logger.warning("Rate limit atingido na API CNPJ.ws. Aguardando 60s...")
            time.sleep(60)
            return None

    except requests.exceptions.RequestException as e:
        logger.warning(f"Erro na busca CNPJ para '{nome_limpo}': {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar CNPJ: {e}")

    return None


def consultar_cnpj_direto(cnpj: str) -> dict | None:
    """Consulta dados de um CNPJ específico via API pública."""
    if not cnpj:
        return None

    cnpj_limpo = re.sub(r'\D', '', cnpj)
    if len(cnpj_limpo) != 14:
        return None

    logger.info(f"🔎 Consultando CNPJ: {cnpj_limpo}")

    try:
        _rate_limit()
        url = f"https://publica.cnpj.ws/cnpj/{cnpj_limpo}"
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            dados = response.json()
            return _processar_resultado_cnpj(dados)
        elif response.status_code == 429:
            logger.warning("Rate limit na API CNPJ.ws.")
            time.sleep(60)

    except Exception as e:
        logger.warning(f"Erro ao consultar CNPJ {cnpj_limpo}: {e}")

    return None


def _processar_resultado_cnpj(dados: dict) -> dict:
    """Processa o resultado da API e extrai informações relevantes."""
    # Extrai sócios
    socios_lista = []
    socios_raw = dados.get('socios', dados.get('qsa', []))
    if isinstance(socios_raw, list):
        for socio in socios_raw:
            nome_socio = socio.get('nome_socio', socio.get('nome', ''))
            qualificacao = socio.get('qualificacao_socio', socio.get('qualificacao', {}))
            if isinstance(qualificacao, dict):
                qualificacao = qualificacao.get('descricao', '')
            if nome_socio:
                socios_lista.append(f"{nome_socio} ({qualificacao})" if qualificacao else nome_socio)

    # Extrai CNAE
    cnae_principal = dados.get('estabelecimento', {}).get('atividade_principal', {})
    if isinstance(cnae_principal, dict):
        cnae_codigo = cnae_principal.get('id', cnae_principal.get('subclasse', ''))
    else:
        cnae_codigo = dados.get('cnae_fiscal', '')

    cnae_str = str(cnae_codigo).replace('.', '').replace('-', '').replace('/', '')
    eh_clinica = any(cnae_str.startswith(c) for c in CNAE_CLINICAS)

    resultado = {
        'cnpj': dados.get('cnpj', dados.get('estabelecimento', {}).get('cnpj', '')),
        'razao_social': dados.get('razao_social', ''),
        'socios': ' | '.join(socios_lista) if socios_lista else None,
        'eh_clinica_cnae': eh_clinica,
        'cnae': cnae_str,
    }

    if socios_lista:
        logger.info(f"  👤 Sócios encontrados: {', '.join(socios_lista)}")
    else:
        logger.info(f"  ⚠️ Nenhum sócio encontrado para: {dados.get('razao_social', 'N/A')}")

    return resultado
