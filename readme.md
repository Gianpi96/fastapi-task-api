# FastAPI Task Manager

API REST per la gestione di task personali con autenticazione JWT.
Progetto portfolio che dimostra architettura professionale, sicurezza, testing e CI/CD.

![Tests](https://github.com/Gianpi96/fastapi-task-api/actions/workflows/test.yml/badge.svg)

---

## Funzionalità

- Registrazione e login utenti con JWT
- CRUD completo dei task (crea, leggi, aggiorna, elimina)
- Isolamento dei dati per utente — nessun utente vede i task altrui
- Notifica email asincrona alla creazione di un task (BackgroundTask)
- Filtri per stato e ricerca per titolo
- Paginazione con `skip` e `limit`

## Stack tecnico

| Layer | Tecnologia |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Migration | Alembic |
| Auth | JWT (PyJWT) + bcrypt |
| Validazione | Pydantic v2 |
| DB sviluppo | SQLite |
| DB produzione | PostgreSQL 16 |
| Rate limiting | slowapi |
| Test | pytest + httpx + anyio |
| CI/CD | GitHub Actions |
| Infrastruttura | Docker Compose |

---

## Avvio rapido (sviluppo locale con SQLite)

### Prerequisiti
- Python 3.11+
- Git

### Setup

```bash
# Clona il repository
git clone https://github.com/Gianpi96/fastapi-task-api.git
cd fastapi-task-api

# Crea e attiva il virtualenv
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac/Linux

# Installa le dipendenze
pip install -r requirements.txt

# Crea il file .env
cp .env.development .env
# Modifica SECRET_KEY con una chiave sicura:
# python -c "import secrets; print(secrets.token_hex(32))"

# Avvia il server
uvicorn main:app --reload
```

Apri **http://localhost:8000/docs** per la documentazione interattiva.

---

## Avvio con PostgreSQL (Docker)

### Prerequisiti
- Docker Desktop

```bash
# Avvia PostgreSQL
docker compose up -d

# Attiva la configurazione PostgreSQL
cp .env.production .env
# Modifica SECRET_KEY nel .env

# Applica le migration
alembic upgrade head

# Avvia il server
uvicorn main:app --reload
```

Verifica le tabelle:
```bash
docker exec -it taskdb_postgres psql -U taskuser -d taskdb -c "\dt"
```

Ferma PostgreSQL:
```bash
docker compose stop
```

---

## Esegui i test

```bash
# Assicurati di usare SQLite per i test
cp .env.development .env

# Tutti i test con coverage
pytest -v --cov=. --cov-report=term-missing

# Solo i test di autenticazione
pytest tests/test_auth.py -v

# Solo i test dei task
pytest tests/test_tasks.py -v
```

Coverage attuale: **93%**

---

## Struttura del progetto

```
fastapi-task-api/
├── api/                    # Router FastAPI
│   ├── deps.py             # Dependency get_current_user
│   ├── exception_handlers.py
│   └── tasks.py            # Endpoints /tasks
├── auth/
│   └── security.py         # JWT, bcrypt, token
├── config/
│   └── settings.py         # Configurazione via .env
├── models/                 # Modelli SQLAlchemy
│   ├── tasks.py
│   └── user.py
├── schemas/                # Schemi Pydantic
│   ├── task.py
│   ├── token.py
│   └── user.py
├── services/               # Business logic
│   ├── notification_service.py
│   └── task_service.py
├── tests/                  # Test asincroni con httpx
│   ├── conftest.py
│   ├── test_auth.py
│   └── test_tasks.py
├── alembic/                # Migration DB
│   └── versions/
├── test_main.py            # Test sincroni
├── main.py                 # Entry point
├── database.py             # Configurazione DB
├── docker-compose.yml      # PostgreSQL locale
└── .github/workflows/      # CI/CD GitHub Actions
```

---

## Sicurezza implementata

- **JWT**: algoritmo HS256 hardcoded (no algorithm confusion attack)
- **Password**: bcrypt con salt automatico
- **Rate limiting**: 5 tentativi/min su login, 3 registrazioni/min
- **Timing attack**: `verify_password` sempre eseguito anche per utenti inesistenti
- **Campi sensibili**: `hashed_password` mai esposta nelle risposte
- **CORS**: origini esplicite, no wildcard con credentials
- **Errori**: traceback mai esposti al client in produzione

---

## Endpoints principali

| Metodo | Endpoint | Descrizione | Auth |
|---|---|---|---|
| POST | `/auth/register` | Registra un nuovo utente | No |
| POST | `/auth/token` | Login, ottieni JWT | No |
| GET | `/tasks` | Lista task con filtri e paginazione | Sì |
| POST | `/tasks` | Crea un task | Sì |
| GET | `/tasks/{id}` | Dettaglio task | Sì |
| PUT | `/tasks/{id}` | Aggiorna task | Sì |
| DELETE | `/tasks/{id}` | Elimina task | Sì |
| GET | `/health` | Health check | No |

### Filtri e paginazione su GET /tasks

```
GET /tasks?skip=0&limit=10&completed=false&search=latte
```

| Parametro | Tipo | Default | Descrizione |
|---|---|---|---|
| `skip` | int | 0 | Offset per la paginazione |
| `limit` | int | 10 | Numero massimo di risultati (max 100) |
| `completed` | bool | null | Filtra per stato completamento |
| `search` | string | null | Ricerca nel titolo (case insensitive) |

---

## Variabili d'ambiente

| Variabile | Descrizione | Esempio |
|---|---|---|
| `SECRET_KEY` | Chiave JWT (min 32 caratteri) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | URL del database | `sqlite:///./tasks.db` o `postgresql://user:pwd@host/db` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Scadenza JWT in minuti | `30` |
| `ENV` | Ambiente (`development`/`production`) | `development` |
