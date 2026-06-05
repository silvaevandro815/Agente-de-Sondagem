-- ==========================================
-- MIGRAÇÃO: Agente de Sondagem v2.0
-- Cole este SQL no Editor SQL do Supabase
-- ==========================================

-- 1. NOVAS COLUNAS para detecção de IA/Chatbot
ALTER TABLE prospeccao_agencia 
  ADD COLUMN IF NOT EXISTS tem_ia_avancada BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS tecnologias_detectadas TEXT;

COMMENT ON COLUMN prospeccao_agencia.tem_ia_avancada IS 'TRUE se a clínica possui IA avançada (Intercom, Drift, etc). FALSE = oportunidade de venda.';
COMMENT ON COLUMN prospeccao_agencia.tecnologias_detectadas IS 'Lista das tecnologias encontradas no site (ex: IA:intercom, Chat:livechat, WhatsApp)';

-- 2. NOVAS COLUNAS para redes sociais
ALTER TABLE prospeccao_agencia 
  ADD COLUMN IF NOT EXISTS link_facebook TEXT,
  ADD COLUMN IF NOT EXISTS link_linkedin TEXT,
  ADD COLUMN IF NOT EXISTS link_youtube TEXT,
  ADD COLUMN IF NOT EXISTS link_tiktok TEXT;

COMMENT ON COLUMN prospeccao_agencia.link_facebook IS 'URL do perfil do Facebook da clínica';
COMMENT ON COLUMN prospeccao_agencia.link_linkedin IS 'URL do perfil do LinkedIn da clínica ou do dono';
COMMENT ON COLUMN prospeccao_agencia.link_youtube IS 'URL do canal do YouTube da clínica';
COMMENT ON COLUMN prospeccao_agencia.link_tiktok IS 'URL do perfil do TikTok da clínica';

-- 3. NOVAS COLUNAS para dados do CNPJ (identificar DONOS)
ALTER TABLE prospeccao_agencia 
  ADD COLUMN IF NOT EXISTS cnpj TEXT,
  ADD COLUMN IF NOT EXISTS razao_social TEXT,
  ADD COLUMN IF NOT EXISTS socios TEXT;

COMMENT ON COLUMN prospeccao_agencia.cnpj IS 'CNPJ da clínica encontrado via API pública';
COMMENT ON COLUMN prospeccao_agencia.razao_social IS 'Razão social da empresa';
COMMENT ON COLUMN prospeccao_agencia.socios IS 'Nomes dos sócios/proprietários separados por | (pipe)';

-- 4. NOVAS COLUNAS para Lead Scoring e Google
ALTER TABLE prospeccao_agencia 
  ADD COLUMN IF NOT EXISTS lead_score INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS avaliacao_google NUMERIC(3,1),
  ADD COLUMN IF NOT EXISTS total_avaliacoes INTEGER,
  ADD COLUMN IF NOT EXISTS endereco TEXT;

COMMENT ON COLUMN prospeccao_agencia.lead_score IS 'Pontuação automática do lead (0-100). Maior = melhor oportunidade.';
COMMENT ON COLUMN prospeccao_agencia.avaliacao_google IS 'Nota de avaliação no Google Maps (ex: 4.5)';
COMMENT ON COLUMN prospeccao_agencia.total_avaliacoes IS 'Quantidade total de avaliações no Google Maps';
COMMENT ON COLUMN prospeccao_agencia.endereco IS 'Endereço completo extraído do Google Maps';

-- 5. ÍNDICES para performance das queries do N8N
CREATE INDEX IF NOT EXISTS idx_prospeccao_status ON prospeccao_agencia(status_prospeccao);
CREATE INDEX IF NOT EXISTS idx_prospeccao_score ON prospeccao_agencia(lead_score DESC);
CREATE INDEX IF NOT EXISTS idx_prospeccao_cidade ON prospeccao_agencia(cidade);
CREATE INDEX IF NOT EXISTS idx_prospeccao_ia ON prospeccao_agencia(tem_ia_avancada);

-- 6. VIEW útil para o N8N buscar os melhores leads
CREATE OR REPLACE VIEW leads_quentes AS
SELECT 
  id,
  nome,
  telefone,
  cidade,
  link_site,
  link_instagram,
  link_facebook,
  link_linkedin,
  socios,
  razao_social,
  lead_score,
  avaliacao_google,
  total_avaliacoes,
  tecnologias_detectadas,
  tem_ia_avancada,
  status_chatbot,
  status_prospeccao,
  data_captura
FROM prospeccao_agencia
WHERE tem_ia_avancada = FALSE
  AND telefone IS NOT NULL
  AND telefone != ''
  AND status_prospeccao = 'pendente'
ORDER BY lead_score DESC;

COMMENT ON VIEW leads_quentes IS 'View pré-filtrada dos leads mais promissores (sem IA avançada, com telefone, ordenados por score)';
