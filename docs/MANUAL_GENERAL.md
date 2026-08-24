# Manual General de Usuario

## 1. Iniciar sesion

1. Abra la pagina de inicio de sesion del personal.
2. Escriba el correo registrado.
3. Escriba la contraseña.
4. Seleccione **Ingresar**.
5. El sistema mostrara solamente las opciones permitidas para el rol de la cuenta.

Si olvido la contraseña, use **Olvide mi contraseña** y siga el enlace recibido. En desarrollo, si no hay SMTP configurado, el enlace se muestra en el registro de la aplicacion.

## 2. Navegacion

- **Dashboard:** resumen de ventas y alertas de stock.
- **Productos:** consulta y, según el rol, administración del catálogo e inventario.
- **Ventas:** seguimiento y cambio de estado de pedidos.
- **Compras:** consulta de compras y, para el administrador, registro de nuevas compras.
- **Reportes:** creación y consulta de reportes.
- **Usuarios:** administración de cuentas, solo para el administrador.
- **Auditoria:** consulta de acciones registradas.

## 3. Estados de un pedido

El flujo normal es:

`Pendiente de Pago` -> `Pagado/Preparando` -> `Preparado` -> `Entregado`

Un pedido pendiente también puede pasar a `Cancelado`. Al cancelarlo se devuelve el stock de sus productos.

## 4. Productos e inventario

- El stock se descuenta cuando el cliente confirma el pedido.
- Una compra registrada aumenta el stock.
- Una baja de inventario disminuye el stock y exige cantidad y motivo.
- Un producto con historial no se elimina físicamente: se marca como inactivo para conservar ventas, compras y reportes.
- Los productos inactivos pueden consultarse y reactivarse por un usuario autorizado.

## 5. Importar productos desde Excel

1. Entre a **Productos > Cargar Excel**.
2. Seleccione un archivo `.xlsx`.
3. Asegúrese de que la primera fila tenga al menos `Producto` y `Precio ($)`.
4. Seleccione **Importar**.

También se reconocen `Costo ($)`, `Stock`, `Stock Mínimo`, `Categoría` y `Subcategoría`. Las columnas adicionales se ignoran. Los valores vacíos quedan en costo `0`, stock `0`, stock mínimo `10` y precio `0`; revise las advertencias mostradas después de importar.

## 6. Cerrar sesion

Use la opción **Cerrar sesión** al terminar, especialmente en equipos compartidos.
