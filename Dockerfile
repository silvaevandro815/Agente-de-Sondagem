# ==========================================
# Agente de Sondagem v2.0 — Dockerfile
# Imagem base com Playwright + Chromium
# ==========================================
FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

# Metadata
LABEL maintainer="Evandro Silva" \
      description="Agente de Sondagem - Prospecção inteligente de clínicas médicas" \
      version="2.0"

# Criar usuário não-root para segurança
RUN useradd -m -s /bin/bash appuser

WORKDIR /app

# Instalar dependências (cache otimizado)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY . .

# Ajustar permissões
RUN chown -R appuser:appuser /app /tmp

# Trocar para usuário não-root
USER appuser

# Health check — verifica se o processo está rodando
HEALTHCHECK --interval=300s --timeout=10s --start-period=30s --retries=3 \
  CMD test -f /tmp/healthcheck && find /tmp/healthcheck -mmin -1500 | grep -q . || exit 1

# Executa o agente com output sem buffer
CMD ["python", "-u", "main.py"]
