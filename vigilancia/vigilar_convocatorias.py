#!/usr/bin/env python3
"""Vigila el BOE y el BOJA: convocatorias NUEVAS y CAMBIOS en las que seguimos, del personal de administración y servicios
(PAS) de las 10 universidades públicas andaluzas. Avisa a quien se haya suscrito a cada oposición.

- BOE: API de datos abiertos del sumario diario (sección «Universidades», epígrafe de personal técnico, de gestión
  y de administración y servicios).
- BOJA: página «Oposiciones, concursos y otras convocatorias» de cada boletín.
- Solo usa la biblioteca estándar de Python y no necesita claves para vigilar. Para ENVIAR avisos hacen falta tres variables
  de entorno (en GitHub, como «secrets»): SUPABASE_URL, SUPABASE_SERVICE_KEY y BREVO_API_KEY.

Qué hace con cada publicación de una universidad andaluza (no docente):
  - es una convocatoria que no conocemos            -> «nueva»: se avisa al titular para que la verifique y la añada.
  - es una corrección, lista de admitidos, fecha de examen, tribunal, resultados… de una convocatoria que SÍ seguimos
                                                    -> «cambio»: se avisa a los suscritos a esa oposición.
  - cualquier otra cosa                             -> se ignora.

Uso:
  python vigilar_convocatorias.py --opos docs/oposiciones.json --estado vigilancia/estado.json
  ... --issue --asignar USUARIO      abre un aviso en GitHub (gh) con lo encontrado
  ... --avisar                       envía los correos a los suscritos (sin esta opción solo cuenta a quién se enviaría)
  ... --auto docs/oposiciones-auto.json   crea SOLA la ficha de cada convocatoria nueva (ficha_auto.py) y la guarda en ese fichero;
                                     el listado público y las páginas la recogen sin que nadie la confirme. Lo que no se pueda
                                     leer con fiabilidad queda en el aviso para revisarlo a mano.
  python vigilar_convocatorias.py --opos docs/oposiciones.json --sin-estado --desde 2026-10-01   # prueba, no guarda nada
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; RutaALaPlaza-vigilante/1.0; +https://rutaalaplaza.com)"
WEB = os.environ.get("URL_WEB", "https://rutaalaplaza.com")
UNIVERSIDADES = ["Almería", "Cádiz", "Córdoba", "Granada", "Huelva", "Jaén", "Málaga", "Pablo de Olavide", "Sevilla",
                 "Internacional de Andalucía"]
RE_UNI = re.compile(r"Universidad (?:de |Internacional de |Pablo de )?(?:%s)" % "|".join(UNIVERSIDADES), re.I)
RE_CONVOCA = re.compile(r"\bconvoca(?:n|toria)?\b|publica la convocatoria", re.I)
RE_PROCESO = re.compile(r"proceso selectivo|pruebas selectivas|concurso-oposici|concurso de m[eé]ritos|bolsa de trabajo", re.I)
RE_CORRECCION = re.compile(r"correcci[oó]n de errores|se corrigen errores", re.I)
# Publicaciones que NO son del PAS: profesorado, becas, contratos de investigación…
RE_NO_PAS = re.compile(r"cuerpos docentes|profesor|personal docente|investigador|\bbeca|contrato predoctoral|formaci[oó]n de doctores|"
                       r"proyecto de investigaci[oó]n|con cargo al proyecto|contrataci[oó]n temporal|concurso de acceso|plazas de (?:catedr|titular)", re.I)


def get(url, accept=None, intentos=3):
    cab = {"User-Agent": UA}
    if accept:
        cab["Accept"] = accept
    err = None
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=40) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return e.code, b""
            err = e
        except Exception as e:  # red caída, tiempo agotado…
            err = e
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"No se pudo leer {url}: {err}")


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def es_pas(titulo):
    return bool(RE_UNI.search(titulo)) and not RE_NO_PAS.search(titulo)


def es_convocatoria(titulo):
    return es_pas(titulo) and not RE_CORRECCION.search(titulo) and bool(RE_CONVOCA.search(titulo) and RE_PROCESO.search(titulo))


# Junta de Andalucía (Administración General): acceso a sus cuerpos, convocado por la Dirección General de Recursos Humanos y Función Pública
RE_JUNTA = re.compile(r"Direcci[oó]n General de Recursos Humanos y Funci[oó]n P[uú]blica|Instituto Andaluz de Administraci[oó]n P[uú]blica", re.I)
RE_JUNTA_CUERPO = re.compile(r"\bcuerpos?\b|procesos? selectivos?|pruebas selectivas", re.I)


def es_junta(titulo):
    """Publicaciones de la Junta sobre procesos selectivos de sus cuerpos (convocatorias, listas, tribunales, resultados…)."""
    return bool(RE_JUNTA.search(titulo) and RE_JUNTA_CUERPO.search(titulo)) and not RE_NO_PAS.search(titulo)


# Servicio Andaluz de Salud: concurso-oposición de las categorías administrativas y de servicios que cubrimos (Auxiliar Administrativo/a, Administrativo/a, Celador/a)
RE_SAS_CAT = re.compile(r"Auxiliar Administrativ|Administrativo/a|Celador", re.I)


def es_sas(titulo):
    """Publicaciones del SAS sobre sus procesos selectivos de esas categorías (convocatoria, listas, resultados…); no los concursos de traslado ni de méritos."""
    return ("Servicio Andaluz de Salud" in titulo and bool(RE_SAS_CAT.search(titulo))
            and bool(re.search(r"concurso-oposici|pruebas selectivas|proceso selectivo|personas aspirantes", titulo, re.I))
            and not re.search(r"concurso de traslado|concurso de m[eé]ritos|libre designaci|cargo intermedio|bolsa", titulo, re.I))


def es_convocatoria_sas(titulo):
    """Convocatoria de concurso-oposición de plazas básicas del SAS (no correcciones ni la reservada a personas con discapacidad intelectual)."""
    return (es_sas(titulo) and bool(re.search(r"por la que se convoca concurso-oposici", titulo, re.I)) and "plazas b" in norm(titulo)
            and not RE_CORRECCION.search(titulo) and "discapacidad intelectual" not in norm(titulo))


def es_convocatoria_junta(titulo):
    """Convocatoria de ACCESO (libre o promoción interna) a cuerpos de la Administración General. Las de personal laboral (categorías
    profesionales, concursos) no se crean solas: salen en el informe para revisarlas."""
    return (es_junta(titulo) and not RE_CORRECCION.search(titulo) and bool(re.search(r"por la que se convocan?\b", titulo, re.I))
            and bool(re.search(r"acceso libre|promoci[oó]n interna", titulo, re.I)) and bool(re.search(r"\bcuerpos?\b", titulo, re.I))
            and not re.search(r"laboral|categor[ií]as? profesional|bolsa", titulo, re.I))


# ---------------------------------------------------------------- clasificación de cambios
TIPOS = [   # (clave, patrón, texto para el suscriptor)
    ("correccion", RE_CORRECCION, "Se ha publicado una corrección de errores de la convocatoria."),
    ("lista_provisional", re.compile(r"(?:relaci[oó]n|lista) provisional", re.I), "Lista provisional de personas admitidas y excluidas."),
    ("lista_definitiva", re.compile(r"(?:relaci[oó]n|lista) definitiva", re.I), "Lista definitiva de personas admitidas y excluidas."),
    ("fecha_examen", re.compile(r"fecha, hora y lugar|se anuncia|se hace p[uú]blic[ao] la fecha|calendario", re.I), "Fecha, hora y lugar de un ejercicio."),
    ("tribunal", re.compile(r"tribunal", re.I), "Cambios en el tribunal calificador."),
    ("modificacion", re.compile(r"ampl[ií]a|pr[oó]rroga|modifica|modificaci[oó]n", re.I), "Modificación de la convocatoria (puede afectar a plazos o bases)."),
    ("anulacion", re.compile(r"desiert|anula|deja sin efecto|desisti", re.I), "Anulación o resolución desierta del proceso."),
    ("resultados", re.compile(r"calificaci|resultado|aprobad|puntuaci|plantilla|superado", re.I), "Resultados o calificaciones."),
    ("nombramiento", re.compile(r"se nombra personal funcionario|se nombran? funcionari|toma de posesi", re.I), "Nombramiento de las personas que han superado el proceso."),
]


def tipo_cambio(titulo):
    """Una publicación puede traer varios cambios a la vez (lista de admitidos + tribunal + fecha del examen): se dicen todos."""
    hallados = [(c, t) for c, rx, t in TIPOS if rx.search(titulo)]
    if not hallados:
        return "novedad", "Nueva publicación oficial sobre la convocatoria."
    return hallados[0][0], " ".join(t for _, t in hallados)


def procesos_de(titulo, opos):
    """Procesos conocidos a los que corresponde una publicación: misma universidad y todas sus palabras clave; si varios
    coinciden, los de claves más largas (más específicos)."""
    nt = norm(titulo)
    cand = []
    for o in opos:
        if norm(o["organismo"]) not in nt and not (o["organismo"] == "Junta de Andalucía" and es_junta(titulo)):   # los títulos del IAAP no nombran a la Junta
            continue
        claves = [norm(c) for c in o.get("claves", [])]
        if claves and all(c in nt for c in claves):
            cand.append((sum(len(c) for c in claves), o))
    if not cand:
        return []
    mejor = max(p for p, _ in cand)
    return [o for p, o in cand if p == mejor]


# ---------------------------------------------------------------- BOE
def boe_dia(dia):
    st, cuerpo = get("https://www.boe.es/datosabiertos/api/boe/sumario/" + dia.strftime("%Y%m%d"), "application/json")
    if st != 200 or not cuerpo:
        return []
    d = json.loads(cuerpo.decode("utf8"))["data"]["sumario"]["diario"]
    d = d[0] if isinstance(d, list) else d
    lista = lambda x: x if isinstance(x, list) else ([x] if x else [])
    out = []
    for sec in lista(d.get("seccion")):
        if sec.get("codigo") not in ("2B", "2A"):
            continue
        for dep in lista(sec.get("departamento")):
            if "UNIVERSIDADES" not in dep.get("nombre", "").upper():
                continue
            for ep in lista(dep.get("epigrafe")):
                if not re.search(r"administraci[oó]n y servicios", ep.get("nombre", ""), re.I):
                    continue
                for it in lista(ep.get("item")):
                    t = re.sub(r"\s+", " ", it.get("titulo", ""))
                    if es_pas(t):
                        out.append({"id": it["identificador"], "fuente": "BOE", "fecha": dia.isoformat(), "titulo": t,
                                    "url": "https://www.boe.es/diario_boe/txt.php?id=" + it["identificador"]})
    return out


# ---------------------------------------------------------------- BOJA
def boja_boletin(anio, n):
    """Devuelve (existe, fecha, publicaciones del PAS) del boletín n del año."""
    st, cuerpo = get(f"https://www.juntadeandalucia.es/boja/{anio}/{n}/s53")
    if st != 200:
        return False, None, []
    t = cuerpo.decode("utf8", "replace")
    f = re.search(r"BOJA n[ºo°] \d+ de (\d{2})/(\d{2})/(\d{4})", t)
    fecha = f"{f.group(3)}-{f.group(2)}-{f.group(1)}" if f else None
    out = []
    for m in re.finditer(r'<div class="item[^"]*">\s*<p>(.*?)</p>.*?href="(/boja/\d{4}/\d+/\d+)"', t, re.S):
        titulo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()
        if es_pas(titulo) or es_junta(titulo) or es_sas(titulo):
            out.append({"id": "BOJA " + m.group(2)[len("/boja/"):], "fuente": "BOJA", "fecha": fecha, "titulo": titulo,
                        "url": "https://www.juntadeandalucia.es" + m.group(2)})
    return True, fecha, out


# ---------------------------------------------------------------- estado
def cargar(ruta):
    if ruta and os.path.exists(ruta):
        return json.load(open(ruta, encoding="utf8"))
    return {}


def conocidos_de(opos):
    ids = set()
    for o in opos:
        u = o.get("enlace", {}).get("u", "")
        m = re.search(r"id=(BOE-[A-Z]-\d{4}-\d+)", u)
        if m:
            ids.add(m.group(1))
        m = re.search(r"/boja/(\d{4})/(\d+)/(\d+)", u)
        if m:
            ids.add("BOJA %s/%s/%s" % m.groups())
    return ids


def uni_de(titulo):
    m = RE_UNI.search(titulo)
    return m.group(0) if m else "?"


# ---------------------------------------------------------------- avisos a suscritos
def suscritos(op_id):
    url = os.environ.get("SUPABASE_URL", "")
    clave = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not clave:
        return None
    q = f"{url}/rest/v1/suscripciones?oposicion=eq.{urllib.parse.quote(op_id)}&activa=eq.true&confirmada=eq.true&select=email,token"
    req = urllib.request.Request(q, headers={"apikey": clave, "Authorization": "Bearer " + clave})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf8"))


def enviar_correo(para, asunto, cuerpo_html):
    clave = os.environ.get("BREVO_API_KEY", "")
    if not clave:
        raise RuntimeError("falta BREVO_API_KEY")
    datos = json.dumps({"sender": {"name": "Ruta a la Plaza", "email": "contacto@rutaalaplaza.com"}, "to": [{"email": para}],
                        "subject": asunto, "htmlContent": cuerpo_html}).encode("utf8")
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=datos, method="POST",
                                 headers={"api-key": clave, "Content-Type": "application/json", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.status in (200, 201)


def correo_cambio(o, ev, token):
    esc = html.escape
    baja = f"{WEB}/#/baja/{token}"
    return (f"<p>Hola:</p><p>Hay una novedad oficial sobre una convocatoria que sigues: <b>{esc(o['nombre'])}</b> ({esc(o['organismo'])}).</p>"
            f"<p><b>{esc(ev['texto'])}</b></p><p style=\"color:#444\">{esc(ev['titulo'])}</p>"
            f"<p><a href=\"{esc(ev['url'])}\">Ver la publicación oficial ({ev['fuente']} del {esc(ev['fecha'] or '')})</a></p>"
            f"<p>Este aviso es informativo y se genera a partir de la publicación oficial: consulta siempre el texto completo.</p>"
            f"<p style=\"color:#666;font-size:.9em\">Recibes este correo porque te suscribiste a los avisos de esta oposición en Ruta a la Plaza. "
            f"<a href=\"{esc(baja)}\">Darme de baja</a> · contacto@rutaalaplaza.com</p>")


def procesar_cambios(eventos, avisar):
    """Para cada cambio, cuenta (y si se pide, avisa a) los suscritos. Devuelve filas de informe y los eventos pendientes."""
    filas, pendientes = [], set()
    for ev in eventos:
        for o in ev["procesos"]:
            try:
                subs = suscritos(o["id"])
            except Exception as e:
                filas.append((ev, o, f"no se pudo consultar los suscritos ({e})"))
                pendientes.add(ev["id"])
                continue
            if subs is None:
                filas.append((ev, o, "suscritos: sin credenciales de Supabase (no se cuentan)"))
                continue
            if not subs:
                filas.append((ev, o, "0 suscritos"))
                continue
            if not avisar:
                filas.append((ev, o, f"{len(subs)} suscritos (no se envía: falta activar el envío automático)"))
                pendientes.add(ev["id"])   # se reintentará cuando se active el envío
                continue
            ok = ko = 0
            for s in subs:
                try:
                    enviar_correo(s["email"], f"Novedad en la convocatoria: {o['nombre']}", correo_cambio(o, ev, s["token"]))
                    ok += 1
                except Exception as e:
                    ko += 1
                    print(f"  ! fallo enviando a un suscrito de {o['id']}: {e}", file=sys.stderr)
                time.sleep(0.2)
            filas.append((ev, o, f"enviados {ok}" + (f", fallidos {ko}" if ko else "")))
            if ko:
                pendientes.add(ev["id"])
    return filas, pendientes


def informe(nuevas, filas, creadas=()):
    l = []
    if creadas:
        l += [f"## Fichas creadas y publicadas automáticamente ({len(creadas)})", "",
              "No hace falta hacer nada: ya están en el listado y con su página. Si quieres, comprueba los datos (plazas, plazo, programa) "
              "en el enlace oficial; para corregir una, edítala en `docs/oposiciones-auto.json` o quítale `auto` y pásala a `oposiciones.json`.", ""]
        for c, f in creadas:
            l += [f"- **{f['organismo']}** · {f['nombre']} · {f['tipo']} · {f['turno']} · {f['plazas']} · plazo hasta "
                  f"{f.get('plazoFin') or 'publicación en el BOE'} · {'con programa' if f.get('programa') else 'sin programa leído'}",
                  f"  {c['url']}"]
            temas = [t for b in (f.get("programa") or {}).get("bloques", []) for t in b.get("temas", [])]
            if temas:
                l += ["  **Temario por preparar** (pídeselo a Claude: «prepara el temario de " + f["id"] + "»): los dos primeros temas abiertos y el resto de pago.",
                      f"  1. {temas[0][:160]}"] + ([f"  2. {temas[1][:160]}"] if len(temas) > 1 else []) + [f"  (programa de {len(temas)} temas)"]
            else:
                l.append("  **Temario por preparar**: no se pudo leer el programa; revisa el anexo de la convocatoria.")
        l.append("")
    if nuevas:
        l += [f"## Convocatorias nuevas ({len(nuevas)})", ""]
        for c in sorted(nuevas, key=lambda c: (c["fecha"] or "", c["id"])):
            l += [f"- **{uni_de(c['titulo'])}** · {c['fuente']} del {c['fecha']}", f"  {c['titulo']}", f"  {c['url']}"]
            if c.get("motivo"):
                l.append(f"  _No se pudo crear la ficha sola: {c['motivo']}_")
        l += ["", "Siguiente paso: abre cada enlace, comprueba escala, plazas, turno y plazo, y añádela a `oposiciones.json` "
                  "(con sus `claves`). Si sale en BOE y BOJA, es la misma: una sola ficha.", ""]
    if filas:
        l += [f"## Cambios en convocatorias que seguimos ({len(filas)})", ""]
        for ev, o, estado in filas:
            l += [f"- **{o['nombre']}** ({o['organismo']}) · {ev['texto']} · {ev['fuente']} del {ev['fecha']} · _{estado}_",
                  f"  {ev['titulo']}", f"  {ev['url']}"]
        l.append("")
    return "\n".join(l) if l else "Sin novedades."


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--opos", required=True, help="oposiciones.json (el listado público, con sus `claves`)")
    ap.add_argument("--estado", help="fichero JSON con lo ya visto")
    ap.add_argument("--sin-estado", action="store_true", help="prueba: no lee ni guarda estado")
    ap.add_argument("--desde", help="AAAA-MM-DD (por defecto, el último día revisado)")
    ap.add_argument("--hasta", help="AAAA-MM-DD (por defecto, hoy)")
    ap.add_argument("--sembrar", action="store_true", help="marca como vistas las convocatorias que ya están en el listado")
    ap.add_argument("--issue", action="store_true", help="abre un issue en GitHub con `gh` si hay novedades")
    ap.add_argument("--asignar", default="", help="usuario de GitHub al que asignar el issue")
    ap.add_argument("--avisar", action="store_true", help="envía los correos a los suscritos")
    ap.add_argument("--salida", help="escribe el informe en este fichero")
    ap.add_argument("--auto", help="fichero JSON donde se guardan las fichas creadas automáticamente (se crea si no existe)")
    ap.add_argument("--solo-estado", action="store_true", help="marca todo lo encontrado como visto, sin informar (para empezar de cero)")
    ap.add_argument("--fecha-escaneo", help="escribe {fecha: hoy} en este fichero JSON (lo lee la web)")
    a = ap.parse_args()

    opos = json.load(open(a.opos, encoding="utf8"))
    auto = cargar(a.auto) if a.auto else []
    if not isinstance(auto, list):
        auto = []
    opos = opos + [o for o in auto if o["id"] not in {x["id"] for x in opos}]
    hoy = dt.date.fromisoformat(a.hasta) if a.hasta else dt.date.today()
    est = {} if a.sin_estado else cargar(a.estado)
    vistos = set(est.get("vistos", []))
    if a.sembrar:
        vistos |= conocidos_de(opos)
    if a.desde:
        ini = dt.date.fromisoformat(a.desde)
    elif est.get("boe_ultimo"):
        ini = dt.date.fromisoformat(est["boe_ultimo"]) - dt.timedelta(days=2)   # solape por si el BOE publica tarde
    else:
        ini = hoy - dt.timedelta(days=3)

    hallazgos = []
    dia = ini
    while dia <= hoy:
        if dia.weekday() != 6:   # el BOE no publica los domingos
            hallazgos += boe_dia(dia)
            time.sleep(0.4)
        dia += dt.timedelta(days=1)

    # BOJA: desde el boletín siguiente al último visto (o, la primera vez, el de la fecha de inicio)
    anio = hoy.year
    n = None
    if est.get("boja_anio") == anio and est.get("boja_ultimo"):
        n = max(est["boja_ultimo"] - 1, 1)   # solape de 2 boletines
    if n is None:
        lo, hi = 1, 260
        while lo < hi:
            mid = (lo + hi) // 2
            ok, f, _ = boja_boletin(anio, mid)
            if not ok or (f and f >= ini.isoformat()):
                hi = mid
            else:
                lo = mid + 1
        n = max(lo - 1, 1)
    ultimo = est.get("boja_ultimo") if est.get("boja_anio") == anio else None
    while True:
        ok, fecha, c = boja_boletin(anio, n)
        if not ok:
            break
        hallazgos += c
        ultimo = n
        n += 1
        time.sleep(0.4)

    # clasificar lo que no hemos visto
    nuevas, eventos = [], []
    for c in hallazgos:
        if c["id"] in vistos:
            continue
        procesos = procesos_de(c["titulo"], opos)
        if es_convocatoria(c["titulo"]) or es_convocatoria_junta(c["titulo"]) or es_convocatoria_sas(c["titulo"]):
            if es_convocatoria_sas(c["titulo"]):   # una resolución del SAS convoca varias categorías: «procesos_de» confundiría Administrativo/a con Auxiliar Administrativo/a
                if not any((o.get("enlace") or {}).get("u") == c["url"] for o in opos):
                    nuevas.append(c)
            elif not procesos:
                nuevas.append(c)
        elif procesos:
            clave, texto = tipo_cambio(c["titulo"])
            eventos.append({**c, "tipo": clave, "texto": texto, "procesos": procesos})
    if a.solo_estado:
        nuevas, eventos = [], []
    creadas = []
    if a.auto and nuevas:
        import ficha_auto
        sin_crear = []
        for c in sorted(nuevas, key=lambda c: (c["fecha"] or "", c["id"])):
            if not es_convocatoria_sas(c["titulo"]) and procesos_de(c["titulo"], opos):   # la misma convocatoria salió en BOE y BOJA: ya la hemos creado en esta vuelta
                continue
            if any((o.get("enlace") or {}).get("u") == c["url"] for o in opos):   # ya hay fichas de esa misma publicación (p. ej. la resolución que convoca varias especialidades)
                continue
            try:
                if es_convocatoria_junta(c["titulo"]):
                    import ficha_junta
                    fichas = ficha_junta.crear(c, opos)   # una ficha por especialidad de la misma resolución
                elif es_convocatoria_sas(c["titulo"]):
                    import ficha_sas
                    fichas = ficha_sas.crear(c, opos)   # una ficha por categoría que cubrimos (Auxiliar, Administrativo/a, Celador/a, Celador/a-Conductor/a)
                else:
                    fichas = [ficha_auto.crear(c, opos)]
            except Exception as e:
                c["motivo"] = str(e)
                sin_crear.append(c)
                print(f"  ! no se pudo crear la ficha de {c['id']}: {e}", file=sys.stderr)
                continue
            for f in fichas:
                auto.append(f)
                opos.append(f)
                creadas.append((c, f))
        nuevas = sin_crear
        if creadas:
            os.makedirs(os.path.dirname(os.path.abspath(a.auto)), exist_ok=True)
            json.dump(auto, open(a.auto, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    filas, pendientes = procesar_cambios(eventos, a.avisar)
    texto = informe(nuevas, filas, creadas)
    print(texto)
    if a.salida:
        open(a.salida, "w", encoding="utf8").write(texto + "\n")

    if (nuevas or filas or creadas) and a.issue:
        titulo = f"Novedades de convocatorias PAS en universidades andaluzas ({hoy.isoformat()})"
        cmd = ["gh", "issue", "create", "--title", titulo, "--body", texto]
        if a.asignar:   # al asignarlo, GitHub avisa por correo a esa persona; si no se puede asignar, se crea igualmente
            if subprocess.run(cmd + ["--assignee", a.asignar]).returncode != 0:
                subprocess.run(cmd, check=True)
        else:
            subprocess.run(cmd, check=True)

    if a.fecha_escaneo:
        os.makedirs(os.path.dirname(os.path.abspath(a.fecha_escaneo)), exist_ok=True)
        json.dump({"fecha": hoy.isoformat()}, open(a.fecha_escaneo, "w", encoding="utf8"))

    if not a.sin_estado and a.estado:
        previo = est.get("boe_ultimo")
        # lo que quedó pendiente de enviar (o a la espera de activar el envío) NO se da por visto: se reintentará
        procesado = {c["id"] for c in hallazgos if c["id"] not in pendientes}
        vistos_nuevos = vistos | procesado
        cambiado = (not os.path.exists(a.estado) or vistos_nuevos != set(est.get("vistos", [])) or not previo
                    or (hoy - dt.date.fromisoformat(previo)).days >= 10 or a.sembrar)
        est["vistos"] = sorted(vistos_nuevos)
        est["boe_ultimo"] = hoy.isoformat()
        est["boja_anio"] = anio
        if ultimo:
            est["boja_ultimo"] = ultimo
        est["revisado"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        if cambiado:   # así no hay un commit diario del estado y, a la vez, el proceso no se desactiva por inactividad
            os.makedirs(os.path.dirname(os.path.abspath(a.estado)), exist_ok=True)
            json.dump(est, open(a.estado, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
