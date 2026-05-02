# Stage 1: builder — installa le dipendenze
FROM python:3.11-slim AS builder

WORKDIR /app

# Copia solo requirements prima del codice per sfruttare la cache Docker
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: runtime — immagine finale leggera
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copia le dipendenze installate dallo stage builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copia il codice dell'applicazione
COPY . .

# Porta esposta
EXPOSE 8000

# Comando di avvio
# --host 0.0.0.0: ascolta su tutte le interfacce (necessario in container)
# --workers 2: 2 worker per gestire più richieste in parallelo
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
