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
