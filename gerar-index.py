#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera a página inicial (index.html na raiz) listando todos os relatórios
existentes, agrupados por cliente. Lê <slug>/<YYYY-MM>/dados.json.

Uso:  python3 gerar-index.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

def br(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(n)

def coletar():
    clientes = {}
    for dados in sorted(ROOT.glob("*/*/dados.json")):
        slug = dados.parent.parent.name
        mes = dados.parent.name  # YYYY-MM
        try:
            d = json.loads(dados.read_text())
        except Exception:
            continue
        posts = d.get("posts", [])
        reach = sum(int(p.get("reach", 0) or 0) for p in posts)
        nome = d.get("cliente", slug)
        clientes.setdefault(slug, {"nome": nome, "meses": []})
        clientes[slug]["meses"].append({
            "mes": mes, "n": len(posts), "reach": reach,
            "label": f"{MESES[int(mes[5:7])]} {mes[:4]}",
        })
    for c in clientes.values():
        c["meses"].sort(key=lambda m: m["mes"], reverse=True)
    return dict(sorted(clientes.items(), key=lambda kv: kv[1]["nome"].lower()))

def card(slug, mes):
    return f'''      <a class="card" href="{slug}/{mes['mes']}/">
        <div class="card-mes">{mes['label']}</div>
        <div class="card-stats"><span>{br(mes['n'])} posts</span><span>{br(mes['reach'])} alcance</span></div>
        <div class="card-go">Ver relatório →</div>
      </a>'''

def bloco(slug, c):
    cards = "\n".join(card(slug, m) for m in c["meses"])
    return f'''  <section class="cliente">
    <h2>{c['nome']}</h2>
    <div class="cards">
{cards}
    </div>
  </section>'''

def render(clientes):
    blocos = "\n".join(bloco(s, c) for s, c in clientes.items()) or \
        '<p class="vazio">Nenhum relatório ainda.</p>'
    total = sum(len(c["meses"]) for c in clientes.values())
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatórios · Forster</title>
<meta name="description" content="Relatórios mensais de performance do Instagram — por Forster.">
<style>
  :root{{--teal-300:#5eead4;--teal-400:#2dd4bf;--teal-500:#14b8a6;--teal-600:#0d9488;
    --ink:#0b1220;--muted:rgba(255,255,255,.6);--muted-2:rgba(255,255,255,.4);
    --font:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:var(--font);background:var(--ink);color:#fff;-webkit-font-smoothing:antialiased;
    min-height:100vh;background:radial-gradient(120% 80% at 50% 0%,#0f766e 0%,#0b1220 55%)}}
  .wrap{{max-width:980px;margin:0 auto;padding:90px 26px 80px}}
  .wordmark{{font-weight:800;letter-spacing:.32em;font-size:14px;opacity:.9;margin-bottom:40px}}
  .wordmark b{{color:var(--teal-400)}}
  h1{{font-size:clamp(40px,8vw,72px);font-weight:800;letter-spacing:-.03em;line-height:1.02}}
  .sub{{color:var(--muted);font-size:clamp(16px,2.2vw,20px);margin-top:16px;max-width:46ch}}
  .cliente{{margin-top:64px}}
  .cliente h2{{font-size:clamp(22px,3.4vw,30px);font-weight:700;letter-spacing:-.02em;
    padding-bottom:14px;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:26px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px}}
  .card{{display:block;text-decoration:none;color:#fff;background:rgba(255,255,255,.05);
    border:1px solid rgba(255,255,255,.1);border-radius:18px;padding:22px 22px 18px;
    transition:transform .15s,border-color .15s,background .15s}}
  .card:hover{{transform:translateY(-3px);border-color:var(--teal-500);background:rgba(20,184,166,.08)}}
  .card-mes{{font-size:22px;font-weight:750;letter-spacing:-.01em}}
  .card-stats{{display:flex;gap:16px;margin-top:12px;color:var(--muted);font-size:13px}}
  .card-stats span{{display:flex;flex-direction:column}}
  .card-go{{margin-top:18px;color:var(--teal-300);font-weight:600;font-size:14px}}
  .vazio{{color:var(--muted);margin-top:40px}}
  footer{{margin-top:80px;color:var(--muted-2);font-size:13px;border-top:1px solid rgba(255,255,255,.08);padding-top:24px}}
</style>
</head>
<body>
  <div class="wrap">
    <div class="wordmark">FOR<b>STER</b></div>
    <h1>Relatórios de<br>performance</h1>
    <p class="sub">Cada mês, um retrato do que aconteceu no Instagram dos nossos clientes — dados reais e análise da Forster.</p>
{blocos}
    <footer>{total} relatório(s) · relatorios.forsterfilmes.com</footer>
  </div>
</body>
</html>
'''

if __name__ == "__main__":
    clientes = coletar()
    (ROOT / "index.html").write_text(render(clientes))
    n = sum(len(c["meses"]) for c in clientes.values())
    print(f"index.html gerado — {len(clientes)} cliente(s), {n} relatório(s).")
