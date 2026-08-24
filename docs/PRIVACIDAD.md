# Política de Privacidad y Tratamiento de Datos Personales

**Sistema:** Cafetería CGAO — SENA (Centro de Gestión Administrativa y Cooperativista)
**Normatividad:** Ley 1581 de 2012, Decreto 1377 de 2013 (Colombia)

## 1. Datos recolectados

| Dato | Finalidad | Base del tratamiento |
|---|---|---|
| Documento de identidad | Identificar el pedido y su titular | Consentimiento (checkbox obligatorio en el registro) |
| Nombre completo | Entregar el pedido a la persona correcta | Consentimiento |
| Número de ficha | Verificar vinculación con el centro | Consentimiento |

No se recolectan datos sensibles.
El consentimiento se solicita de forma expresa mediante un checkbox **no premarcado**
en `templates/cliente/registro.html` y se valida también en el backend.

**Aprendices menores de edad (16-17 años):** el centro tiene aprendices menores de edad
(adolescentes, según el Código de la Infancia y la Adolescencia, que cubre hasta los 18 años),
y este sistema sí trata sus datos (documento, nombre, ficha) en el mismo formulario de registro.
El Artículo 7 de la Ley 1581 de 2012 exige que el representante legal del menor participe en la
autorización de ese tratamiento — un checkbox marcado por el propio adolescente en el momento del
registro **no cumple ese requisito por sí solo**.

Todo aprendiz (incluidos los menores de edad) firma un **contrato de aprendizaje** como condición
para vincularse al SENA; en el caso de menores, ese contrato requiere la participación de su
representante legal, lo cual cubre la exigencia general del Artículo 7 de la Ley 1581 de 2012 para
la relación de formación con el SENA.

**Pendiente de definir con el área jurídica/de protección de datos del SENA:** el contrato de
aprendizaje autoriza el tratamiento de datos para la relación de formación en general, pero **no
está confirmado que cubra explícitamente el tratamiento de datos por parte de este sistema de
cafetería en particular** (un servicio adicional, no el proceso central de matrícula). Falta
verificar si el texto del contrato es lo bastante amplio para amparar este uso, o si se necesita
una autorización/cláusula específica para sistemas internos como este.

## 2. Derecho de supresión (Ley 1581 de 2012, Art. 9)

Todo cliente puede solicitar la supresión de sus datos desde la ruta
`/cliente/supresion` (enlazada desde la política de privacidad). Cada solicitud
queda registrada en la tabla `solicitudsupresion` con:

- documento del solicitante
- motivo (opcional)
- **fecha y hora** de la solicitud (zona horaria America/Bogota)
- estado (`Pendiente` / `Procesada`)

El administrador (rol con permiso `ver_datos_personales`) ve las solicitudes en
**Admin → Usuarios → Solicitudes de Supresión** y las procesa manualmente.

## 3. Qué se elimina y qué se conserva al procesar una solicitud

### Se elimina / anonimiza
- El registro del **cliente** en la tabla `cliente` (documento, nombre, ficha),
  o su anonimización si tiene pedidos asociados:
  - `nombre` → `ANONIMIZADO`
  - `ficha` → `0`
  - el documento se conserva como clave técnica sin uso identificativo.

### Se conserva (obligación legal — NO se puede borrar)
- Los registros de **venta/facturación** ya emitidos (`venta`, `detalleventa`),
  porque el sistema respalda reportes oficiales ante el SENA:

| Obligación | Plazo mínimo de retención | Norma |
|---|---|---|
| Registros contables y comprobantes | 10 años | Art. 60 Código de Comercio |
| Soportes fiscales | 5 años | Art. 632 Estatuto Tributario |

Estos registros conservan los montos y productos, pero quedan **desvinculados
de la identidad** del titular tras la anonimización.

## 4. Seguridad y acceso

- Solo el rol **admin** tiene el permiso `ver_datos_personales`.
- Los roles auditor, cajero y despachador ven datos enmascarados
  (iniciales y `*****XXX`) en pantallas y exportaciones a Excel.
- Las facturas solo son consultables por su titular o por personal autenticado.

## 5. Contacto

Para ejercer derechos de acceso, actualización, rectificación o supresión:
administración de la Cafetería CGAO — SENA.
