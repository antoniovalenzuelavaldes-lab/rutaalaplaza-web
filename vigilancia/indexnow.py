#!/usr/bin/env python3
"""Avisa a los buscadores que usan IndexNow (Bing, Yandex, Seznam, Naver…) de las páginas que han cambiado, para que no tengan que
esperar a rastrear la web. Google no usa IndexNow: a Google se le avisa con el sitemap y Search Console.

Uso:
  python indexnow.py docs cambios.txt     # cambios.txt: rutas de ficheros cambiados, una por línea (salida de git diff --name-only)
  python indexnow.py docs --todas         # todas las direcciones del sitemap
La clave es el fichero «<clave>.txt» de docs/ (público por diseño: así el buscador comprueba que la web es nuestra).
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

HOST = "rutaalaplaza.com"
BASE = "https://" + HOST


def url_de(fichero):
    f = fichero.replace("\\", "/")
    if f == "docs/index.html":
        return BASE + "/"
    m = re.fullmatch(r"docs/(oposiciones(?:/[^/]+)*)/index\.html", f)
    if m:
        return f"{BASE}/{m.group(1)}/"
    m = re.fullmatch(r"docs/(legal/[a-z-]+\.html)", f)
    return f"{BASE}/{m.group(1)}" if m else None


def main():
    docs = sys.argv[1] if len(sys.argv) > 1 else "docs"
    claves = [f[:-4] for f in os.listdir(docs) if re.fullmatch(r"[0-9a-f]{32}\.txt", f)]
    if not claves:
        print("No hay fichero de clave en", docs)
        return 0
    clave = claves[0]
    if len(sys.argv) > 2 and sys.argv[2] == "--todas":
        urls = re.findall(r"<loc>([^<]+)</loc>", open(os.path.join(docs, "sitemap.xml"), encoding="utf8").read())
    else:
        lista = open(sys.argv[2], encoding="utf8").read().split() if len(sys.argv) > 2 and os.path.exists(sys.argv[2]) else []
        urls = sorted({u for u in (url_de(f) for f in lista) if u})
    if not urls:
        print("Nada que avisar.")
        return 0
    cuerpo = json.dumps({"host": HOST, "key": clave, "keyLocation": f"{BASE}/{clave}.txt", "urlList": urls[:10000]}).encode("utf8")
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: {len(urls)} direcciones enviadas (respuesta {r.status}).")
    except urllib.error.HTTPError as e:   # 202 = recibido, pendiente de comprobar la clave; otros códigos se informan, sin romper el proceso
        print(f"IndexNow: respuesta {e.code} {e.read()[:200].decode('utf8', 'replace')}")
    except Exception as e:
        print("IndexNow: no se pudo avisar:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
