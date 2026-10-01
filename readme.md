# Painel de Cotações (Café & Dólar) em Tempo Real

Painel web com cotações de café (Nova York, BM&F, Londres) e dólar comercial
atualizadas em tempo real via WebSocket, com login por usuário e limite de
telas (sessões) simultâneas.

## Arquitetura

- **Backend**: Python (FastAPI) + PostgreSQL (SQLAlchemy async + Alembic).
- **Frontend**: HTML/CSS/JS puro (`src/`), sem framework — o próprio backend
  serve esses arquivos estáticos.
- **Tempo real**: WebSocket (`/ws/quotes`) com broadcast a cada atualização.
- **Autenticação**: login por e-mail/senha, JWT por sessão, com controle de
  quantas "telas" (sessões) cada usuário pode ter abertas ao mesmo tempo.

```
backend/
  app/
    core/       # config, segurança (hash de senha, JWT)
    db/         # engine e sessão do SQLAlchemy
    models/     # User, UserSession, Praça, Ativo, Instrumento, Cotações
    schemas/    # schemas Pydantic (request/response)
    api/        # rotas REST + endpoint WebSocket
    services/   # limite de sessões, providers de cotação, WS manager
  alembic/      # migrations do banco
src/            # frontend estático (login.html, index.html, styles.css, js/)
docker-compose.yml
```

## Como rodar localmente (Docker Compose — recomendado)

```bash
docker compose up --build
```

Isso sobe o PostgreSQL e o backend (que já serve o frontend). Acesse
`http://localhost:8000`.

Crie o primeiro usuário:

```bash
docker compose exec backend python -m app.seed \
  --email voce@empresa.com --password "senha-forte" --nome "Seu Nome" --max-sessions 1
```

## Como rodar sem Docker

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajuste DATABASE_URL para seu Postgres local

alembic upgrade head
python -m app.seed --email voce@empresa.com --password "senha-forte" --nome "Seu Nome"

uvicorn app.main:app --reload
```

Acesse `http://localhost:8000`.

## Limite de telas simultâneas

Cada usuário tem um campo `max_sessions` (padrão: 1). Ao logar, se o limite
já foi atingido:

- **`SESSION_LIMIT_POLICY=reject`** (padrão): o novo login é recusado com
  HTTP 409, pedindo para encerrar uma sessão existente primeiro.
- **`SESSION_LIMIT_POLICY=kick_oldest`**: a sessão mais antiga é encerrada
  automaticamente (e a tela correspondente é desconectada do WebSocket em
  tempo real) para abrir espaço para o novo login.

A validação não é só no login: cada requisição e cada mensagem no WebSocket
reconfirma que a sessão continua ativa, então um logout ou revogação em uma
tela derruba a conexão em tempo real das outras.

Ajuste o limite por usuário via `--max-sessions` no `app.seed`.

## Fontes de cotação

Configuradas para usar **APIs públicas gratuitas**, sem necessidade de chave:

- **Dólar comercial**: [AwesomeAPI](https://docs.awesomeapi.com.br/api-de-moedas).
- **Café**: Yahoo Finance (símbolo `KC=F`, contrato futuro corrente de Nova
  York/ICE). Os preços de **BM&F e Londres são estimados** a partir do preço
  de Nova York (spread fixo, ver `app/services/providers/cafe_yahoo.py`) até
  que uma fonte gratuita dedicada a essas praças seja integrada — é a
  limitação conhecida deste MVP.

Para plugar uma fonte paga/oficial (ex: CEPEA, B3, ICE Futures Europe),
implemente um novo `QuoteProvider` em `app/services/providers/` seguindo a
interface em `base.py` e registre-o em `PROVIDERS`
(`app/services/quote_updater.py`).

## Próximos passos sugeridos

- Hospedagem definitiva: como o backend precisa de processo persistente,
  WebSocket e Postgres, ele **não roda no modelo puramente estático do Azure
  Static Web Apps** (usado hoje só para o front). Avalie Azure Container
  Apps/App Service, Railway, Render ou VPS quando for para produção.
- Tela de administração de usuários (hoje via `app.seed` por linha de
  comando).
- Fonte de dados dedicada para BM&F e Londres.
