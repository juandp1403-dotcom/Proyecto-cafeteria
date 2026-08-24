# Manual del Administrador

## Alcance

El administrador tiene acceso completo al dashboard, productos, ventas, compras, reportes, usuarios y auditoria. Puede crear, editar, desactivar y reactivar la información permitida por el sistema.

## Administrar productos

1. Abra **Productos**.
2. Use **Nuevo producto** para registrar nombre, precio, costo, stock, stock mínimo, categoría, subcategoría, descripción e imagen.
3. Use el botón de edición para corregir información.
4. Use **Eliminar** para retirar un producto. Si tiene historial, quedará inactivo.
5. Use la vista de inactivos para reactivar un producto cuando sea necesario.

## Cargar el inventario desde Excel

Use **Cargar Excel** para importar productos en lote. El sistema actualiza un producto si ya existe un nombre igual sin distinguir mayúsculas y crea uno nuevo si no existe. Revise siempre el resumen y las advertencias de filas después de cargar.

## Registrar compras

1. Abra **Compras** y seleccione **Nueva compra**.
2. Escriba el vendedor.
3. Agregue los productos, cantidades y precios pagados.
4. Confirme la compra.

El sistema registra la compra, aumenta el stock y actualiza el costo unitario del producto.

## Gestionar ventas

- Acepte pedidos en estado `Pendiente de Pago`.
- Rechace pedidos pendientes cuando corresponda.
- Marque como `Preparado` o `Entregado` según el avance.
- Use los filtros por día, semana, mes o año.
- Exporte ventas a Excel cuando necesite conservar o analizar la información.

## Administrar usuarios y roles

1. Abra **Usuarios**.
2. Seleccione **Nuevo Usuario**.
3. Elija una cuenta administrativa o de personal.
4. Para personal, seleccione `cajero`, `despachador` o `auditor`.
5. Asigne una contraseña de mínimo 8 caracteres con letras y números.

Un usuario con historial no se elimina físicamente: se desactiva. No es posible eliminar la cuenta actualmente utilizada por el administrador.

## Reportes y auditoria

- Cree reportes desde **Reportes** indicando descripción, producto y fecha.
- Consulte **Auditoria** para revisar acciones realizadas por las cuentas.
- Atienda las solicitudes de supresión de datos personales conforme al procedimiento de privacidad del proyecto.
