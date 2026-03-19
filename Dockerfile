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

# Dependencies first (cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Application code (changes frequently — small layer)
COPY src/ src/
COPY knowledge/ knowledge/

# Reinstall to pick up the package source (fast — deps already cached)
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

CMD ["uvicorn", "openinsure.main:app", "--host", "0.0.0.0", "--port", "8000"]
