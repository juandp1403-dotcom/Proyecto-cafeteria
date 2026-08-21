# Spike: autenticación real para clientes (HU-10)

**Problema:** hoy el registro de cliente (`/cliente/registro`) solo pide
documento, nombre y ficha, sin ninguna verificación de identidad — es
la causa del IDOR de HU-08 (cualquiera que conozca un número de
documento ajeno puede "registrarse" con él y ver sus pedidos).

## Alternativa 1 — PIN local (generado en el primer registro)

- Al registrarse por primera vez, el sistema genera un PIN de 4-6
  dígitos y se lo muestra al cliente en pantalla (o se lo entrega el
  cajero en persona, dado que es una cafetería física).
- En visitas siguientes, el cliente debe dar documento + PIN.
- **Costo:** bajo. No requiere infraestructura de correo/SMS, solo una
  columna nueva (`pin_hash`) en `Cliente` y comparación con
  `check_password_hash`.
- **Beneficio:** cierra el IDOR sin fricción para el cliente (no
  necesita tener correo ni celular a mano).
- **Riesgo:** si el cliente pierde el PIN, no hay forma de
  recuperarlo sin que un cajero lo resetee manualmente.

## Alternativa 2 — OTP por correo

- Se pide correo en el registro; cada visita envía un código de un
  solo uso por email antes de dar acceso al historial.
- **Costo:** medio-alto. Requiere infraestructura SMTP (el otro
  proyecto del equipo, Sistema Clima, ya tiene una reutilizable en
  `app/security.py` como referencia), manejo de expiración de
  códigos, y que el cliente tenga correo a mano en cada visita.
- **Beneficio:** más robusto, con canal de recuperación natural
  (reenviar código).
- **Riesgo:** fricción alta para un caso de uso de cafetería rápida —
  no todos los estudiantes van a querer revisar el correo para pedir
  un café.

## Recomendación

**Alternativa 1 (PIN local)** para este caso de uso — es proporcional
al riesgo real (evitar que alguien vea el pedido de otro, no proteger
una cuenta bancaria) y no agrega fricción ni dependencias nuevas. La
alternativa 2 se puede reconsiderar más adelante si el sistema empieza
a manejar pagos en línea o datos más sensibles.

**Estado:** spike completo, pendiente de que el equipo confirme la
alternativa antes de implementarla como historia de código.
