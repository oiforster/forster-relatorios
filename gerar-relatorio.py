#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar-relatorio.py — Gerador do Relatório Mensal de performance (Forster).

Fluxo:
  1. Resolve cliente -> credenciais Instagram (token + ig_user_id) a partir do Postiz.
  2. Lista a mídia publicada no mês via Instagram Graph API.
  3. Para cada post, busca Insights (views, reach, likes, comments, shares, saved, avg_watch_time).
  4. Cacheia thumbnails (media_url expira).
  5. Ordena destaques e chama o Claude (CLI `claude -p`) para as análises.
  6. Renderiza o template HTML e salva em <slug>/<YYYY-MM>/index.html.
  7. (opcional) git add/commit/push.

Uso:
  python3 gerar-relatorio.py --cliente forsterfilmes --mes 2026-06 [--no-publish] [--no-ia]

Decisões e credenciais ficam em config.json (não versionado) ou via flags.
Tudo é defensivo: falha em um post não aborta o relatório; erros vão para build.log.
"""

import argparse, json, os, re, sys, subprocess, urllib.request, urllib.parse, urllib.error
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template" / "relatorio.html"
LOG = ROOT / "build.log"
GRAPH = "https://graph.facebook.com/v21.0"

# ---------------------------------------------------------------- util / log
def log(msg):
    ts = dt.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def http_get(url, params=None, timeout=40, binary=False, retries=3):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "forster-relatorios/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                return data if binary else json.loads(data.decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            last = f"HTTP {e.code}: {body}"
            if e.code in (400, 404):  # nao adianta repetir
                break
        except Exception as e:
            last = str(e)
        if attempt < retries:
            import time; time.sleep(1.5 * attempt)
    raise RuntimeError(f"GET falhou ({url.split('?')[0]}): {last}")

def br(n):
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except Exception:
        return str(n)

def slugify(s):
    s = s.lower().strip()
    s = re.sub(r"@", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

# ---------------------------------------------------------------- config
def load_config():
    cfg_path = ROOT / "config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text())
    return {}

def resolve_credenciais(cliente, cfg):
    """Retorna dict: {token, ig_user_id, handle, nome, canal_postiz}.
    Ordem: config.json -> variaveis de ambiente -> Postiz DB via SSH."""
    clientes = cfg.get("clientes", {})
    c = clientes.get(cliente) or clientes.get(slugify(cliente)) or {}
    token = c.get("token") or os.environ.get("IG_TOKEN")
    ig_user_id = c.get("ig_user_id") or os.environ.get("IG_USER_ID")
    handle = c.get("handle", cliente.replace("@", ""))
    nome = c.get("nome", handle)
    canal = c.get("canal_postiz")

    if not (token and ig_user_id):
        log("Credenciais Instagram nao no config — tentando Postiz DB via SSH...")
        got = puxar_credenciais_postiz(c.get("profile", handle), cfg)
        if got:
            token = token or got.get("token")
            ig_user_id = ig_user_id or got.get("ig_user_id")
    return {"token": token, "ig_user_id": ig_user_id, "handle": handle,
            "nome": nome, "canal_postiz": canal}

def puxar_credenciais_postiz(profile, cfg):
    """Consulta a tabela Integration do Postiz no Lenovo via SSH para extrair
    token e id da conta Instagram. Ajustável após probe do schema real."""
    ssh = cfg.get("ssh_lenovo", "samuel@192.168.2.50")
    # Postiz roda em docker; a query exata é confirmada no probe (ver README).
    # Placeholder de query — preenchido na fase de wiring com o schema real.
    queries = cfg.get("postiz_db_query")
    if not queries:
        log("  (sem postiz_db_query no config — wiring do DB pendente)")
        return None
    try:
        out = subprocess.run(["ssh", ssh, queries], capture_output=True, text=True, timeout=40)
        if out.returncode != 0:
            log(f"  SSH/DB falhou: {out.stderr[:200]}")
            return None
        return json.loads(out.stdout)
    except Exception as e:
        log(f"  SSH erro: {e}")
        return None

# ---------------------------------------------------------------- dados Instagram
TIPOS = {"REELS": "reel", "VIDEO": "reel", "CAROUSEL_ALBUM": "carrossel", "IMAGE": "card"}

def listar_midia(cred, mes):
    """Lista mídia do mês via Graph API. mes = 'YYYY-MM'."""
    ano, m = map(int, mes.split("-"))
    inicio = dt.datetime(ano, m, 1)
    fim = (dt.datetime(ano + (m == 12), (m % 12) + 1, 1))
    since = int(inicio.timestamp()); until = int(fim.timestamp())
    fields = "id,media_type,media_product_type,caption,permalink,media_url,thumbnail_url,timestamp"
    posts, url = [], f"{GRAPH}/{cred['ig_user_id']}/media"
    params = {"fields": fields, "since": since, "until": until,
              "limit": 100, "access_token": cred["token"]}
    while url:
        data = http_get(url, params)
        for it in data.get("data", []):
            ts = it.get("timestamp", "")
            if ts and not (since <= int(dt.datetime.fromisoformat(ts.replace("+0000", "+00:00")).timestamp()) < until):
                continue
            posts.append(it)
        url = data.get("paging", {}).get("next")
        params = None  # 'next' ja traz tudo
    log(f"Mídia no mês {mes}: {len(posts)} posts")
    return posts

def classificar(post):
    mpt = post.get("media_product_type", "")
    mt = post.get("media_type", "")
    if mpt == "REELS" or mt == "VIDEO":
        return "reel"
    if mt == "CAROUSEL_ALBUM":
        return "carrossel"
    return "card"

def buscar_insights(media_id, tipo, token):
    base = ["reach", "likes", "comments", "shares", "saved"]
    if tipo == "reel":
        metrics = ["views"] + base + ["ig_reels_avg_watch_time"]
    else:
        metrics = ["views"] + base  # 'views' substitui impressions na API nova
    out = {}
    try:
        data = http_get(f"{GRAPH}/{media_id}/insights",
                        {"metric": ",".join(metrics), "access_token": token})
        for row in data.get("data", []):
            vals = row.get("values", [{}])
            out[row["name"]] = vals[0].get("value", 0) if vals else 0
    except Exception as e:
        log(f"  insights {media_id} falhou: {e}")
    return out

def cache_thumb(post, destdir):
    url = post.get("thumbnail_url") or post.get("media_url")
    if not url:
        return None
    destdir.mkdir(parents=True, exist_ok=True)
    ext = ".jpg"
    fname = f"{post['id']}{ext}"
    dest = destdir / fname
    if dest.exists():
        return f"img/{fname}"
    try:
        data = http_get(url, binary=True)
        dest.write_bytes(data)
        return f"img/{fname}"
    except Exception as e:
        log(f"  thumb {post['id']} falhou: {e}")
        return None

# ---------------------------------------------------------------- IA (claude -p)
def claude_analise(prompt, fallback=""):
    try:
        out = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=120)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
        log(f"  claude -p rc={out.returncode}: {out.stderr[:160]}")
    except Exception as e:
        log(f"  claude -p erro: {e}")
    return fallback

def gerar_analises(nome, mes_label, destaques, resumo, usar_ia=True):
    if not usar_ia:
        return {d["rank"]: "" for d in destaques} | {"insight": ""}
    res = {}
    for d in destaques:
        p = (f"Você é estrategista de conteúdo da Forster. Em 2 a 3 frases curtas, tom consultivo "
             f"e humano (sem jargão técnico, sem markdown), explique por que este post do cliente "
             f"'{nome}' se destacou em {mes_label}. Não invente dados. Use só estes números.\n"
             f"Tipo: {d['tipo']}. Legenda: \"{d['caption'][:240]}\". Métricas: {json.dumps(d['metrics'], ensure_ascii=False)}. "
             f"Categoria do destaque: {d['rank_label']}.\nResponda apenas com o texto da análise.")
        res[d["rank"]] = claude_analise(p, fallback="")
    pins = (f"Você é estrategista da Forster. Escreva UM parágrafo (3-4 frases, tom consultivo, "
            f"sem markdown, sem jargão) com o insight do mês de {mes_label} para o cliente '{nome}', "
            f"destacando quais formatos funcionaram e UMA sugestão prática para o próximo mês. "
            f"Não invente dados. Base: {json.dumps(resumo, ensure_ascii=False)}.\nResponda apenas com o parágrafo.")
    res["insight"] = claude_analise(pins, fallback="")
    return res

# ---------------------------------------------------------------- render
def ms_to_label(ms):
    try:
        s = float(ms) / 1000.0
        return f"{s:.1f}s".replace(".", ",")
    except Exception:
        return "—"

def thumb_html(rel, alt, is_reel):
    if not rel:
        return '<div class="play"></div>'
    play = '<div class="play"></div>' if is_reel else ""
    return f'<img src="{rel}" alt="{alt}" loading="lazy">{play}'

def render(ctx):
    html = TEMPLATE.read_text()
    for k, v in ctx.items():
        html = html.replace("{{" + k + "}}", str(v))
    return html

# ---------------------------------------------------------------- publish
def publicar(slug, mes):
    try:
        subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
        msg = f"Relatório {slug}/{mes}"
        subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
        log("Publicado (git push).")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Publicação falhou: {e}")
        return False

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cliente", required=True)
    ap.add_argument("--mes", required=True, help="YYYY-MM")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--no-ia", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    cred = resolve_credenciais(args.cliente, cfg)
    if not (cred["token"] and cred["ig_user_id"]):
        log("ERRO: sem credenciais Instagram (token/ig_user_id). Configure config.json.")
        sys.exit(2)

    nome = cred["nome"]
    slug = slugify(args.cliente)
    MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    ano, m = args.mes.split("-")
    mes_label = f"{MESES[int(m)]} {ano}"

    destdir = ROOT / slug / args.mes
    imgdir = destdir / "img"
    destdir.mkdir(parents=True, exist_ok=True)

    # 1-3. coleta
    posts = listar_midia(cred, args.mes)
    registros = []
    for p in posts:
        tipo = classificar(p)
        ins = buscar_insights(p["id"], tipo, cred["token"])
        thumb = cache_thumb(p, imgdir)
        eng = sum(int(ins.get(k, 0) or 0) for k in ("likes", "comments", "shares", "saved"))
        registros.append({
            "id": p["id"], "tipo": tipo, "permalink": p.get("permalink", "#"),
            "caption": (p.get("caption") or "").strip(), "thumb": thumb,
            "timestamp": p.get("timestamp", ""), "metrics": ins,
            "views": int(ins.get("views", 0) or 0),
            "reach": int(ins.get("reach", 0) or 0),
            "eng": eng,
        })

    # salva dados crus
    (destdir / "dados.json").write_text(json.dumps(
        {"cliente": nome, "mes": args.mes, "posts": registros}, ensure_ascii=False, indent=2))

    if not registros:
        log("AVISO: nenhum post coletado. Verifique credenciais/período.")

    n_reel = sum(r["tipo"] == "reel" for r in registros)
    n_card = sum(r["tipo"] == "card" for r in registros)
    n_carr = sum(r["tipo"] == "carrossel" for r in registros)
    reach_total = sum(r["reach"] for r in registros)
    views_total = sum(r["views"] for r in registros if r["tipo"] == "reel")

    # destaques
    reels = [r for r in registros if r["tipo"] == "reel"]
    d1 = max(reels, key=lambda r: r["views"], default=None) or (registros[0] if registros else None)
    d2 = max(registros, key=lambda r: r["eng"], default=None)
    d3 = max(registros, key=lambda r: r["reach"], default=None)

    # taxa engajamento media = eng / reach
    taxas = [(r["eng"] / r["reach"] * 100) for r in registros if r["reach"]]
    taxa = round(sum(taxas) / len(taxas), 1) if taxas else 0.0

    # distribuicao de alcance por formato
    reach_reel = sum(r["reach"] for r in registros if r["tipo"] == "reel")
    reach_card = sum(r["reach"] for r in registros if r["tipo"] == "card")
    reach_carr = sum(r["reach"] for r in registros if r["tipo"] == "carrossel")
    tot = max(reach_reel + reach_card + reach_carr, 1)
    pct = lambda x: round(x / tot * 100)

    # IA
    def mk(d, rank, rank_label):
        return {"rank": rank, "rank_label": rank_label, "tipo": d["tipo"],
                "caption": d["caption"], "metrics": d["metrics"]} if d else None
    destaques = [x for x in [
        mk(d1, "D1", "mais visto"), mk(d2, "D2", "mais engajamento"),
        mk(d3, "D3", "maior alcance")] if x]
    resumo = {"total": len(registros), "reels": n_reel, "cards": n_card,
              "carrosseis": n_carr, "reach_total": reach_total,
              "views_total": views_total, "taxa_engajamento": taxa}
    analises = gerar_analises(nome, mes_label, destaques, resumo, usar_ia=not args.no_ia)

    g = lambda d, k, default=0: (d["metrics"].get(k, default) if d else default)
    bloco_comp = ""  # comparacao mes anterior — preenchida quando houver snapshot

    ctx = {
        "CLIENTE_NOME": nome, "MES_ANO": mes_label,
        "TOTAL_POSTS": len(registros), "N_REELS": n_reel, "N_CARDS": n_card, "N_CARROSSEIS": n_carr,
        "REACH_TOTAL": reach_total, "VIEWS_TOTAL": views_total, "BLOCO_COMPARACAO": bloco_comp,
        # D1
        "D1_THUMB": thumb_html(d1["thumb"] if d1 else None, "Destaque 1", True),
        "D1_TITULO": "O Reel mais visto do mês" if d1 else "—",
        "D1_VIEWS": g(d1, "views"), "D1_REACH": g(d1, "reach"), "D1_LIKES": g(d1, "likes"),
        "D1_WATCH": ms_to_label(g(d1, "ig_reels_avg_watch_time")),
        "D1_LINK": d1["permalink"] if d1 else "#", "D1_ANALISE": analises.get("D1", ""),
        # D2
        "D2_THUMB": thumb_html(d2["thumb"] if d2 else None, "Destaque 2", d2 and d2["tipo"] == "reel"),
        "D2_TITULO": "O post que mais engajou" if d2 else "—",
        "D2_LIKES": g(d2, "likes"), "D2_COMMENTS": g(d2, "comments"),
        "D2_SHARES": g(d2, "shares"), "D2_SAVED": g(d2, "saved"),
        "D2_LINK": d2["permalink"] if d2 else "#", "D2_ANALISE": analises.get("D2", ""),
        # D3
        "D3_THUMB": thumb_html(d3["thumb"] if d3 else None, "Destaque 3", d3 and d3["tipo"] == "reel"),
        "D3_TITULO": "O post de maior alcance" if d3 else "—",
        "D3_REACH": g(d3, "reach"), "D3_LIKES": g(d3, "likes"),
        "D3_COMMENTS": g(d3, "comments"), "D3_SAVED": g(d3, "saved"),
        "D3_LINK": d3["permalink"] if d3 else "#", "D3_ANALISE": analises.get("D3", ""),
        # engajamento
        "TAXA_ENGAJAMENTO": taxa,
        "BAR_REELS_PCT": pct(reach_reel), "BAR_CARDS_PCT": pct(reach_card),
        "BAR_CARROSSEIS_PCT": pct(reach_carr),
        # insight + rodape
        "INSIGHT_MES": analises.get("insight", ""),
        "INSTAGRAM_URL": f"https://instagram.com/{cred['handle']}",
        "INSTAGRAM_HANDLE": cred["handle"],
    }

    html = render(ctx)
    (destdir / "index.html").write_text(html)
    log(f"Relatório gerado: {destdir/'index.html'}")

    if not args.no_publish:
        publicar(slug, args.mes)
    else:
        log("--no-publish: pulando git push.")

if __name__ == "__main__":
    main()
