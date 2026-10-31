#!/usr/bin/env python3
"""Texto del boletín semanal «Oposiciones PTGAS abiertas en Andalucía», listo para pegar en Telegram, WhatsApp, Instagram y X.
Lee oposiciones.json y oposiciones-auto.json (las abiertas por fecha de plazo) y añade enlaces con marca de origen.
Uso: python boletin_semanal.py  ->  boletin.md"""
import datetime as dt, json, os, re, sys
sys.stdout.reconfigure(encoding="utf8")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hoy = dt.date.today()
def abre(n):   # en el proyecto local los listados están en la raíz; en el repositorio publicado, en docs/
    for c in (os.path.join(RAIZ, n), os.path.join(RAIZ, "docs", n)):
        if os.path.exists(c):
            return json.load(open(c, encoding="utf8"))
    return []
lista = abre("oposiciones.json") + abre("oposiciones-auto.json")
def slug(t): return re.sub(r"[^a-z0-9]+", "-", __import__("unicodedata").normalize("NFD", t.lower()).encode("ascii", "ignore").decode()).strip("-")
ab = [o for o in lista if o.get("plazoPorAbrir") or (o.get("plazoFin") and o["plazoFin"] >= hoy.isoformat())]
ab.sort(key=lambda o: o.get("plazoFin") or "9999")
def fecha(o): return "plazo por abrir" if o.get("plazoPorAbrir") else "hasta el " + dt.date.fromisoformat(o["plazoFin"]).strftime("%d/%m")
lin = [f"# Boletín del {hoy.strftime('%d/%m/%Y')}\n"]
corto = [f"📢 Oposiciones PTGAS abiertas en universidades andaluzas ({hoy.strftime('%d/%m')}):\n"]
for o in ab:
    n = (o["nombre"][:60] + "…") if len(o["nombre"]) > 60 else o["nombre"]
    corto.append(f"• {o['organismo'].replace('Universidad ', 'U. ')}: {n} · {o.get('plazas','')} · {fecha(o)}")
corto += ["", "Programa, plazos y avisos de cambios: https://rutaalaplaza.com/oposiciones/abiertas/?utm_source={red}&utm_campaign=boletin", "Fuente: BOE y BOJA. Comprueba siempre la convocatoria oficial."]
lin += ["## Telegram / WhatsApp (canal propio)\n", "\n".join(corto).replace("{red}", "telegram"), "\n## Instagram (pie de la imagen o historia)\n",
        "\n".join(corto[:1] + corto[1:1 + len(ab)]).replace("{red}", "instagram") + "\n\nEnlace en la bio 👆 #PTGAS #oposiciones #universidad #Andalucía",
        "\n## X (hilo: un mensaje por convocatoria)\n"]
for i, o in enumerate(ab, 1):
    lin.append(f"{i}/{len(ab)} {o['organismo'].replace('Universidad ', 'U. ')}: {o['nombre'][:90]} · {fecha(o)}\nhttps://rutaalaplaza.com/oposiciones/{slug(o['organismo'])}/?utm_source=x&utm_campaign=boletin\n")
lin.append(f"\n({len(ab)} abiertas hoy). Repetir cada lunes: ejecutar este script y pegar.")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "boletin.md"), "w", encoding="utf8").write("\n".join(lin))
print("\n".join(corto[:1 + len(ab)]))
