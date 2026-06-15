# ☀️ Status da madrugada — Relatório Mensal

**Build de 2026-06-15 (~02:22–02:40).** Resumo honesto do que ficou pronto e do que
depende de você. Não publiquei relatório com métricas vazias nem inventei dados —
a regra do projeto é usar só dados reais.

---

## ✅ Pronto e testado

| Item | Status |
|---|---|
| Template HTML animado (`template/relatorio.html`) | ✅ Estilo Spotify Wrapped, GSAP, teal-500. **Validado no navegador** (capa + animações + countup, console sem erros) |
| Gerador `gerar-relatorio.py` | ✅ Completo: coleta → Insights → cache de thumbs → análise via `claude -p` → render → publica. Sintaxe ok, guardas de erro testadas |
| Repositório GitHub | ✅ [oiforster/forster-relatorios](https://github.com/oiforster/forster-relatorios) criado e populado |
| GitHub Pages | ✅ Habilitado, CNAME = `relatorios.forsterfilmes.com` (aguardando DNS) |
| Inventário real de junho (API Postiz) | ✅ Puxado — mas só 1 post (a API pública só enxerga posts publicados PELO Postiz, não os orgânicos) |

---

## 🔑 2 coisas que só você pode destravar

### 1. Token do Instagram → destrava as MÉTRICAS (o coração do relatório)
As métricas (views, reach, likes, etc.) vêm da **Instagram Graph API**, que exige o
**token** e o **ig_user_id** da conta. Eles estão na tabela `Integration` do Postiz,
mas **o classificador de segurança bloqueou** eu ler a base de produção via SSH sem
sua autorização explícita (correto — é infra compartilhada). Eu **não** forcei.

**O que fazer (escolha um):**

**Opção A — ler do Postiz (você roda/autoriza):**
```bash
# no seu terminal, com acesso ao Lenovo:
ssh samuel@192.168.2.50 \
 'docker exec postiz-postgres psql "$(docker exec postiz printenv DATABASE_URL)" -At \
  -c "SELECT \"internalId\",token FROM \"Integration\" WHERE id='"'"'cmqdfi4c80001od75su2tkblj'"'"';"'
```
Cole os dois valores em `config.json` (campos `ig_user_id` e `token`).

**Opção B — manual:** pegue o token + IG user id pela sua conexão e cole no `config.json`.

`config.json` deve ficar assim (já tem o resto preenchido):
```json
{ "clientes": { "forsterfilmes": {
    "nome":"Forster","handle":"forsterfilmes","profile":"forsterfilmes",
    "canal_postiz":"cmqdfi4c80001od75su2tkblj",
    "ig_user_id":"<COLE_AQUI>", "token":"<COLE_AQUI>" } } }
```

> ⚠️ A integração é `instagram-standalone` → o script usa `graph.instagram.com` (já é o
> default). Se der erro de endpoint, troque para `graph.facebook.com/v21.0` no campo
> `graph_base` do config.

> 📌 Com o token, o script lista **todos** os posts do mês via Graph API (não fica
> limitado ao 1 post que o Postiz conhece).

### 2. DNS do subdomínio (GoDaddy) → deixa o site acessível
`relatorios.forsterfilmes.com` ainda não existe no DNS (NXDOMAIN). O DNS é GoDaddy e
não tenho credencial aqui. Crie um registro igual ao de `propostas`/`aprovar`:

| Tipo | Host | Valor |
|---|---|---|
| CNAME | `relatorios` | `oiforster.github.io` |

Propaga em minutos; o HTTPS do Pages provisiona logo depois.

---

## ▶️ Depois dos 2 passos, rode:
```bash
cd ~/forster-relatorios
python3 gerar-relatorio.py --cliente forsterfilmes --mes 2026-06
```
Gera e publica. Confira em `https://relatorios.forsterfilmes.com/forsterfilmes/2026-06/`.
Aí partimos para os ajustes finos (copy das análises, cores, seções).

**Preview do design (mock):** `_preview.html` na raiz do repo (ou rodar o server `relatorios`).
