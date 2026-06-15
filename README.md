# forster-relatorios

Relatórios mensais de performance do Instagram para clientes da Forster.
Página HTML animada (estilo Spotify Wrapped), dados reais da Instagram Insights API
e análise escrita por IA (Claude). Publicado via GitHub Pages em
**relatorios.forsterfilmes.com**.

## Estrutura

```
template/relatorio.html     Template base (placeholders {{...}})
gerar-relatorio.py          Gerador (coleta dados -> IA -> render -> publica)
<slug-cliente>/<YYYY-MM>/   Relatório de cada cliente/mês (index.html + img/ + dados.json)
config.json                 Credenciais por cliente (NÃO versionado)
```

## Uso

```bash
python3 gerar-relatorio.py --cliente forsterfilmes --mes 2026-06
# opções: --no-publish (não faz git push)  --no-ia (pula análises do Claude)
```

## config.json (não versionado)

```json
{
  "ssh_lenovo": "samuel@192.168.2.50",
  "clientes": {
    "forsterfilmes": {
      "nome": "Forster",
      "handle": "forsterfilmes",
      "profile": "forsterfilmes",
      "canal_postiz": "cmqdfi4c80001od75su2tkblj",
      "token": "<IG_GRAPH_TOKEN>",
      "ig_user_id": "<IG_BUSINESS_ACCOUNT_ID>"
    }
  }
}
```

As credenciais do Instagram (token + ig_user_id) também podem vir de:
1. variáveis de ambiente `IG_TOKEN` / `IG_USER_ID`;
2. da tabela `Integration` do Postiz no Lenovo (via SSH) — ver `postiz_db_query` no config.

## Métricas coletadas (Instagram Graph API)

`views`, `reach`, `likes`, `comments`, `shares`, `saved`, `ig_reels_avg_watch_time`.

Cada relatório é um snapshot congelado: thumbnails são cacheadas localmente
(o `media_url` do Instagram expira) e os dados crus ficam em `dados.json`.
