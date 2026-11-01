#!/usr/bin/env python3
"""Fichas de las convocatorias de ACCESO a los cuerpos de la Administración General de la Junta de Andalucía (BOJA).
Una misma resolución convoca varias especialidades (cada una con su programa en el Anexo II): se crea UNA ficha por especialidad.
Solo biblioteca estándar. Mismas reglas que ficha_auto: lo que no se lee con seguridad se deja como «consulta la convocatoria».

Uso de prueba (no escribe nada):  python ficha_junta.py <url del BOJA> AAAA-MM-DD
"""
import datetime as dt
import html
import json
import re
import sys

import ficha_auto as fa
import vigilar_convocatorias as v

ORGANISMO = "Junta de Andalucía"
RE_CODIGO = re.compile(r"[A-Z]\d\.\d{4}$")


def texto_completo(url):
    """Texto de la disposición sin recortar (el cuadro de plazas está al principio, que ficha_auto descarta)."""
    st, cuerpo = v.get(url)
    if st != 200:
        raise RuntimeError(f"HTTP {st} al leer {url}")
    t = cuerpo.decode("utf8", "replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"</(?:p|div|li|h\d|tr)>|<br\s*/?>", "\n", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    i = t.find("BASES DE LA CONVOCATORIA")
    return t[i:] if i > 0 else t


def titulo_es(t):
    """«ADMINISTRACIÓN DE GESTIÓN FINANCIERA» -> «Administración de Gestión Financiera»."""
    peq = {"de", "del", "la", "las", "los", "y", "e", "en", "el"}
    return " ".join(w.lower() if w.lower() in peq and i else w.capitalize() for i, w in enumerate(t.split()))


def num(s):
    s = s.strip().replace(",", ".")
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def cuadro(texto):
    """Filas del cuadro del apartado 1 de la base primera: código, especialidad, plazas (total, general, discapacidad, enf. mental),
    anexo del programa y tasa. Devuelve [] si no se lee con seguridad."""
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    ini = next((i for i, l in enumerate(lineas) if re.match(r"CUERPO .*", l) and i + 1 < len(lineas) and "TOTAL PLAZAS" in lineas[i + 1]), None)
    if ini is None:
        return []
    filas, k = [], ini
    while k < len(lineas) and not lineas[k].startswith("2."):
        if RE_CODIGO.match(lineas[k]):
            cod = lineas[k]
            esp, k = [], k + 1
            while k < len(lineas) and not re.fullmatch(r"\d+", lineas[k]):
                esp.append(lineas[k])
                k += 1
            nums = []
            while k < len(lineas) and re.fullmatch(r"\d+|-", lineas[k]) and len(nums) < 4:
                nums.append(0 if lineas[k] == "-" else int(lineas[k]))
                k += 1
            anexos = []   # primero el anexo de comisión y titulación (I.x) y después el del programa, que puede ser «II.1. y II.A» (común + propio)
            while k < len(lineas) and re.fullmatch(r"[IVX]+\.[\dA-Z]+\.?(?: y [IVX]+\.[\dA-Z]+\.?)?", lineas[k]) and len(anexos) < 2:
                anexos.append(lineas[k])
                k += 1
            tasa = num(lineas[k]) if k < len(lineas) and re.fullmatch(r"\d+[.,]\d+", lineas[k]) else None
            k += 1
            if len(nums) in (3, 4) and len(anexos) == 2:
                nums = nums + [0] * (4 - len(nums))   # sin columna de enfermedad mental
                filas.append({"codigo": cod, "especialidad": titulo_es(" ".join(esp)), "total": nums[0], "general": nums[1],
                              "discapacidad": nums[2], "enfermedad_mental": nums[3], "anexos_programa": re.findall(r"[IVX]+\.[\dA-Z]+", anexos[1]),
                              "tasa": tasa})
            continue
        k += 1
    return filas


def programa_anexo(texto, anexo):
    """Bloques de temas del subanexo (p. ej. «II.A.»), con sus encabezados en mayúsculas, o None."""
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    base = max((i for i, l in enumerate(lineas) if re.fullmatch(r"ANEXO\s+II\.?", l, re.I)), default=0)   # el cuadro de la base primera también cita «II.1. y II.A»
    ini = next((i for i in range(base, len(lineas)) if re.match(re.escape(anexo) + r"\.\s", lineas[i])), None)
    if ini is None:
        return None
    fin = next((i for i in range(ini + 1, len(lineas)) if re.match(r"II\.[A-Z0-9]\.\s", lineas[i]) or re.fullmatch(r"ANEXO\s+[IVX]+\.?", lineas[i], re.I)), len(lineas))
    bloques, grupo, bloque, tema = [], "", None, None
    for l in lineas[ini + 1: fin]:
        mg = re.fullmatch(r"GRUPO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO)", l)
        mt = re.match(r"Tema\s+(\d{1,3})\.\s*(.+)", l)
        if mg:
            grupo = mg.group(1).capitalize()
            bloque = None
        elif mt:
            if bloque is None:
                bloque = {"titulo": "Programa" + (f" · grupo {grupo.lower()}" if grupo else ""), "temas": []}
                bloques.append(bloque)
            bloque["temas"].append(mt.group(2)[:420])
        elif l.isupper() and len(l) < 150 and not l.startswith("ANEXO"):
            bloque = {"titulo": (f"Grupo {grupo.lower()} · " if grupo else "") + titulo_es(l), "temas": []}
            bloques.append(bloque)
        elif bloque is not None and bloque["temas"] and not mt:
            bloque["temas"][-1] += " " + l[:200]   # el enunciado de un tema continúa en la línea siguiente
    return [b for b in bloques if b["temas"]] or None


def ejercicios_de(texto):
    """Primeras frases de cada ejercicio de la fase de oposición, tal como las describen las bases."""
    out = []
    for nombre in ("Primer", "Segundo", "Tercer", "Cuarto"):
        m = re.search(rf"\n\s*(?:\d+\.\d+\.\s*)?{nombre} ejercicio\.\s*\n(.{{0,3000}})", texto, re.S)
        if not m:
            continue
        cuerpo = re.split(r"\n\s*(?:\d+\.\d+\.\s*)?(?:Segundo|Tercer|Cuarto) ejercicio\.", m.group(1))[0]
        frases = [f.strip() for f in re.split(r"(?<=[.])\s+", re.sub(r"\s+", " ", cuerpo).strip()) if f.strip()]
        txt = " ".join(frases[:3])
        if len(txt) > 420:
            txt = txt[:420].rsplit(" ", 1)[0] + "…"
        out.append(f"{nombre} ejercicio. {txt}")
    return out


def crear(c, existentes):
    """Lista de fichas (una por especialidad) de la convocatoria `c` de acceso a un cuerpo de la Junta; lanza excepción si no es fiable."""
    if re.search(r"diferentes cuerpos|distintos cuerpos|cuerpos generales|cuerpos especiales", c["titulo"], re.I):
        raise ValueError("la resolución convoca varios cuerpos a la vez: revisa la convocatoria y crea las fichas a mano")
    texto = texto_completo(c["url"])
    filas = cuadro(texto)
    if not filas:
        raise ValueError("no se pudo leer el cuadro de especialidades y plazas")
    m = re.search(r"(?:Cuerpo|CUERPO)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]+?)\s*(?:,|\.|\s+en el [aá]mbito)", c["titulo"])
    cuerpo = re.sub(r"\s+", " ", m.group(1)).strip() if m else "Cuerpo de la Administración General"
    cuerpo = cuerpo if cuerpo.lower().startswith("cuerpo") else "Cuerpo " + cuerpo
    cuerpo = re.sub(r"^(?:Cuerpo)\s+", "Cuerpo ", cuerpo)
    acceso = "libre" if "acceso libre" in v.norm(c["titulo"]) else ("promocion interna" if "promocion interna" in v.norm(c["titulo"]) else "")
    pi = acceso == "promocion interna"
    pub = c["fecha"]
    plazo = None
    for x in re.finditer(r"plazo de presentaci[oó]n de solicitudes ser[aá] de (\S+) d[ií]as (h[aá]biles|naturales)", texto):
        n = fa.numero(x.group(1))
        if n:
            plazo = (n, x.group(2).startswith("h"))
            break
    ids = {o["id"] for o in existentes}
    ejercicios = ejercicios_de(texto)
    fichas = []
    for f in filas:
        esp = f["especialidad"]
        id_ = "junta-" + re.sub(r"[^a-z0-9]+", "-", v.norm(cuerpo.replace("Cuerpo ", "") + " " + esp)).strip("-")[:72] + ("-pi" if pi else "")
        if id_ in ids:
            id_ = f"{id_}-{pub}"
        corto_esp = re.sub(r"^Administraci[oó]n de ", "", esp)   # para la dirección web: «gestion-financiera» y no «administracion-de-gestion-financiera»
        slug_url = v.norm(cuerpo.replace("Cuerpo ", "") + " " + corto_esp)
        slug_url = re.sub(r"[^a-z0-9]+", "-", slug_url).strip("-") + ("-pi" if pi else "")
        extra = []
        if f["discapacidad"]:
            extra.append(f"{f['discapacidad']} para personas con discapacidad")
        if f["enfermedad_mental"]:
            extra.append(f"{f['enfermedad_mental']} para personas con enfermedad mental")
        plazas = f"{f['total']} plazas" + (f" (turno general: {f['general']}; " + "; ".join(extra) + ")" if extra else "")
        ficha = {"id": id_, "nombre": f"{cuerpo}, especialidad {esp} ({f['codigo']})", "organismo": ORGANISMO, "ambito": "Andalucía",
                 "estado": "preparacion", "tipo": "Personal funcionario",
                 "turno": "Promoción interna" if pi else "Libre", "grupo": "A1" if f["codigo"].startswith("A1") else f["codigo"][:2],
                 "plazas": plazas, "convocatoria": f"BOJA del {fa.fecha_larga_es(pub)}", "publicado": pub,
                 "examen": fa.examen_de(texto), "enlace": {"t": "Convocatoria en el BOJA", "u": c["url"]},
                 "claves": [v.norm(cuerpo), "especialidad " + v.norm(esp)], "slug": slug_url, "auto": True}
        if f["tasa"]:
            ficha["tasa"] = f"{float(f['tasa']):.2f}".replace(".", ",") + " €"
        if plazo:
            n, habiles = plazo
            fin = fa.dias_habiles_despues(dt.date.fromisoformat(pub), n) if habiles else dt.date.fromisoformat(pub) + dt.timedelta(days=n)
            ficha["plazoFin"] = fin.isoformat()
            ficha["plazoNota"] = (f"{n} días {'hábiles' if habiles else 'naturales'} desde el día siguiente a la publicación en el BOJA; "
                                  f"la fecha de cierre es aproximada (no se descuentan festivos locales). Ficha creada automáticamente a partir del texto oficial: comprueba los datos en la convocatoria.")
        else:
            ficha["plazoFin"] = fa.dias_habiles_despues(dt.date.fromisoformat(pub), 20).isoformat()
            ficha["plazoNota"] = "No se ha podido leer el plazo en la convocatoria: la fecha de cierre es una estimación. Consulta la convocatoria."
        bloques, usados = [], []
        for ax in f["anexos_programa"]:   # puede haber un anexo común (II.1) y otro propio de la especialidad (II.A)
            b = programa_anexo(texto, ax)
            if b:
                if len(f["anexos_programa"]) > 1:   # sin encabezados propios: se distingue la parte común de la específica
                    for blk in b:
                        if blk["titulo"].startswith("Programa"):
                            blk["titulo"] = blk["titulo"].replace("Programa", "Parte común a todas las especialidades" if ax.endswith(".1") else "Parte específica de la especialidad", 1)
                bloques += b
                usados.append(ax)
        if bloques:
            n_t = sum(len(b["temas"]) for b in bloques)
            ficha["programa"] = {"nota": f"Programa del Anexo {' y '.join(usados)} de la convocatoria ({n_t} temas), extraído automáticamente del texto oficial: consulta el anexo para ver el enunciado completo.",
                                 "bloques": bloques,
                                 "ejercicios": ejercicios or ["Consulta los ejercicios y su valoración en las bases de la convocatoria."]}
        fichas.append(ficha)
        ids.add(id_)
    return fichas


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    url, fecha = sys.argv[1], sys.argv[2]
    c = {"url": url, "fuente": "BOJA", "fecha": fecha, "titulo": input("Título: ")}
    for f in crear(c, []):
        p = f.pop("programa", None)
        print(json.dumps(f, ensure_ascii=False, indent=1))
        if p:
            print("PROGRAMA:", p["nota"], [(b["titulo"], len(b["temas"])) for b in p["bloques"]], p["ejercicios"][:2])
