# InForge Leads — Backend

API multi-tenant da Plataforma de Inteligência de Base. FastAPI + PostgreSQL.

## O que está pronto

- **Multi-tenant** — `tenant_id` em todas as tabelas, isolamento total
- **Auth dupla** — JWT para o painel (`/auth/login`), API key (`X-API-Key`) para BI e integrações
- **Leads** — CRUD com deduplicação automática (email/telefone), score preditivo, paginação e filtros
- **Rastreamento** — recebe eventos do `track.js` (pageview, click, scroll, form), sessões com dispositivo/OS/browser, **identity stitching** (anônimo → lead com histórico retroativo)
- **Conector Meta Lead Ads** — webhook com verificação de assinatura, busca campos na Graph API
- **Qualificação** — débito de créditos, provedores plugáveis (mock / Speedio / Econodata)
- **BI** — `/bi/leads` (paginado, carga incremental), `/bi/leads.csv`, `/bi/metrics` — Power BI/Tableau consomem direto

## Rodar local

```bash
cd backend
pip install -r requirements.txt
python seed.py                      # cria tenant demo + admin (demo123)
uvicorn app.main:app --reload
```

Docs interativas: http://localhost:8000/docs

## Testes (rodar antes de todo deploy)

```bash
pip install pytest
python -m pytest          # 24 testes, ~12s
```

O que a suíte garante:

- **Isolamento multi-tenant** — tenant B nunca lê, edita ou qualifica leads do tenant A (o teste mais importante: vazamento aqui acaba com o negócio)
- **Deduplicação** — mesmo email não gera lead duplicado; merge preenche campos faltantes
- **Identity stitching** — sessões anônimas são vinculadas retroativamente no identify
- **Créditos** — débito correto, extrato registrado e HTTP 402 quando o saldo acaba
- **Segurança do webhook Meta** — assinatura HMAC inválida é rejeitada (403)
- **API keys** — chave inválida e chave revogada retornam 401; cada chave só acessa o próprio tenant

## Validação no cliente (track.js)

Após instalar o script no site do cliente, abra `tracker/validar-instalacao.html`,
informe o tracking token e a URL da API. A página confirma em tempo real:
script carregado, API alcançável, pageview aceito, dispositivo detectado e identify funcionando.

## Deploy no Railway

1. Suba este repositório no GitHub
2. Railway → New Project → Deploy from GitHub → selecione o repo, root = `backend/`
3. Add PostgreSQL (Railway injeta `DATABASE_URL` sozinho)
4. Variáveis: `ENV=prod`, `SECRET_KEY` (gere com `openssl rand -hex 32`), `META_*` quando conectar o Meta
5. Rode `python seed.py` uma vez no 