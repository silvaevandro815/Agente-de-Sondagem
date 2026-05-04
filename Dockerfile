FROM python:3.11-slim

WORKDIR /app

# Instalar dependências de sistema necessárias para o Playwright e atualizações
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Instala os navegadores e dependências de sistema do Playwright
RUN playwright install --with-deps chromium

COPY . .

CMD ["python", "-u", "main.py"]
