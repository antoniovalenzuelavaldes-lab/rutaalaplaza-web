#!/usr/bin/env python3
"""Genera las páginas estáticas para buscadores (SEO) de Ruta a la Plaza a partir de oposiciones.json:

  /oposiciones/                                  listado de convocatorias del PAS de las universidades andaluzas
  /oposiciones/<universidad>/                    una página por universidad (las 10)
  /oposiciones/<universidad>/<oposicion>/        una página por oposición
  /sitemap.xml, /404.html, /og.png, /favicon.png

Cada página tiene su título, descripción, dirección canónica, datos estructurados y texto propio. La web de la aplicación
(la de «#/…») no se puede indexar, por eso existen estas páginas, que enlazan a ella.

Solo usa la biblioteca estándar (y Pillow, si está, para las imágenes). Se ejecuta:
  - en local, desde build.py;
  - cada mañana, en GitHub (vigilancia/generar_seo.py), para que los estados «abierta/cerrada» no queden anticuados.
Uso suelto:  python generar_seo.py RUTA_A_docs
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import unicodedata

BASE = "https://rutaalaplaza.com"
MARCA = "Ruta a la Plaza"
UNIVERSIDADES = [  # (nombre completo, localidad para el texto)
    ("Universidad de Almería", "Almería"), ("Universidad de Cádiz", "Cádiz"), ("Universidad de Córdoba", "Córdoba"),
    ("Universidad de Granada", "Granada"), ("Universidad de Huelva", "Huelva"), ("Universidad de Jaén", "Jaén"),
    ("Universidad de Málaga", "Málaga"), ("Universidad Pablo de Olavide", "Sevilla"), ("Universidad de Sevilla", "Sevilla"),
    ("Universidad Internacional de Andalucía", "Andalucía"),
]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
# Universidades sin convocatoria publicada: lo que se sabe, con su fuente oficial.
NOTA_UNI = {
    "Universidad de Málaga": ("La Universidad de Málaga publicó su oferta de empleo público del personal técnico, de gestión y de administración "
                              "y servicios para 2026, pero todavía no ha convocado los procesos selectivos.",
                              "https://www.juntadeandalucia.es/boja/2026/106/17.html", "Oferta de empleo público 2026 en el BOJA"),
}


def e(t):
    return html.escape(str(t), quote=True)


def slug(t, maximo=70):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if len(t) > maximo:   # se corta en una palabra completa
        t = t[:maximo].rsplit("-", 1)[0]
    return t.strip("-")


def fecha_larga(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def corto(t, n=155):
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def abierta(o, hoy):
    return bool(o.get("plazoPorAbrir")) or bool(o.get("plazoFin") and hoy.isoformat() <= o["plazoFin"])


def rutas(opos):
    """Dirección de cada universidad y de cada oposición (sin repeticiones)."""
    uni = {n: f"/oposiciones/{slug(n)}/" for n, _ in UNIVERSIDADES}
    proc, usadas = {}, set()
    for o in opos:
        nombre = o["nombre"].split(" · ")[-1]   # si hay «escala · puesto», la parte más concreta
        s = f"{slug(o['organismo'])}/{slug(nombre, 70)}"
        base, k = s, 2
        while s in usadas:
            s, k = f"{base}-{k}", k + 1
        usadas.add(s)
        proc[o["id"]] = f"/oposiciones/{s}/"
    return uni, proc


CSS = """:root{--bg:#F1F5F0;--surface:#fff;--surface2:#E8EFE9;--ink:#14231E;--muted:#566962;--line:#D5DFD8;--accent:#A3202D;--pine:#1D5A49;--good:#1B7A4D}
@media (prefers-color-scheme:dark){:root{--bg:#0E1916;--surface:#162621;--surface2:#1D312B;--ink:#E8F0EC;--muted:#92A7A0;--line:#2B4039;--accent:#E8737D;--pine:#62C7A6;--good:#59C58F}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 system-ui,'Segoe UI',Roboto,sans-serif;padding:0 16px 48px}
.w{max-width:880px;margin:0 auto}a{color:var(--pine)}h1,h2,h3{font-family:Georgia,'Segoe UI',serif;line-height:1.2;margin:1.4em 0 .4em}h1{font-size:clamp(1.6rem,5vw,2.3rem);margin-top:.6em}h2{font-size:1.4rem}h3{font-size:1.1rem}
header{border-bottom:1px solid var(--line);margin:0 -16px;padding:12px 16px}header .w{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.brand{font:800 1.2rem Georgia,serif;color:var(--ink);text-decoration:none;margin-right:auto}.brand i{display:inline-block;width:20px;height:20px;border-radius:50% 50% 50% 8px;background:var(--accent);transform:rotate(-20deg);margin-right:8px;vertical-align:-3px}
.btn{display:inline-block;background:var(--ink);color:var(--bg);padding:10px 18px;border-radius:10px;font-weight:700;text-decoration:none}.btn.acc{background:var(--accent);color:#fff}.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
nav.mig{font-size:.9rem;color:var(--muted);margin-top:14px}nav.mig a{color:var(--muted)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:12px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:719px){.grid{grid-template-columns:1fr}}
dl{display:grid;grid-template-columns:170px 1fr;gap:6px 16px;margin:0}dt{font-weight:700}dd{margin:0}@media(max-width:719px){dl{grid-template-columns:1fr}}
.pill{display:inline-block;font:700 .72rem ui-monospace,Consolas,monospace;text-transform:uppercase;letter-spacing:.04em;padding:3px 9px;border-radius:99px;border:1px solid var(--line);background:var(--surface2)}.pill.ok{border-color:var(--good);color:var(--good)}
.muted{color:var(--muted)}.lead{font-size:1.08rem}.row{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}details{margin:8px 0}summary{cursor:pointer;font-weight:700}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);font-size:.88rem;color:var(--muted)}footer a{color:var(--muted)}ul.l{padding-left:1.2em}ul.l li{margin:5px 0}"""

JS_ESTADO = """<script>(function(){var h=new Date(),y=h.getFullYear()+'-'+String(h.getMonth()+1).padStart(2,'0')+'-'+String(h.getDate()).padStart(2,'0');
document.querySelectorAll('[data-fin]').forEach(function(e){var a=y<=e.getAttribute('data-fin');e.textContent=a?'abierta':'cerrada';e.className='pill'+(a?' ok':'')})})()</script>"""


def estado_html(o, hoy):
    if o.get("plazoPorAbrir"):
        return '<span class="pill ok">abierta</span>'
    a = abierta(o, hoy)
    return f'<span class="pill{" ok" if a else ""}" data-fin="{e(o.get("plazoFin", ""))}">{"abierta" if a else "cerrada"}</span>'


def plazo_texto(o, hoy):
    if o.get("plazoPorAbrir"):
        return "El plazo de solicitud todavía no ha empezado: se abrirá al publicarse la convocatoria en el BOE."
    f = fecha_larga(o["plazoFin"])
    if abierta(o, hoy):
        return f"El plazo de solicitud sigue abierto: termina aproximadamente el {f}."
    return f"El plazo de solicitud ya ha terminado (cerró aproximadamente el {f})."


GC = None   # codigo de GoatCounter (estadisticas sin cookies); se fija en generar()


def etiqueta_gc():
    if not GC:
        return ""
    return ("<script>if(navigator.doNotTrack!=='1'&&!navigator.globalPrivacyControl){var s=document.createElement('script');s.async=1;s.src='/count.js';"
            f"s.setAttribute('data-goatcounter','https://{GC}.goatcounter.com/count');document.head.appendChild(s)}}</script>")


def pagina(ruta, titulo, desc, h1, cuerpo, migas, extra_ld=None, noindex=False):
    url = BASE + ruta
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList",
           "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": BASE + u} for i, (n, u) in enumerate(migas)]}]
    if extra_ld:
        ld.append(extra_ld)
    mig = " › ".join(f'<a href="{e(u)}">{e(n)}</a>' if i < len(migas) - 1 else e(n) for i, (n, u) in enumerate(migas))
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titulo)}</title><meta name="description" content="{e(corto(desc))}">
<link rel="canonical" href="{e(url)}"><meta name="robots" content="{'noindex' if noindex else 'index,follow,max-image-preview:large'}">
<meta property="og:type" content="website"><meta property="og:locale" content="es_ES"><meta property="og:site_name" content="{MARCA}">
<meta property="og:title" content="{e(titulo)}"><meta property="og:description" content="{e(corto(desc))}"><meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{BASE}/og.png"><meta name="twitter:card" content="summary_large_image"><meta name="theme-color" content="#1D5A49">
<link rel="icon" href="/favicon.png" type="image/png"><link rel="alternate" type="application/atom+xml" title="Convocatorias de universidades andaluzas" href="/oposiciones/feed.xml">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{CSS}</style></head><body>
<header><div class="w"><a class="brand" href="/"><i></i>{MARCA}</a><a href="/oposiciones/">Convocatorias</a><a class="btn acc" href="/">Entrar</a></div></header>
<main class="w"><nav class="mig" aria-label="Ruta de navegación">{mig}</nav>
<h1>{e(h1)}</h1>
{cuerpo}
</main>
<footer><div class="w"><p>{MARCA} es un servicio independiente de preparación de oposiciones: no está vinculado a ninguna universidad ni administración.
La información de las convocatorias se recoge del BOE y el BOJA y es orientativa: manda siempre el texto oficial.</p>
<p><a href="/oposiciones/">Oposiciones en universidades de Andalucía</a> · <a href="/legal/aviso-legal.html">Aviso legal</a> · <a href="/legal/privacidad.html">Privacidad</a> · <a href="/legal/cookies.html">Cookies</a> · <a href="/legal/condiciones.html">Condiciones</a></p><p>✦ Web desarrollada por <a href="https://valenprojects.online" rel="noopener">ValenProjects</a></p></div></footer>
{JS_ESTADO}{etiqueta_gc()}</body></html>"""


def tarjeta(o, proc, hoy):
    return (f'<div class="card"><div class="row" style="margin:0 0 6px;justify-content:space-between"><span class="muted">{e(o["organismo"])}</span>{estado_html(o, hoy)}</div>'
            f'<h3 style="margin:.2em 0"><a href="{e(proc[o["id"]])}">{e(o["nombre"])}</a></h3>'
            f'<p class="muted" style="margin:0">{e(o["tipo"])} · {e(o["turno"])}{" · grupo " + e(o["grupo"].replace("Grupo ", "")) if o.get("grupo") else ""} · {e(o["plazas"])}</p></div>')


def pag_proceso(o, opos, uni, proc, hoy, temario_ugr):
    n, org = o["nombre"], o["organismo"]
    anio = (o.get("publicado") or "2026")[:4]
    titulo = corto(f"{org}: temario y examen de {n} {anio}" if o.get("programa") or o["estado"] == "disponible" else f"{org}: oposición {n} {anio}", 110)   # la universidad va primero: es lo que busca la gente y lo que no debe recortarse
    desc = (f"Oposición de {n} en la {org}: {o['plazas']}, {o['tipo'].lower()} por turno {o['turno'].lower()}. "
            f"{o['convocatoria']}. Plazo, programa del examen y enlace a la convocatoria oficial.")
    g = f", grupo {o['grupo'].replace('Grupo ', '')}" if o.get("grupo") else ""
    filas = [("Universidad", org), ("Escala o categoría", n), ("Tipo de personal", o["tipo"]), ("Turno", o["turno"]),
             ("Grupo", o.get("grupo", "").replace("Grupo ", "")), ("Plazas", o["plazas"]), ("Convocatoria", o["convocatoria"]),
             ("Examen", o.get("examen", ""))]
    dl = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in filas if b)
    cuerpo = (f'<p class="lead">La {e(org)} ha convocado un proceso selectivo para la <strong>{e(n)}</strong>: {e(o["plazas"])} de personal '
              f'{e(o["tipo"].replace("Personal ", ""))}{e(g)}, por el turno {e(o["turno"].lower())}. {e(o["convocatoria"])}. '
              f'Estado del plazo de solicitud: {estado_html(o, hoy)}</p>'
              f'<h2>Datos de la convocatoria</h2><div class="card"><dl>{dl}</dl></div>'
              f'<h2>Plazo de solicitud</h2><p>{e(plazo_texto(o, hoy))}{" " + e(o["plazoNota"]) if o.get("plazoNota") else ""} '
              f'Comprueba siempre la fecha exacta en la convocatoria oficial.</p>')
    pr = o.get("programa")
    if pr:
        cuerpo += f'<h2>Programa y ejercicios de la oposición</h2><p class="muted">{e(pr["nota"])}</p>'
        for b in pr["bloques"]:
            if b.get("temas"):
                cuerpo += (f'<details{" open" if len(pr["bloques"]) == 1 else ""}><summary>{e(b["titulo"])} ({len(b["temas"])} temas)</summary>'
                           f'<ol>{"".join("<li>" + e(x) + "</li>" for x in b["temas"])}</ol></details>')
            else:
                cuerpo += f'<details open><summary>{e(b["titulo"])} ({b["n"]} temas)</summary><p>{e(b["resumen"])}</p></details>'
        cuerpo += f'<h3>Cómo es el examen</h3><ul class="l">{"".join("<li>" + e(x) + "</li>" for x in pr["ejercicios"])}</ul>'
    tem = o.get("temario") or (temario_ugr if o["estado"] == "disponible" else None)
    if o["estado"] == "disponible" and tem:
        propio = any("gratis" in t for t in tem)   # temarios nuevos: dos temas abiertos y el resto se publica al comprar
        intro = (f'En {MARCA} tienes los dos primeros temas de esta oposición abiertos, con apuntes por artículos y tests con la cita literal de la norma. '
                 f'El programa completo tiene {len(tem)} temas: el resto se desbloquea con la compra, con simulacros, plan de estudio y audio.') if propio else                 (f'En {MARCA} tienes preparados los {len(tem)} temas de esta oposición, con apuntes por artículos, '
                 f'tests con la cita literal de la norma, simulacros, plan de estudio y audio. Los dos primeros son gratuitos.')
        cuerpo += (f'<h2>Temario de la oposición de {e(n)}</h2><p>{e(intro)}</p>'
                   f'<ul class="l">{"".join("<li><strong>" + e(t["titulo"]) + "</strong> <span class=muted>— " + e(t["alcance"][:240]) + "</span></li>" for t in tem)}</ul>')
    if pr or o["estado"] == "disponible":
        prep = ["Empieza por leer el programa completo y marca los temas que menos conoces.",
                "Estudia cada tema con la norma delante: es lo que se pregunta en el examen.",
                "Haz tests por temas desde el principio, no solo al final, y repasa cada fallo con su explicación."]
        if o["estado"] == "disponible":
            prep.append("Combina apuntes, tests con la cita de la norma y audio para repasar en cualquier sitio; los dos primeros temas son gratis.")
        prep.append("Fija una fecha para cada bloque y guarda las últimas semanas para simulacros completos con tiempo.")
        cuerpo += f'<h2>Cómo preparar esta oposición</h2><ol>{"".join("<li>" + e(x) + "</li>" for x in prep)}</ol>'
    faq = [("¿Cuántas plazas tiene?", f"{o['plazas']}, de {o['tipo'].lower()}, por el turno {o['turno'].lower()}."),
           ("¿Cuándo es el examen?", (o.get("examen") or "La fecha se publicará con la lista de personas admitidas.") + " La fecha exacta la fija la universidad y se publica en su portal de personal."),
           ("¿Dónde está la convocatoria oficial?", f"En el {'BOE' if 'BOE' in o['convocatoria'] else 'BOJA'}: {o['convocatoria']}. Aquí tienes el enlace directo a la publicación oficial."),
           ("¿Puedo enterarme de los cambios?", "Sí: suscríbete a la oposición y te avisamos por correo de correcciones, listas de admitidos y fecha del examen.")]
    cuerpo += "<h2>Preguntas frecuentes</h2>" + "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)
    cuerpo += (f'<div class="card"><h2 style="margin-top:0">{"Estudia esta oposición" if o["estado"] == "disponible" else "Sigue esta convocatoria"}</h2>'
               f'<p>{"Empieza gratis con los dos primeros temas, haz tests con la cita de la norma y sigue un plan de estudio hasta el examen." if o["estado"] == "disponible" else "Todavía no tenemos el temario de esta oposición. Suscríbete y te avisamos por correo de los cambios que se publiquen en el BOE o el BOJA y de cuándo esté el temario."}</p>'
               f'<div class="row"><a class="btn acc" href="/#/oposicion/{e(o["id"])}">{"Ver el temario" if o["estado"] == "disponible" else "Avisarme de las novedades"}</a>'
               f'<a class="btn ghost" href="{e(o["enlace"]["u"])}" rel="noopener" target="_blank">{e(o["enlace"]["t"])}</a></div></div>')
    otras = [x for x in opos if x["organismo"] == org and x["id"] != o["id"]]
    if otras:
        cuerpo += f'<h2>Otras oposiciones de la {e(org)}</h2>' + "".join(tarjeta(x, proc, hoy) for x in otras[:6])
    cuerpo += f'<p><a href="{e(uni[org])}">Todas las oposiciones de la {e(org)}</a> · <a href="/oposiciones/">Oposiciones en las universidades de Andalucía</a></p>'
    migas = [("Inicio", "/"), ("Oposiciones", "/oposiciones/"), (org, uni[org]), (n, proc[o["id"]])]
    return pagina(proc[o["id"]], titulo, desc, f"{n} · {org}: oposición {anio}", cuerpo, migas)


def pag_uni(nombre, ciudad, opos, uni, proc, hoy):
    lista = [o for o in opos if o["organismo"] == nombre]
    ab = [o for o in lista if abierta(o, hoy)]
    ce = [o for o in lista if not abierta(o, hoy)]
    titulo = f"Oposiciones {nombre} 2026: convocatorias PAS/PTGAS"
    desc = (f"Convocatorias de oposiciones del personal de administración y servicios (PAS) de la {nombre}: "
            f"{len(ab)} con plazo abierto y {len(ce)} cerradas. Plazas, plazos, programa y temario.") if lista else \
           f"Oposiciones del personal de administración y servicios (PAS) de la {nombre}: estado de las convocatorias de 2026."
    cuerpo = (f'<p class="lead">Convocatorias de oposiciones del <strong>personal técnico, de gestión y de administración y servicios (PAS o PTGAS)</strong> '
              f'de la {e(nombre)}. Aquí tienes los procesos selectivos publicados en el BOE y el BOJA, con sus plazas, su plazo de solicitud y su programa.</p>')
    if lista:
        if ab:
            cuerpo += f'<h2>Oposiciones con plazo de solicitud abierto en la {e(nombre)}</h2>' + "".join(tarjeta(o, proc, hoy) for o in ab)
        if ce:
            cuerpo += f'<h2>Convocatorias cerradas de la {e(nombre)}</h2><p class="muted">Procesos con el plazo de solicitud terminado: puedes seguir su desarrollo (listas de admitidos, fecha del examen, resultados).</p>' + "".join(tarjeta(o, proc, hoy) for o in ce)
    else:
        cuerpo += f'<h2>Convocatorias de la {e(nombre)}</h2><p>No hay convocatorias publicadas de la {e(nombre)} en este momento.</p>'
    if nombre in NOTA_UNI:
        t, u, n = NOTA_UNI[nombre]
        cuerpo += f'<div class="card"><p style="margin:0">{e(t)} <a href="{e(u)}" rel="noopener" target="_blank">{e(n)}</a>.</p></div>'
    cuerpo += (f'<div class="card"><h2 style="margin-top:0">Avisos de las convocatorias de la {e(nombre)}</h2><p>Suscríbete a una oposición y te escribimos cuando haya novedades oficiales '
               f'(correcciones, listas de admitidos, fecha del examen).</p><div class="row"><a class="btn acc" href="/#/oposiciones">Ver oposiciones y suscribirme</a></div></div>'
               f'<p><a href="/oposiciones/">Oposiciones en todas las universidades de Andalucía</a></p>')
    migas = [("Inicio", "/"), ("Oposiciones", "/oposiciones/"), (nombre, uni[nombre])]
    return pagina(uni[nombre], titulo, desc, f"Oposiciones de la {nombre}: convocatorias del PTGAS (PAS)", cuerpo, migas)


def pag_hub(opos, uni, proc, hoy):
    ab = [o for o in opos if abierta(o, hoy)]
    escalas = sorted({re.sub(r"^Escala (?:de |de los |de las )?", "", o["nombre"]).split(" · ")[0] for o in opos if o["tipo"] == "Personal funcionario"})[:8]
    titulo = "Oposiciones PTGAS universidades de Andalucía 2026: convocatorias"
    desc = (f"Convocatorias de oposiciones PTGAS (PAS) de las 10 universidades públicas andaluzas: "
            f"{len(ab)} con plazo abierto. Granada, Sevilla, Málaga, Cádiz, Córdoba, Almería, Huelva, Jaén, UPO y UNIA.")
    cuerpo = (f'<p class="lead">Todas las <strong>convocatorias de oposiciones de las universidades públicas de Andalucía</strong> para el personal de administración y servicios (PAS), '
              f'recogidas del BOE y el BOJA: Universidad de Granada, de Sevilla, de Málaga, de Cádiz, de Córdoba, de Almería, de Huelva, de Jaén, Pablo de Olavide e Internacional de Andalucía. '
              f'Ahora mismo hay <strong>{len(ab)} con el plazo de solicitud abierto</strong> y {len(opos)} en el listado.</p>')
    if ab:
        cuerpo += "<h2>Convocatorias con plazo de solicitud abierto</h2>" + "".join(tarjeta(o, proc, hoy) for o in ab) + '<p><a href="/oposiciones/abiertas/">Ver solo las oposiciones abiertas ahora</a></p>'
    cuerpo += '<h2>Oposiciones por universidad</h2><div class="grid">'
    for n, c in UNIVERSIDADES:
        k = [o for o in opos if o["organismo"] == n]
        a = sum(1 for o in k if abierta(o, hoy))
        cuerpo += (f'<div class="card"><h3 style="margin:.1em 0"><a href="{e(uni[n])}">Oposiciones {e(n)}</a></h3>'
                   f'<p class="muted" style="margin:0">{len(k)} convocatorias · {a} abiertas</p></div>')
    cuerpo += '</div><h2>Qué es el PTGAS (antes PAS): personal técnico, de gestión y de administración y servicios</h2>'
    cuerpo += ('<p>El personal técnico, de gestión y de administración y servicios (PTGAS, sigla que usa la Ley Orgánica del Sistema Universitario y que sustituye a la antigua PAS) de las universidades es el que se ocupa de la gestión, la administración, '
               'las bibliotecas, los archivos, los laboratorios y los servicios técnicos. Se accede mediante procesos selectivos de concurso-oposición '
               '(o por promoción interna) que cada universidad convoca y publica en el BOE y el BOJA.</p>')
    if escalas:
        cuerpo += f'<p>Entre las escalas y categorías convocadas ahora figuran: {e("; ".join(escalas))}.</p>'
    cuerpo += ('<h2>Preguntas frecuentes</h2>'
               '<details><summary>¿Dónde se publican las convocatorias?</summary><p>En el Boletín Oficial del Estado (BOE), en el Boletín Oficial de la Junta de Andalucía (BOJA) y en la página de personal de cada universidad. '
               'Este listado se actualiza a partir de esas publicaciones.</p></details>'
               '<details><summary>¿Qué significa «promoción interna»?</summary><p>Es el turno reservado al personal que ya trabaja en la universidad y quiere acceder a una escala de nivel superior. '
               'El turno libre está abierto a cualquier persona que cumpla los requisitos.</p></details>'
               '<details><summary>¿Cómo sé si ha cambiado algo de mi convocatoria?</summary><p>Suscríbete a la oposición en Ruta a la Plaza y te avisamos por correo cuando se publique una corrección, '
               'una lista de admitidos o la fecha del examen.</p></details>'
               '<div class="card"><h2 style="margin-top:0">Prepara tu oposición</h2><p>Apuntes por artículos, tests con la cita literal de la norma, simulacros, plan de estudio y audio. '
               'Disponible ahora: Escala de Auxiliares de Archivos, Bibliotecas y Museos de la Universidad de Granada, con los dos primeros temas gratis.</p>'
               '<div class="row"><a class="btn acc" href="/#/oposiciones">Ver oposiciones y empezar</a></div></div>')
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Universidades públicas de Andalucía",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "url": BASE + uni[n]} for i, (n, _) in enumerate(UNIVERSIDADES)]}
    return pagina("/oposiciones/", titulo, desc, "Oposiciones PTGAS (PAS) en las universidades de Andalucía: convocatorias", cuerpo,
                  [("Inicio", "/"), ("Oposiciones", "/oposiciones/")], ld)


def pag_abiertas(opos, uni, proc, hoy):
    ab = [o for o in opos if abierta(o, hoy)]
    ab.sort(key=lambda o: o.get("plazoFin") or "9999")
    titulo = "Oposiciones abiertas ahora en universidades de Andalucía"
    desc = f"{len(ab)} oposiciones PTGAS (PAS) con el plazo de solicitud abierto en las universidades andaluzas: plazas, plazo, programa y enlace oficial." if ab else \
           "Oposiciones PTGAS (PAS) con el plazo de solicitud abierto en las universidades andaluzas. Ahora mismo no hay ninguna abierta."
    cuerpo = (f'<p class="lead">Convocatorias del personal técnico, de gestión y de administración y servicios (PTGAS o PAS) de las universidades públicas de Andalucía '
              f'con el <strong>plazo de solicitud abierto</strong>, ordenadas por la fecha en que termina. Ahora mismo hay <strong>{len(ab)}</strong>.</p>')
    cuerpo += "".join(tarjeta(o, proc, hoy) for o in ab) if ab else "<p>Ahora mismo no hay ninguna convocatoria con el plazo abierto. Suscríbete a tu universidad y te avisamos cuando salga una.</p>"
    cuerpo += ('<div class="card"><h2 style="margin-top:0">¿No ves la tuya?</h2><p>Mira todas las convocatorias, también las cerradas, o suscríbete a una oposición para recibir los cambios oficiales por correo.</p>'
               '<div class="row"><a class="btn acc" href="/oposiciones/">Todas las convocatorias</a><a class="btn ghost" href="/#/oposiciones">Suscribirme</a></div></div>')
    return pagina("/oposiciones/abiertas/", titulo, desc, "Oposiciones abiertas ahora en las universidades de Andalucía", cuerpo,
                  [("Inicio", "/"), ("Oposiciones", "/oposiciones/"), ("Abiertas ahora", "/oposiciones/abiertas/")])


def feed_atom(opos, uni, proc):
    ult = sorted(opos, key=lambda o: o.get("publicado", ""), reverse=True)
    ahora = (ult[0].get("publicado") or "2026-01-01") + "T00:00:00Z"
    items = ""
    for o in ult:
        resumen = f"{o['organismo']}: {o['plazas']}, {o['tipo'].lower()}, turno {o['turno'].lower()}. {o['convocatoria']}."
        items += (f"<entry><id>{BASE}{proc[o['id']]}</id><title>{e(o['organismo'] + ': ' + o['nombre'])}</title>"
                  f"<link href=\"{BASE}{proc[o['id']]}\"/><updated>{(o.get('publicado') or '2026-01-01')}T00:00:00Z</updated><summary>{e(resumen)}</summary></entry>")
    return (f'<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Oposiciones PTGAS de las universidades de Andalucía · {MARCA}</title>'
            f'<id>{BASE}/oposiciones/</id><link href="{BASE}/oposiciones/"/><link rel="self" href="{BASE}/oposiciones/feed.xml"/><updated>{ahora}</updated>'
            f'<author><name>{MARCA}</name></author>{items}</feed>')


def bloque_inicio(opos, uni, proc, hoy):
    """Texto que ve el buscador en la portada antes de ejecutar JavaScript (la aplicación lo sustituye al cargar)."""
    ab = [o for o in opos if abierta(o, hoy)]
    li = "".join(f'<li><a href="{e(uni[n])}">Oposiciones {e(n)}</a></li>' for n, _ in UNIVERSIDADES)
    la = "".join(f'<li><a href="{e(proc[o["id"]])}">{e(o["nombre"])} · {e(o["organismo"])}</a></li>' for o in ab[:12])
    return ('<section id="seo-inicial" style="max-width:880px;margin:0 auto;padding:24px 0"><h1>Oposiciones en las universidades de Andalucía: convocatorias, temario y tests</h1>'
            '<p>Convocatorias del personal de administración y servicios (PAS) de las universidades públicas andaluzas, con apuntes por artículos, tests con la cita literal de la norma, '
            'simulacros y plan de estudio. Disponible: Escala de Auxiliares de Archivos, Bibliotecas y Museos de la Universidad de Granada, con 2 temas gratis.</p>'
            f'<h2>Oposiciones por universidad</h2><ul>{li}</ul><h2>Convocatorias con plazo abierto</h2><ul>{la}</ul>'
            '<p><a href="/oposiciones/abiertas/">Oposiciones abiertas ahora</a> · <a href="/oposiciones/">Ver todas las convocatorias</a></p><noscript><p>Para estudiar los temas necesitas activar JavaScript.</p></noscript></section>')


def imagenes(docs):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return
    def fuente(nombres, tam):
        for n in nombres:
            try:
                return ImageFont.truetype(n, tam)
            except Exception:
                pass
        return ImageFont.load_default()
    g = ["georgiab.ttf", "georgia.ttf", "DejaVuSerif-Bold.ttf"]; s = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
    im = Image.new("RGB", (1200, 630), "#1D5A49"); d = ImageDraw.Draw(im)
    d.ellipse((70, 70, 150, 150), fill="#A3202D")
    d.text((175, 82), MARCA, font=fuente(g, 64), fill="white")
    d.text((70, 230), "Oposiciones en las", font=fuente(g, 76), fill="white")
    d.text((70, 330), "universidades de Andalucía", font=fuente(g, 76), fill="white")
    d.text((70, 470), "Convocatorias · temario · tests con cita de la norma", font=fuente(s, 38), fill="#CFE3DB")
    d.text((70, 530), "rutaalaplaza.com", font=fuente(s, 34), fill="#CFE3DB")
    im.save(os.path.join(docs, "og.png"), optimize=True)
    ic = Image.new("RGBA", (96, 96), (0, 0, 0, 0)); di = ImageDraw.Draw(ic)
    di.ellipse((8, 8, 88, 88), fill="#A3202D"); di.ellipse((30, 30, 66, 66), fill="#F1F5F0")
    ic.save(os.path.join(docs, "favicon.png"))


def pag_404():
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Página no encontrada · {MARCA}</title>
<meta name="robots" content="noindex"><link rel="icon" href="/favicon.png"><style>{CSS}</style></head><body><header><div class="w"><a class="brand" href="/"><i></i>{MARCA}</a></div></header>
<main class="w"><h1>No encontramos esta página</h1><p>La dirección no existe o ha cambiado. Puedes volver al inicio o ver las convocatorias de las universidades de Andalucía.</p>
<div class="row"><a class="btn acc" href="/">Ir al inicio</a><a class="btn ghost" href="/oposiciones/">Ver convocatorias</a></div></main></body></html>"""


def codigo_gc(docs):
    """Lee el codigo de GoatCounter de docs/config.js (lo usa el proceso diario, que no tiene la configuracion local)."""
    try:
        m = re.search(r'"goatcounter":\s*"([a-z0-9-]+)"', open(os.path.join(docs, "config.js"), encoding="utf8").read())
        return m.group(1) if m else None
    except OSError:
        return None


def generar(opos, docs, hoy=None, temario_ugr=None, goatcounter=None):
    global GC
    GC = goatcounter if goatcounter is not None else codigo_gc(docs)
    hoy = hoy or dt.date.today()
    uni, proc = rutas(opos)
    destino = os.path.join(docs, "oposiciones")
    shutil.rmtree(destino, ignore_errors=True)
    paginas = {"/oposiciones/": pag_hub(opos, uni, proc, hoy)}
    paginas["/oposiciones/abiertas/"] = pag_abiertas(opos, uni, proc, hoy)
    for n, c in UNIVERSIDADES:
        paginas[uni[n]] = pag_uni(n, c, opos, uni, proc, hoy)
    for o in opos:
        paginas[proc[o["id"]]] = pag_proceso(o, opos, uni, proc, hoy, temario_ugr if o["estado"] == "disponible" else None)
    for ruta, contenido in paginas.items():
        d = os.path.join(docs, ruta.strip("/"))
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf8").write(contenido)
    open(os.path.join(docs, "404.html"), "w", encoding="utf8").write(pag_404())
    open(os.path.join(docs, "oposiciones", "feed.xml"), "w", encoding="utf8").write(feed_atom(opos, uni, proc))
    urls = ["/"] + sorted(paginas) + [f"/legal/{x}.html" for x in ("aviso-legal", "privacidad", "cookies", "condiciones", "desistimiento")]
    open(os.path.join(docs, "sitemap.xml"), "w", encoding="utf8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{BASE}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    if not os.path.exists(os.path.join(docs, "og.png")):
        imagenes(docs)
    return paginas, bloque_inicio(opos, uni, proc, hoy)


def actualiza_portada(docs, bloque):
    p = os.path.join(docs, "index.html")
    t = open(p, encoding="utf8").read()
    n = re.sub(r'<section id="seo-inicial".*?</section>', lambda _: bloque, t, count=1, flags=re.S)
    if n != t:
        open(p, "w", encoding="utf8").write(n)


if __name__ == "__main__":
    docs = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")
    opos = json.load(open(os.path.join(docs, "oposiciones.json"), encoding="utf8"))
    _f = os.path.join(docs, "oposiciones-auto.json")   # fichas creadas solas por el proceso diario
    if os.path.exists(_f):
        opos += [o for o in json.load(open(_f, encoding="utf8")) if o["id"] not in {x["id"] for x in opos}]
    ugr = next((o.get("temario") for o in opos if o.get("temario")), None)
    paginas, bloque = generar(opos, docs, temario_ugr=ugr)
    actualiza_portada(docs, bloque)
    print(f"{len(paginas)} páginas generadas en {docs}")
