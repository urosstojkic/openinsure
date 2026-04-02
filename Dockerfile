FROM python:3.12-slim

WORKDIR /app

# System deps + ODBC driver (cached layer — rarely changes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg2 unixodbc-dev gcc g++ \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y gcc g++ \
    && apt-get autoremove -y \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer — only rebuilds when pyproject.toml changes)
COPY pyproject.toml .
RUN mkdir -p src/openinsure && touch src/openinsure/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf src/openinsure

# Copy application source (changes frequently, but deps are already cached)
COPY src/ src/
COPY knowledge/ knowledge/
RUN pip install --no-cache-dir --no-deps .

RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "openinsure.main:app", "--host", "0.0.0.0", "--port", "8000"]
