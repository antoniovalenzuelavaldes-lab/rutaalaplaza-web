#!/usr/bin/env python3
"""Genera el material de difusión de la primera semana a partir de los dos temas GRATUITOS (g1 y g2, ya públicos):
  test-del-dia/dia-N-pregunta.png y dia-N-respuesta.png (carrusel de Instagram, 1080x1350)
  test-del-dia/textos.md (pie de cada publicación, versión corta para X y Telegram, con enlace marcado)
  perfil/avatar-512.png, perfil/banner-1500x500.png y perfil/biografias.md
"""
import glob
import json
import os
import re
import sys
import textwrap

sys.stdout.reconfigure(encoding="utf8")
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CONTENIDO = r"C:\Proyectos\14.ruta-a-la-plaza\Oposiciones UGR Lourdes\contenido"
F = r"C:\Windows\Fonts"
PINO, GRANADA, FONDO, TINTA, SUAVE = "#1D5A49", "#A3202D", "#F1F5F0", "#14231E", "#566962"


def fuente(nombre, tam):
    for n in nombre:
        try:
            return ImageFont.truetype(os.path.join(F, n), tam)
        except Exception:
            pass
    return ImageFont.load_default()


SERIF_B = ["georgiab.ttf", "timesbd.ttf"]
SANS, SANS_B = ["segoeui.ttf", "arial.ttf"], ["segoeuib.ttf", "arialbd.ttf"]


def ajusta(draw, texto, nombres, tam, ancho, alto, minimo=26):
    """Reduce la letra hasta que el texto entra en el recuadro; devuelve (fuente, líneas, interlineado)."""
    while True:
        f = fuente(nombres, tam)
        lineas = []
        for parrafo in texto.split("\n"):
            palabras, actual = parrafo.split(), ""
            for p in palabras:
                prueba = (actual + " " + p).strip()
                if draw.textlength(prueba, font=f) <= ancho:
                    actual = prueba
                else:
                    lineas.append(actual)
                    actual = p
            lineas.append(actual)
        inter = int(tam * 1.32)
        if len(lineas) * inter <= alto or tam <= minimo:
            return f, lineas, inter
        tam -= 2


def bloque(draw, x, y, texto, nombres, tam, ancho, alto, color):
    f, lineas, inter = ajusta(draw, texto, nombres, tam, ancho, alto)
    for i, l in enumerate(lineas):
        draw.text((x, y + i * inter), l, font=f, fill=color)
    return y + len(lineas) * inter


def lienzo(titulo_sup, pie):
    im = Image.new("RGB", (1080, 1350), FONDO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1080, 150), fill=PINO)
    d.ellipse((60, 42, 126, 108), fill=GRANADA)
    d.text((150, 38), "Ruta a la Plaza", font=fuente(SERIF_B, 52), fill="white")
    d.text((150, 100), titulo_sup, font=fuente(SANS, 28), fill="#CFE3DB")
    d.rectangle((0, 1250, 1080, 1350), fill=PINO)
    d.text((60, 1280), pie, font=fuente(SANS_B, 34), fill="white")
    return im, d


def preguntas():
    """Siete preguntas de g1 y g2 que quepan bien en una imagen, repartidas por los temas."""
    sel = []
    for f in sorted(glob.glob(os.path.join(CONTENIDO, "t0[12].json"))):
        t = json.load(open(f, encoding="utf8"))
        buenas = [p for p in t["preguntas"] if len(p["q"]) <= 210 and all(len(o) <= 95 for o in p["o"]) and len(p["e"]) <= 330 and len(p["ref"][2]) <= 330]
        paso = max(1, len(buenas) // (4 if t["id"] == "g1" else 3))
        sel += [(t, p) for p in buenas[::paso][: (4 if t["id"] == "g1" else 3)]]
    # segunda semana: una pregunta de cada uno de los temas abiertos nuevos (otras oposiciones)
    extra = [("temarios/ual-auxiliar-administrativa/ual-1.json"), ("temarios/uco-administrativa/uco-2.json"), ("temarios/uca-auxiliar-administrativa/ucaaux-2.json"),
             ("temarios/uca-tecnico-especialista-de-servicios-tecnicos-de-pi/ucaobr-1.json"), ("temarios/ugr-auxiliar-servicios-generales-discapacidad/ugrasg-2.json"),
             ("temarios/unia-auxiliar-administrativa/uniaaux-3.json"), ("temarios/uja-laboral-prl/ujaprl-1.json")]
    mas = [("temarios/uco-administrativa/uco-1.json", .3), ("temarios/ugr-auxiliar-servicios-generales-discapacidad/ugrasg-1.json", .6), ("temarios/uca-auxiliar-administrativa/ucaaux-1.json", .4),
           ("temarios/ual-auxiliar-administrativa/ual-2.json", .5), ("temarios/upo-administrativa/upoadm-3.json", .5), ("temarios/uhu-ayudantes-archivos-bibliotecas/uhuaab-1.json", .5),
           ("temarios/ugr-apoyo-docencia-bellas-artes/ugrbba-2.json", .5), ("temarios/uco-laboral-stoem/ucolab-1.json", .5), ("temarios/uja-laboral-prl/ujaprl-2.json", .4),
           ("temarios/uca-tecnico-especialista-de-servicios-tecnicos-de-pi/ucaobr-2.json", .3), ("temarios/unia-auxiliar-administrativa/uniaaux-1.json", .5),
           ("temarios/ual-auxiliar-administrativa/ual-1.json", .2), ("temarios/uco-administrativa/uco-2.json", .7), ("temarios/uca-tecnico-especialista-de-servicios-tecnicos-de-pi/ucaobr-1.json", .8),
           ("temarios/ugr-auxiliar-servicios-generales-discapacidad/ugrasg-2.json", .75), ("temarios/uja-laboral-prl/ujaprl-1.json", .85)]
    for f in extra:
        t = json.load(open(os.path.join(RAIZ, f), encoding="utf8"))
        buenas = [p for p in t["preguntas"] if len(p["q"]) <= 210 and all(len(o) <= 95 for o in p["o"]) and len(p["e"]) <= 330 and len(p["ref"][2]) <= 330]
        if buenas:
            sel.append((t, buenas[len(buenas) // 2]))
    usadas = {p["q"] for _, p in sel}
    for f, frac in mas:
        t = json.load(open(os.path.join(RAIZ, f), encoding="utf8"))
        buenas = [p for p in t["preguntas"] if len(p["q"]) <= 210 and all(len(o) <= 95 for o in p["o"]) and len(p["e"]) <= 330 and len(p["ref"][2]) <= 330 and p["q"] not in usadas]
        if buenas:
            p = buenas[int(len(buenas) * frac) % len(buenas)]
            usadas.add(p["q"])
            sel.append((t, p))
    return sel[:30]


def etiqueta_ley(k):
    sys.path.insert(0, RAIZ)
    import importlib.util
    if not hasattr(etiqueta_ley, "L"):
        spec = importlib.util.spec_from_file_location("build_ruta", os.path.join(RAIZ, "build.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        etiqueta_ley.L = m.LEYES
    return etiqueta_ley.L.get(k, k)


def main():
    out = os.path.join(AQUI, "test-del-dia")
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(AQUI, "perfil"), exist_ok=True)
    textos = ["# Tests del día (primera semana)\n",
              "Cada día: publica las dos imágenes como carrusel en Instagram (pregunta primero, respuesta después). En Telegram y X, el texto corto.\n",
              "Los enlaces llevan marca de origen para ver en GoatCounter qué canal funciona.\n"]
    for i, (t, p) in enumerate(preguntas(), 1):
        tema = t["titulo"].split(":")[0].split("(")[0].strip()
        tema = tema if len(tema) <= 46 else tema[:45].rsplit(" ", 1)[0] + "…"
        # --- imagen de la pregunta
        im, d = lienzo(f"Test del día · {tema}", "Desliza para ver la respuesta  ›")
        d.text((60, 200), f"TEST DEL DÍA  #{i}", font=fuente(SANS_B, 34), fill=GRANADA)
        y = bloque(d, 60, 260, p["q"], SERIF_B, 60, 960, 420, TINTA) + 30
        for k, op in enumerate(p["o"]):
            d.rounded_rectangle((60, y, 1020, y + 150), radius=22, fill="white", outline="#D5DFD8", width=3)
            d.text((90, y + 40), "ABCD"[k], font=fuente(SERIF_B, 56), fill=GRANADA)
            bloque(d, 170, y + 24, op, SANS, 38, 820, 110, TINTA)
            y += 175
        im.save(os.path.join(out, f"dia-{i}-pregunta.png"), optimize=True)
        # --- imagen de la respuesta
        im, d = lienzo(f"Test del día · {tema}", "Más tests explicados con la ley: rutaalaplaza.com")
        corr = "ABCD"[p["c"]]
        d.text((60, 200), "LA RESPUESTA", font=fuente(SANS_B, 34), fill=GRANADA)
        y = bloque(d, 60, 260, f"{corr}) {p['o'][p['c']]}", SERIF_B, 60, 960, 330, PINO) + 30
        y = bloque(d, 60, y, p["e"], SANS, 38, 960, 340, TINTA) + 30
        k, a, c = p["ref"]
        fuente_txt = etiqueta_ley(k) + ("" if a == "doc" else (", art. " + str(a) if str(a)[:1].isdigit() else ", " + str(a).capitalize().replace(" iii", " III")))
        f2, l2, i2 = ajusta(d, f"«{c}»", SERIF_B, 38, 900, 1210 - y - 190)
        fin = y + 66 + len(l2) * i2 + 80
        d.rounded_rectangle((60, y, 1020, min(fin, 1210)), radius=22, fill="white", outline="#D5DFD8", width=3)
        d.text((90, y + 22), "Lo dice la norma:", font=fuente(SANS_B, 30), fill=SUAVE)
        yy = bloque(d, 90, y + 66, f"«{c}»", SERIF_B, 38, 900, 1210 - y - 190, TINTA)
        bloque(d, 90, yy + 8, fuente_txt, SANS, 28, 900, 70, SUAVE)
        im.save(os.path.join(out, f"dia-{i}-respuesta.png"), optimize=True)
        # --- textos
        enlace = "https://rutaalaplaza.com/?utm_source={r}&utm_campaign=test-del-dia"
        opciones = " ".join(f"{'ABCD'[k]}) {o}" for k, o in enumerate(p["o"]))
        pregunta = re.sub(r"\s+", " ", p["q"])
        corto_x = f"Test del día #{i}: {pregunta}"
        if len(corto_x) > 190:
            corto_x = corto_x[:187].rsplit(" ", 1)[0] + "…"
        textos.append(f"\n## Día {i} · {tema}\n")
        textos.append(f"**Instagram (pie del carrusel):**\n\n> Test del día #{i} · {tema}. ¿Cuál es la correcta? Respóndelo en comentarios y desliza para ver la respuesta y lo que dice la norma. "
                      f"Tests que explican cada respuesta con la ley, en el enlace de la biografía. #PTGAS #oposicionesuniversidad #PASuniversidad #opositores #oposicionesandalucia\n")
        textos.append(f"**X (menos de 280 caracteres):**\n\n> {corto_x}\n> {opciones[:0]}Respuesta explicada con la ley: {enlace.format(r='x')}\n")
        textos.append(f"**Telegram o WhatsApp (canal propio):**\n\n> 📚 Test del día #{i}\n> {pregunta}\n> {opciones}\n> Respuesta explicada con la ley, mañana. Más tests: {enlace.format(r='telegram')}\n")
        print(f"día {i}: {p['q'][:70]}…")
    open(os.path.join(out, "textos.md"), "w", encoding="utf8").write("\n".join(textos))

    # --- perfil
    av = Image.new("RGB", (512, 512), PINO)
    da = ImageDraw.Draw(av)
    da.ellipse((96, 96, 416, 416), fill=GRANADA)
    da.ellipse((196, 196, 316, 316), fill=FONDO)
    av.save(os.path.join(AQUI, "perfil", "avatar-512.png"), optimize=True)
    ba = Image.new("RGB", (1500, 500), PINO)
    db = ImageDraw.Draw(ba)
    db.ellipse((90, 150, 250, 310), fill=GRANADA)
    db.text((290, 140), "Ruta a la Plaza", font=fuente(SERIF_B, 96), fill="white")
    db.text((290, 270), "Oposiciones de las universidades de Andalucía", font=fuente(SANS, 52), fill="#CFE3DB")
    db.text((290, 350), "Convocatorias · temario · tests explicados con la ley", font=fuente(SANS, 38), fill="#CFE3DB")
    ba.save(os.path.join(AQUI, "perfil", "banner-1500x500.png"), optimize=True)
    bios = {
        "Instagram (máx. 150)": "Convocatorias PTGAS de las universidades de Andalucía · Temario y tests explicados con la ley · Avisos de cambios 👇",
        "X (máx. 160)": "Convocatorias de oposiciones PTGAS (PAS) de las universidades andaluzas, con plazos, programa y avisos de cambios. Tests explicados con la ley.",
        "Telegram, descripción del canal (máx. 255)": "Convocatorias de oposiciones del personal de administración y servicios (PTGAS) de las 10 universidades públicas de Andalucía: plazos, programa y cambios oficiales. Más en rutaalaplaza.com/oposiciones/",
        "WhatsApp, descripción del canal (máx. 255)": "Aviso de cada convocatoria nueva y de cada cambio oficial (correcciones, listas, fechas de examen) de las oposiciones PTGAS de las universidades de Andalucía. Fuente: BOE y BOJA.",
    }
    md = ["# Biografías y descripciones\n", "Enlace para la biografía de cada red: `https://rutaalaplaza.com/oposiciones/?utm_source=<red>`\n",
          "Nombre de cuenta recomendado en todas: **rutaalaplaza** (si está ocupado, `rutaalaplaza_oposiciones`).\n"]
    for k, v in bios.items():
        lim = int(re.search(r"máx\. (\d+)", k).group(1))
        md.append(f"## {k}\n\n> {v}\n\n*{len(v)} caracteres{'' if len(v) <= lim else '  ⚠ SE PASA DEL LÍMITE'}*\n")
        print(f"{k}: {len(v)}/{lim}", "" if len(v) <= lim else "<<< LARGO")
    open(os.path.join(AQUI, "perfil", "biografias.md"), "w", encoding="utf8").write("\n".join(md))


if __name__ == "__main__":
    main()
