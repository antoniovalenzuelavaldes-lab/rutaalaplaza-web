#!/usr/bin/env python3
"""Crea sola la ficha de una convocatoria NUEVA a partir del texto oficial (BOJA o BOE), para que el proceso diario la publique
sin que nadie tenga que confirmarla. Solo usa la biblioteca estándar.

Cada dato se extrae del texto con reglas prudentes: si no se puede leer con seguridad, se deja un texto neutro («consulta la
convocatoria») en vez de inventar. Toda ficha creada así lleva `"auto": true` y una nota visible que lo dice; si alguien la
revisa y la mejora a mano, basta con quitar `auto` (o moverla a oposiciones.json).

Uso de prueba (no escribe nada):  python ficha_auto.py <url de la convocatoria> [AAAA-MM-DD fecha de publicación]
"""
import datetime as dt
import html
import json
import re
import sys

import vigilar_convocatorias as v

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
SIGLAS = {"almería": "ual", "cádiz": "uca", "córdoba": "uco", "granada": "ugr", "huelva": "uhu", "jaén": "uja", "málaga": "uma",
          "pablo de olavide": "upo", "sevilla": "us", "internacional de andalucía": "unia"}
# Festivos que caen entre semana y son comunes a toda Andalucía (el cierre es siempre aproximado y la ficha lo dice)
FESTIVOS_FIJOS = {(1, 1), (1, 6), (2, 28), (5, 1), (8, 15), (10, 12), (11, 1), (12, 6), (12, 8), (12, 25)}

_UN = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
       "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
       "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
       "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30,
       "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100}


def numero(t):
    """«cinco», «5», «treinta y dos», «veinte (20)» -> int, o None."""
    t = v.norm(t).strip()
    m = re.match(r"(\d+)\b", t)
    if m:
        return int(m.group(1))
    m = re.match(r"([a-z]+)(?: y ([a-z]+))?\b", t)
    if m and m.group(1) in _UN:
        return _UN[m.group(1)] + (_UN.get(m.group(2), 0) if m.group(2) else 0)
    return None


def fecha_larga_es(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def dias_habiles_despues(inicio, n):
    """Fecha del día hábil número n contando desde el día siguiente a `inicio` (sin sábados, domingos ni festivos comunes)."""
    d = inicio
    while n > 0:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and (d.month, d.day) not in FESTIVOS_FIJOS:
            n -= 1
    return d


# ---------------------------------------------------------------- texto oficial
def texto_oficial(c):
    st, cuerpo = v.get(c["url"])
    if st != 200:
        raise RuntimeError(f"HTTP {st} al leer {c['url']}")
    t = cuerpo.decode("utf8", "replace")
    if c["fuente"] == "BOE":
        m = re.search(r'<div id="textoxslt"[^>]*>(.*)', t, re.S)
        t = m.group(1) if m else t
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"</(?:p|div|li|h\d|tr)>|<br\s*/?>", "\n", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    for marca in ("En uso de las atribuciones", "RESUELVO", "Resuelvo", "De conformidad con"):   # salta el menú de la página
        i = t.find(marca)
        if i > 0 and c["fuente"] == "BOJA":
            return t[max(0, i - 200):]
    return t


# ---------------------------------------------------------------- campos
def nombre_de(titulo):
    m = re.search(r"\b((?:Escala|Cuerpo)\s+.+?)\s+(?:de la|del)\s+Universidad", titulo)
    if m:
        return m.group(1).strip(" ,.")
    m = re.search(r"\b(?:categor[ií]a|especialidad)\s+(?:profesional\s+)?(?:de\s+)?(.+?)\s+(?:de la|del)\s+Universidad", titulo, re.I)
    if m:
        n = m.group(1).strip(" ,.")
        return n[0].upper() + n[1:]
    return None


def datos_de(c, texto):
    t = c["titulo"]
    nt = v.norm(t)
    head = texto[:6000]
    organismo = v.uni_de(t)
    nombre = nombre_de(t)
    if not nombre:
        raise ValueError("no se pudo leer el nombre de la escala o categoría en el título")
    laboral = bool(re.search(r"\blaboral|categor[ií]a profesional|convenio colectivo", t + " " + head[:2500], re.I)) and not re.search(r"\bEscala\b|\bCuerpo\b", t)
    pi = "promocion interna" in nt
    turno = []
    if pi:
        turno.append("Promoción interna")
    if not pi:
        turno.append("Libre")
    if "discapacidad" in nt:
        turno.append("con reserva para personas con discapacidad")
    n_plazas = None
    for m in re.finditer(r"\b(\d+|[a-záéíóúñ]+(?: y [a-záéíóúñ]+)?)(?: \(\d+\))?\s+plazas?\b", head, re.I):
        n_plazas = numero(m.group(1))
        if n_plazas:
            break
    plazas = (f"{n_plazas} plaza" + ("s" if n_plazas != 1 else "")) if n_plazas else "Consulta el número de plazas en la convocatoria"
    mg = re.search(r"[Ss]ubgrupo\s+([ABC][12]?)\b|\bGrupo\s+(I{1,3}V?|IV|V|[ABC][12]?)\b", head)
    grupo = (mg.group(1) or mg.group(2)) if mg else ""
    return {"organismo": organismo, "nombre": nombre, "tipo": "Personal laboral" if laboral else "Personal funcionario",
            "turno": " ".join(turno) if turno else "Consulta la convocatoria", "grupo": grupo, "plazas": plazas, "promo": pi}


def plazo_de(c, texto):
    """(plazoFin | None, plazoPorAbrir, nota). El plazo cuenta desde el día siguiente a la publicación en el boletín que diga la convocatoria."""
    pub = dt.date.fromisoformat(c["fecha"])
    m = None
    for x in re.finditer(r"(?:plazo de (?:los )?|ser[aá] de |es de )(\d+|[a-záéíóúñ]+(?: y [a-záéíóúñ]+)?(?: \(\d+\))?)\s+d[ií]as\s+(h[aá]biles|naturales)", texto, re.I):
        antes = texto[max(0, x.start() - 220): x.start()]
        if re.search(r"solicitud|instancia", antes, re.I) and not re.search(r"subsan|excluid|reclamaci|alegaci", antes[-60:], re.I):
            m = x
            break
    n = numero(m.group(1)) if m else None
    if not n:
        fin = dias_habiles_despues(pub, 20)
        return fin.isoformat(), False, "No se ha podido leer el plazo en el texto de la convocatoria: la fecha de cierre es una estimación (20 días hábiles). Consulta la convocatoria."
    habiles = m.group(2).lower().startswith("h")
    seg = texto[m.start(): m.start() + 400]
    en_boe = re.search(r"Bolet[ií]n Oficial del Estado", seg) and not re.search(r"Junta de Andaluc[ií]a|BOJA", seg)
    if en_boe and c["fuente"] == "BOJA":
        return None, True, f"El plazo ({n} días {'hábiles' if habiles else 'naturales'}) empieza al publicarse el extracto en el BOE."
    fin = dias_habiles_despues(pub, n) if habiles else pub + dt.timedelta(days=n)
    return fin.isoformat(), False, f"{n.__str__()} días {'hábiles' if habiles else 'naturales'} desde el día siguiente a la publicación en el {c['fuente']}; la fecha de cierre es aproximada."


def examen_de(texto):
    m = re.search(r"primer ejercicio[^.]{0,200}?(?:no antes del|a partir del|se celebrar[aá] el)\s+(\d{1,2}) de ([a-z]+) de (\d{4})", texto, re.I)
    if m and m.group(2).lower() in MESES:
        return f"Primer ejercicio: no antes del {int(m.group(1))} de {m.group(2).lower()} de {m.group(3)}"
    return "Fecha del primer ejercicio por publicar (se anunciará con la lista de personas admitidas)"


def programa_de(texto):
    """Temas del anexo de programa y descripción de los ejercicios del anexo de ejercicios, si se leen con claridad."""
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    anexos = [i for i, l in enumerate(lineas) if re.fullmatch(r"ANEXO\s+(?:[IVX]+|\d+|[ÚU]NICO)\.?", l, re.I)]
    temas_b, ejercicios = [], []
    for k, i in enumerate(anexos):
        fin = anexos[k + 1] if k + 1 < len(anexos) else len(lineas)
        cuerpo = lineas[i + 1: fin]
        cab = " ".join(cuerpo[:3]).lower()
        if re.search(r"programa|temario|materias", cab) and not temas_b:
            bloque = None
            for l in cuerpo:
                if re.match(r"(?:BLOQUE|PARTE|GRUPO|MATERIAS?|M[ÓO]DULO)\b", l, re.I) and len(l) < 160:
                    bloque = {"titulo": l.strip(" .:").title() if l.isupper() else l.strip(" .:"), "temas": []}
                    temas_b.append(bloque)
                elif re.match(r"\d{1,3}\s*[.\-)]\s+\S", l):
                    if bloque is None:
                        bloque = {"titulo": "Programa", "temas": []}
                        temas_b.append(bloque)
                    bloque["temas"].append(re.sub(r"^\d{1,3}\s*[.\-)]\s+", "", l)[:420])
        elif re.search(r"ejercicios|valoraci[oó]n|fase de oposici", cab) and not ejercicios:
            for l in cuerpo:
                if re.match(r"(?:Primer|Segundo|Tercer|Cuarto|[ÚU]nico) ejercicio", l, re.I):
                    if len(l) > 330:
                        corte = max(l.rfind(". ", 0, 330), -1)
                        l = l[: corte + 1] if corte > 120 else l[:330].rsplit(" ", 1)[0] + "…"
                    ejercicios.append(l.strip())
    temas_b = [b for b in temas_b if b["temas"]]
    n = sum(len(b["temas"]) for b in temas_b)
    if n < 5:
        return None
    return {"nota": f"Programa del anexo de la convocatoria ({n} temas), extraído automáticamente del texto oficial: consulta el anexo para ver el enunciado completo.",
            "bloques": temas_b,
            "ejercicios": ejercicios[:4] or ["Consulta los ejercicios y su valoración en el anexo correspondiente de la convocatoria."]}


def crear(c, existentes):
    """Devuelve la ficha (dict) de la convocatoria `c` (de vigilar_convocatorias) o lanza una excepción si no es fiable."""
    texto = texto_oficial(c)
    d = datos_de(c, texto)
    fin, por_abrir, nota = plazo_de(c, texto)
    clave_uni = v.norm(d["organismo"].replace("Universidad de ", "").replace("Universidad ", ""))
    sigla = next((s for k, s in SIGLAS.items() if v.norm(k) in clave_uni or clave_uni in v.norm(k)), "u")
    base = sigla + "-" + re.sub(r"[^a-z0-9]+", "-", v.norm(d["nombre"])).strip("-")[:48].rsplit("-", 1)[0] + ("-pi" if d["promo"] else "")
    ids = {o["id"] for o in existentes}
    id_ = base if base not in ids else f"{base}-{c['fecha']}"
    fecha = c["fecha"]
    fuente_txt = "BOJA" if c["fuente"] == "BOJA" else "BOE"
    ficha = {"id": id_, "nombre": d["nombre"], "organismo": d["organismo"], "ambito": "Andalucía", "estado": "preparacion",
             "tipo": d["tipo"], "turno": d["turno"], "grupo": d["grupo"], "plazas": d["plazas"],
             "convocatoria": f"{fuente_txt} del {fecha_larga_es(fecha)}", "publicado": fecha,
             "examen": examen_de(texto),
             "enlace": {"t": f"Convocatoria en el {fuente_txt}", "u": c["url"]},
             "claves": [v.norm(d["nombre"])],
             "auto": True}
    if por_abrir:
        ficha["plazoPorAbrir"] = True
    else:
        ficha["plazoFin"] = fin
    ficha["plazoNota"] = (nota + f" Ficha creada automáticamente el {fecha_larga_es(dt.date.today().isoformat())} a partir del texto oficial: "
                          "comprueba los datos en la convocatoria.")
    prog = programa_de(texto)
    if prog:
        ficha["programa"] = prog
    return ficha


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    url = sys.argv[1]
    fecha = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat()
    c = {"url": url, "fuente": "BOE" if "boe.es" in url else "BOJA", "fecha": fecha, "id": "prueba", "titulo": input("Título: ")}
    f = crear(c, [])
    p = f.pop("programa", None)
    print(json.dumps(f, ensure_ascii=False, indent=1))
    if p:
        print("PROGRAMA:", p["nota"], "|", [(b["titulo"], len(b["temas"])) for b in p["bloques"]], "|", p["ejercicios"])
