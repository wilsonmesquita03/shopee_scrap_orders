FROM python:3.12-slim-bookworm

# Instalar dependências do sistema necessárias para o Playwright
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxtst6 \
    libasound2 \
    fonts-liberation \
    libx11-6 \
    libx11-xcb1 \
    libxext6 \
    libxfixes3 \
    libxcb1 \
    libgbm1 \
    libgtk-3-0 \
    && apt-get clean

# Instalar poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml poetry.lock* README.md /app/

# Instalar dependências via poetry
RUN poetry install --no-interaction --no-ansi --no-root

# Instalar browser Chromium do Playwright
RUN poetry run playwright install chromium

# Copiar o restante do código
COPY . /app

# Comando para rodar FastAPI com uvicorn
CMD ["poetry", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
