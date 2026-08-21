# Decisión: alcance del módulo de pago de sueldos (HU-67)

Bryan pidió "agregar apartado de pago de sueldos". Antes de estimarlo
como código, hay que decidir cuál de los dos escenarios aplica —
tienen implicaciones muy distintas.

## Opción A — Registro interno informal

Una tabla simple que registra cuánto se le pagó a cada persona del
equipo por turno/tarea, sin pretender ser nómina laboral formal.

- **Alcance:** una tabla (`pago`) con documento, monto, fecha,
  concepto. Un formulario para registrarlo, una lista para
  consultarlo.
- **Implicaciones legales:** ninguna adicional a las que ya tiene el
  proyecto — es solo un registro de datos, no un sistema de nómina.
- **Tamaño:** Mediano.

## Opción B — Nómina laboral formal

Un sistema que realmente liquida prestaciones sociales, aportes a
seguridad social (salud, pensión, ARL) y parafiscales, con las
obligaciones legales completas de un empleador.

- **Alcance:** mucho mayor — requiere modelar liquidaciones,
  integrarse (o al menos ser compatible) con nómina electrónica de la
  DIAN, que es obligatoria para empleadores con contrato laboral
  formal.
- **Implicaciones legales:** Código Sustantivo del Trabajo, resolución
  de nómina electrónica DIAN. Esto es del mismo orden de complejidad
  que la facturación electrónica de ventas — no es algo que se deba
  improvisar sin conocimiento contable/laboral.
- **Tamaño:** Grande, y con riesgo legal real si se hace mal.

## Decisión

**Pendiente de que el equipo (o quien tenga la última palabra sobre el
proyecto) elija A o B por escrito aquí antes de que se implemente
cualquier código.** Si la cafetería no tiene personal con contrato
laboral formal (parece ser el caso — es un proyecto SENA con
estudiantes/practicantes), la Opción A es casi con seguridad la
correcta.

- [ ] Opción A (registro informal) — recomendada si no hay contrato
      laboral formal de por medio.
- [ ] Opción B (nómina formal) — solo si el proyecto ya tiene personal
      contratado formalmente y necesita cumplir obligaciones legales
      reales.

_Marcar la opción elegida y la fecha antes de crear la historia de
código correspondiente._
