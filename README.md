# forster-relatorios

Relatórios mensais de performance do Instagram para clientes da Forster.
Página HTML animada (estilo Spotify Wrapped), com dados reais da Instagram
Insights API e análise escrita por IA (Claude). Publicado via GitHub Pages em
**relatorios.forsterfilmes.com**.

Cada relatório é um **snapshot congelado** de um cliente/mês, no ar em
`relatorios.forsterfilmes.com/<slug>/<YYYY-MM>/`.

## Estrutura

```
template/relatorio.html     Template base (placeholders {{...}})
gerar-relatorio.py          Gerador (coleta dados -> IA -> render -> publica)
gerar-index.py              Gera a home (index.html) listando os relatórios por cliente
configurar-clientes.sh      Popula o config.json a partir dos canais do Postiz (NÃO versionado)
puxar-token.sh              Lê token/ig_user_id de um canal no Postiz (NÃO versionado)
config.json                 Credenciais por cliente (NÃO versionado)
CNAME / .nojekyll           GitHub Pages: domínio + serve index.html como home
<slug>/<YYYY-MM>/           Relatório de cada cliente/mês:
  index.html                  página final self-contained
  img/                        thumbnails cacheadas (media_url do IG expira)
  dados.json                  dados crus coletados (para --rerender e comparação m-a-m)
  analises.json               textos da IA cacheados (para --rerender)
```

## Como gerar (recomendado): skill `/relatorio`

O caminho normal é a skill conversacional **`/relatorio`** (em
`~/.claude/skills/relatorio/`), que conduz cliente → mês → geração → resumo →
publicação com confirmação, e suporta gerar **todos os clientes** de uma vez.
Roda **local** (precisa do config.json, token, LAN pro Lenovo e CLI `claude`).

## Uso direto (script)

```bash
# Gera o mês fresh (coleta API + análise IA) e publica:
python3 gerar-relatorio.py --cliente forsterfilmes --mes 2026-06

# Atualiza a home depois de gerar/alterar relatórios:
python3 gerar-index.py
```

### Modos / flags

| Flag           | Efeito |
|----------------|--------|
| (padrão)       | Coleta a API + chama a IA + renderiza + `git push`. Use para **fechar o mês**. |
| `--no-publish` | Gera local, sem `git push`. |
| `--no-ia`      | Pula as análises do Claude (textos vazios). |
| `--rerender`   | Re-renderiza do cache (`dados.json` + `analises.json`), **sem API/IA**. Use só para **mudanças de design** — sem custo. |

`--rerender` exige que o mês já tenha sido gerado fresh ao menos uma vez (precisa do cache).

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
      "ig_user_id": "<IG_BUSINESS_ACCOUNT_ID>",
      "graph_base": "https://graph.instagram.com/v21.0"
    }
  }
}
```

- `graph_base`: canais `instagram-standalone` usam **`graph.instagram.com`** (não `graph.facebook.com`).
- Credenciais também podem vir de env (`IG_TOKEN` / `IG_USER_ID`) ou da tabela
  `Integration` do Postiz no Lenovo (via SSH — passo do usuário).
- Multi-cliente: `configurar-clientes.sh` lê todos os canais do Postiz de uma vez,
  resolve o @handle via Graph API e popula o `config.json`.
- **Token do Instagram vence ~60 dias.** Coleta vazia / erro de auth = renovar o
  token rodando `puxar-token.sh`.

## Métricas (Instagram Graph API v21)

Coletadas por post: `views`, `reach`, `likes`, `comments`, `shares`, `saved`,
`ig_reels_avg_watch_time`. Parsing aceita o formato novo (`total_value.value`) e o
legado (`values[0].value`), com fallback por métrica.

### Destaques — métricas dinâmicas

São escolhidos 3 destaques (posts distintos): **#1 mais visto**, **#2 mais
engajamento**, **#3 maior alcance**. Cada card mostra até 4 métricas a partir de uma
**lista priorizada própria** (`METRICA_CANDIDATAS` no gerador), que preserva a
"personalidade" do card. Slots **zerados são pulados** e substituídos pela próxima
métrica relevante com valor — nunca expõe `0`. Ex.: o #3 com 0 comentários mostra
"9 compart." no lugar. Isso também faz o "Tempo médio" (só Reels) sumir sozinho em
não-Reels. Com poucos posts no mês, destaques sem post são removidos do HTML.

## Design

Capítulos coloridos (cada seção tem seu `--accent`): capa/insight teal âncora,
resumo indigo, alcance magenta, d1 ouro, d2 esmeralda, d3 violeta, engajamento azul.
Fontes Plus Jakarta Sans (display) + Inter (corpo). Fundo dos destaques = thumbnail
borrada (`.sec-bg`) + tint radial da cor do capítulo (`.sec-bg-tint`). Animação de
scroll e countup via GSAP ScrollTrigger (CDN). Grain + orbs em todas as seções.

## Segurança

- **Nunca** imprimir/commitar o token do Instagram. `config.json`,
  `configurar-clientes.sh`, `puxar-token.sh` são gitignored.
- Publicar = `git push` (ação para fora) — confirmar antes.
- Cada relatório é congelado: thumbnails cacheadas localmente; dados crus em `dados.json`.
