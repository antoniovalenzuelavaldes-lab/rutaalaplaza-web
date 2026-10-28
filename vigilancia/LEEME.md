# Vigilancia diaria de convocatorias

Cada mañana, el flujo `.github/workflows/vigilar-convocatorias.yml` ejecuta `vigilar_convocatorias.py`, que lee el BOE y el
BOJA y busca publicaciones del personal de administración y servicios de las 10 universidades públicas andaluzas.

- **Convocatoria nueva** (que no está en `docs/oposiciones.json`): abre un aviso (issue) para que se verifique y se añada al listado.
- **Cambio en una convocatoria que seguimos** (corrección de errores, lista de admitidos, fecha del examen, tribunal,
  resultados…): lo incluye en el aviso y escribe por correo a quien se haya suscrito a esa oposición.
- Escribe la fecha del último escaneo en `docs/ultimo-escaneo.json`, que muestra la web («Listado actualizado a fecha…»).
- `estado.json` recuerda lo ya visto, para no repetir avisos.

## Activarlo (una sola vez)
1. En GitHub: **Settings → Secrets and variables → Actions → New repository secret**, con estos tres:
   - `SUPABASE_URL`: `https://iwphtebnkvxlcsjmxptc.supabase.co`
   - `SUPABASE_SERVICE_KEY`: la clave `service_role` de Supabase (Project Settings → API). **Nunca en el chat ni en el código.**
   - `BREVO_API_KEY`: clave de API de Brevo (SMTP & API → API Keys; no es la clave SMTP).
2. **El envío a suscritos viene apagado.** Mientras no se active, el aviso solo cuenta cuántas personas recibirían cada cambio.
   Para activarlo: **Settings → Secrets and variables → Actions → Variables → New repository variable**,
   nombre `AVISOS_AUTOMATICOS`, valor `si`.
3. Prueba manual: pestaña **Actions → Vigilar convocatorias → Run workflow**.

## Mantenimiento
- Al añadir una oposición a `oposiciones.json`, hay que darle sus `claves` (palabras que la identifican en los títulos del
  BOE/BOJA) para que se le asignen sus cambios.
- Si no hay actividad en el repositorio durante 60 días GitHub desactiva los flujos programados; el flujo hace un commit con la fecha
  del escaneo cada día, así que no debería pasar.
