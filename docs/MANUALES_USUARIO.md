# Manuales de Usuario - Sistema de Cafeteria

## Documentos

- [Manual general](MANUAL_GENERAL.md)
- [Manual del administrador](MANUAL_ADMINISTRADOR.md)
- [Manual del cajero](MANUAL_CAJERO.md)
- [Manual del despachador](MANUAL_DESPACHADOR.md)
- [Manual del auditor](MANUAL_AUDITOR.md)
- [Manual del cliente comprador](MANUAL_CLIENTE.md)

## Roles del sistema

| Rol | Funcion principal |
| --- | --- |
| Administrador | Administra usuarios, productos, compras, ventas, reportes y auditoria. |
| Cajero | Consulta el sistema, gestiona el flujo de ventas, compras en modo consulta y reportes. |
| Despachador | Prepara y marca pedidos como entregados. |
| Auditor | Consulta la informacion del sistema y revisa la auditoria sin modificar datos. |
| Cliente comprador | Consulta el menu, crea pedidos y consulta el estado de sus propias compras. |

## Nota sobre nombres de roles

El rol mostrado como despachador se almacena internamente con el valor `despachador`. Las cuentas creadas como personal pueden tener los roles `cajero`, `despachador` o `auditor`.
