import os
import logging

# ==========================================
# CONFIGURAÇÃO DE LOGS
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger('AgenteSondagem')

# ==========================================
# CREDENCIAIS E VARIÁVEIS DE AMBIENTE
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CIDADES_ALVO = [c.strip() for c in os.getenv("CIDADES_ALVO", "Muriaé, MG;Juiz de Fora, MG;Rio de Janeiro, RJ").split(";") if c.strip()]
INTERVALO_HORAS = int(os.getenv("INTERVALO_HORAS", 24))
MAX_RESULTADOS_POR_CIDADE = int(os.getenv("MAX_RESULTADOS_POR_CIDADE", 30))

# ==========================================
# ASSINATURAS DE CHATBOT/IA PARA DETECÇÃO
# ==========================================
# Provedores de IA AVANÇADA (o lead JÁ possui tecnologia - menor oportunidade)
IA_AVANCADA_SIGNATURES = {
    'intercom': ['intercomcdn.com', 'api-iam.intercom.io', 'intercom-container', 'window.Intercom'],
    'drift': ['js.driftt.com', 'drift-widget', 'window.drift'],
    'tidio': ['code.tidio.co', 'tidio-chat', 'window.tidioChatApi'],
    'crisp': ['client.crisp.chat', 'crisp-chatbox', 'window.$crisp'],
    'botpress': ['botpress.com', 'botpress-widget'],
    'chatgpt_widget': ['chatgpt', 'openai-widget', 'chat.openai'],
    'manychat': ['manychat.com', 'mcwidget'],
    'hubspot_chat': ['js.usemessages.com', 'HubSpotConversations'],
    'zenvia': ['zenvia.com', 'zenvia-chat'],
    'blip': ['blip.ai', 'take.chat'],
}

# Provedores de CHAT HUMANO/SIMPLES (lead tem chat, mas sem IA)
CHAT_HUMANO_SIGNATURES = {
    'livechat': ['cdn.livechatinc.com', 'LiveChatWidget'],
    'zendesk': ['static.zdassets.com', 'v2.zopim.com', 'window.zE'],
    'tawk': ['embed.tawk.to', 'tawk-chat'],
    'jivochat': ['code.jivosite.com', 'jivo-chat'],
    'freshdesk': ['freshdesk.com', 'freshchat'],
}

# Indicadores de WhatsApp BÁSICO
WHATSAPP_SIGNATURES = ['wa.me', 'api.whatsapp.com', 'whatsapp', 'whatschat']

# CNAE de clínicas médicas
CNAE_CLINICAS = ['8630501', '8630502', '8630503', '8630504', '8630599']

# User Agent padrão
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
