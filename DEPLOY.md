# Despliegue

## Verificar que la app está usando la base de datos real (no SQLite efímero)

Antes de dar por bueno un despliegue en producción:

1. Confirma que el contenedor tiene configuradas `SSH_HOST` (+ `SSH_PORT`,
   `SSH_USER`, `SSH_KEY`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`,
   `DB_NAME`) o directamente `DATABASE_URL`. Ver `.env.example`.
2. Revisa los logs de arranque: si aparece `[tunel SSH] Conectado a ...`,
   el túnel se abrió correctamente.
3. Si falta la configuración, la app ahora **no arranca** en producción —
   falla con un `RuntimeError` explícito en vez de usar SQLite en
   silencio (ver HU-34). Si el contenedor no levanta y el log menciona
   "No hay conexion real a base de datos configurada", es exactamente
   esto: falta configurar las variables de entorno antes de desplegar.
4. Nunca despliegues con `config_name='development'` en producción: ese
   modo sí permite caer en SQLite efímero (los datos se perderían en
   cada reinicio del contenedor).

## Verificar la clave de host SSH del túnel (HU-43)

Si el despliegue usa `SSH_HOST` para el túnel hacia la base de datos:

1. Obtén la clave de host real del servidor una sola vez, desde una red
   de confianza: `ssh-keyscan -t ed25519 <tu-host-ssh>`.
2. Configura `SSH_HOST_KEY` con esa línea (formato `tipo base64key`).
3. En producción, si `SSH_HOST_KEY` no está configurada, el arranque
   falla explícitamente con `RuntimeError` — es intencional: sin esa
   clave, el túnel aceptaría cualquier servidor que se haga pasar por
   el real (riesgo de intercepción MITM del tráfico hacia la BD).
4. En desarrollo local, si falta, solo se imprime una advertencia y el
   túnel sigue funcionando sin verificar — para no bloquear a alguien
   que recién está configurando su entorno local.

## Imágenes subidas: usar un volumen persistente (HU-63)

`static/imagenes/` (biblioteca) y `static/productos/` (imágenes activas
de cada producto) ya no se versionan en git — solo queda un `.gitkeep`
para que las carpetas existan en un clon nuevo. Si no se monta un
volumen persistente, cada redeploy del contenedor borra las imágenes
subidas por el equipo.

En Coolify (o el orquestador que se use), monta un volumen para ambas
rutas, por ejemplo en `docker-compose.yml`:

```yaml
services:
  web:
    volumes:
      - imagenes_productos:/app/static/imagenes
      - imagenes_activas:/app/static/productos

volumes:
  imagenes_productos:
  imagenes_activas:
```

## CI: lint + tests + pip-audit (HU-30) y Dependabot (HU-23)

- `.github/workflows/ci.yml` corre en cada push/PR a `main`: `ruff`
  (lint), `pytest` (tests) y `pip-audit` (vulnerabilidades conocidas).
- `.github/dependabot.yml` abre PRs automáticos semanales para
  `requirements.txt` y para las Actions usadas en el workflow.
- **Pendiente de un admin del repo (no se puede hacer por código):**
  activar "Require status checks to pass before merging" en
  Settings → Branches → Branch protection rules para `main`, marcando
  los tres checks (`lint`, `test`, `pip-audit`) como obligatorios.
- El check `pip-audit` hoy queda en rojo a propósito: hay CVEs
  conocidos en Flask, Werkzeug, python-dotenv, Pillow y paramiko
  (ver salida de `pip-audit -r requirements.txt`). Actualizarlos es
  un cambio aparte que merece su propia verificación (Pillow salta de
  10.4 a 12.x), no se hizo aquí para no arriesgar el despliegue de hoy.
