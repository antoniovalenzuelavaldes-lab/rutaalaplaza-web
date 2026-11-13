#!/usr/bin/env python3
r"""Publica en el canal de Telegram de Ruta a la Plaza con un bot oficial (sin cuenta personal).
Uso:
  python publicar_telegram.py pregunta [N]     # imagen de la pregunta del «test del día» N (por defecto, el de hoy)
  python publicar_telegram.py respuesta [N]    # imagen con la respuesta
  python publicar_telegram.py boletin          # texto del boletín semanal de convocatorias abiertas
  python publicar_telegram.py prueba           # solo comprueba el bot y el canal, sin publicar
  Añade --seco para ver lo que se publicaría sin enviar nada.
El token del bot se lee de la variable TELEGRAM_BOT_TOKEN o de C:\Proyectos\01.secretos\telegram_token.txt; el canal, de TELEGRAM_CANAL
(p. ej. @rutaalaplaza) o de C:\Proyectos\01.secretos\telegram_canal.txt. Nunca se imprime el token. «Hoy» = días desde marketing/inicio.txt (AAAA-MM-DD) + 1."""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request
import uuid

sys.stdout.reconfigure(encoding="utf8")
AQUI = os.path.dirname(os.path.abspath(__file__))
SECO = "--seco" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]


def leer(nombre_env, fichero):
    v = os.environ.get(nombre_env, "").strip()
    if v:
        return v
    f = os.path.expanduser(fichero) if fichero.startswith("~") else (fichero if os.path.isabs(fichero) else os.path.join(AQUI, fichero))
    return open(f, encoding="utf8").read().strip() if os.path.exists(f) else ""


def api(metodo, campos=None, fichero=None):
    token = leer("TELEGRAM_BOT_TOKEN", r"C:\Proyectos\01.secretos\telegram_token.txt") or leer("", "~/.telegram_token")
    if not token:
        sys.exit("Falta el token del bot (TELEGRAM_BOT_TOKEN o secretos/telegram_token.txt)")
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    if fichero:
        b = "----" + uuid.uuid4().hex
        cuerpo = b""
        for k, v in (campos or {}).items():
            cuerpo += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf8")
        cuerpo += f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="foto.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + open(fichero, "rb").read() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(url, data=cuerpo, headers={"Content-Type": "multipart/form-data; boundary=" + b})
    else:
        req = urllib.request.Request(url, data=json.dumps(campos or {}).encode("utf8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def numero_hoy():
    ini = leer("", "inicio.txt")
    if not ini:
        sys.exit("Falta marketing/inicio.txt con la fecha del día 1 (AAAA-MM-DD)")
    return max(1, (dt.date.today() - dt.date.fromisoformat(ini)).days + 1)


def pie_del_dia(n):
    """Pie de foto de la publicación N sacado de test-del-dia/textos.md (versión «Telegram»)."""
    t = open(os.path.join(AQUI, "test-del-dia", "textos.md"), encoding="utf8").read()
    m = re.search(rf"## Día {n} ·.*?\*\*Telegram o WhatsApp \(canal propio\):\*\*\s*\n\n((?:> [^\n]*\n?)+)", t, re.S)
    return re.sub(r"^> ?", "", m.group(1).strip(), flags=re.M) if m else f"Test del día #{n}"


def enviar(canal, texto=None, foto=None, pie=None):
    if SECO:
        print("[seco]", canal, "|", foto or "texto", "\n", (pie or texto or "")[:400])
        return
    r = api("sendPhoto", {"chat_id": canal, "caption": pie[:1000]}, foto) if foto else api("sendMessage", {"chat_id": canal, "text": texto, "disable_web_page_preview": True})
    print("enviado" if r.get("ok") else f"ERROR: {r.get('description')}")
    if not r.get("ok"):
        sys.exit(1)


def main():
    modo = args[0] if args else "prueba"
    canal = leer("TELEGRAM_CANAL", r"C:\Proyectos\01.secretos\telegram_canal.txt")
    if modo == "prueba":
        me = api("getMe")
        print("bot:", me.get("result", {}).get("username") if me.get("ok") else me.get("description"))
        if canal:
            ch = api("getChat", {"chat_id": canal})
            print("canal:", ch.get("result", {}).get("title") if ch.get("ok") else ch.get("description"))
        return
    if not canal and not SECO:
        sys.exit("Falta el canal (TELEGRAM_CANAL o secretos/telegram_canal.txt)")
    canal = canal or "@canal"
    if modo in ("pregunta", "respuesta"):
        n = int(args[1]) if len(args) > 1 else numero_hoy()
        if n > 30:
            print("Se acabaron los 30 tests del día preparados: no se publica nada (el boletín sale los lunes).")
            return
        f = os.path.join(AQUI, "test-del-dia", f"dia-{n}-{modo}.png")
        pie = pie_del_dia(n) if modo == "pregunta" else f"✅ Respuesta del test del día #{n}. Más tests explicados con la ley: https://rutaalaplaza.com/?utm_source=telegram&utm_campaign=test-del-dia"
        enviar(canal, foto=f, pie=pie)
    elif modo == "boletin":
        main_boletin(canal)


def main_boletin(canal):
    subprocess.run([sys.executable, os.path.join(AQUI, "boletin_semanal.py")], check=True, capture_output=True)
    t = open(os.path.join(AQUI, "boletin.md"), encoding="utf8").read()
    m = re.search(r"## Telegram / WhatsApp \(canal propio\)\s*\n\n(.*?)\n\n## Instagram", t, re.S)
    enviar(canal, texto=m.group(1))


main()
