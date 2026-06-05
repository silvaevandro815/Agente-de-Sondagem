import logging
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger('AgenteSondagem.Supabase')

def init_supabase() -> Client | None:
    """Inicializa e retorna o cliente Supabase."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Conexão com Supabase estabelecida com sucesso.")
            return client
        except Exception as e:
            logger.error(f"Erro ao conectar com Supabase: {e}")
    else:
        logger.warning("Credenciais do Supabase não encontradas. Modo de teste ativado.")
    return None

def salvar_lead(supabase: Client, dados: dict):
    """Salva ou atualiza um lead na tabela prospeccao_agencia via upsert."""
    if not supabase:
        logger.info(f"[TESTE] Dados capturados: {dados.get('nome', 'N/A')} | Score: {dados.get('lead_score', 0)}")
        return
    try:
        # Remove campos com valor None para não sobrescrever dados existentes
        dados_limpos = {k: v for k, v in dados.items() if v is not None}
        data, count = supabase.table("prospeccao_agencia").upsert(
            dados_limpos, on_conflict='telefone'
        ).execute()
        logger.info(f"✅ Salvo: {dados.get('nome')} | Score: {dados.get('lead_score', 0)} | Cidade: {dados.get('cidade')}")
    except Exception as e:
        logger.error(f"Erro ao salvar lead '{dados.get('nome')}': {e}")

def verificar_lead_existente(supabase: Client, telefone: str) -> bool:
    """Verifica se um lead com esse telefone já existe no banco."""
    if not supabase or not telefone:
        return False
    try:
        result = supabase.table("prospeccao_agencia").select("id").eq("telefone", telefone).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Erro ao verificar lead existente: {e}")
        return False
