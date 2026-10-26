# Comisiones de vendedores (`sale_commission`)

Calcula la comisión del vendedor en cada línea de pedido de venta y ofrece un análisis mensual por vendedor.

## Tramos completados

- **Ejercicio base:** calculo la comisión de cada línea al confirmar el pedido
  y ofrezco un reporte mensual por vendedor.
- **Mejora por categoría:** una regla de categoría, incluida una categoría
  padre, reemplaza el porcentaje general del vendedor; prevalece la regla más
  específica.
- **Ticket T-200:** corregí el acceso de lectura que impedía confirmar a los
  vendedores, manteniendo sus permisos limitados, y aseguré que una
  confirmación hecha por un gerente use el vendedor asignado al pedido.
- **Incidente:** reproducción, causa, contención, revisión de datos,
  despliegue y prevención están documentados en [`INCIDENT.md`](./INCIDENT.md).

## Configuración

- **Porcentaje del vendedor:** Ajustes › Usuarios › pestaña *Comisiones* (solo gerentes de ventas).
- **Porcentaje por categoría (desde la 1.1):** Inventario/Ventas › Configuración › Categorías de producto,
  campo *Comisión (%)*. Si la categoría (o una categoría padre) tiene porcentaje, reemplaza al del vendedor.

## Cómo funciona

- Al confirmar el pedido se fija el porcentaje en cada línea y se calcula la comisión sobre el subtotal sin impuestos.
- El botón *Recalcular comisiones* del pedido vuelve a aplicar los porcentajes vigentes.
- Ventas › Reportes › *Comisiones*: tabla dinámica y gráfico por vendedor y mes. Cada vendedor ve solo lo suyo.

## Pruebas

```bash
./odoo test prueba-tecnica sale_commission
```

## Supuestos y limitaciones

- La comisión se calcula sobre el subtotal de cada línea sin impuestos y el
  porcentaje queda guardado al confirmar el pedido.
- Si existe una regla para la categoría del producto o una categoría padre,
  esa regla reemplaza el porcentaje configurado en el usuario.
- El script de auditoría T-200 lista candidatos con señales de posible
  diferencia; cada caso debe confirmarse con el historial y Comercial antes de
  corregir datos.
- El reporte solo muestra las comisiones que el usuario tiene permiso de ver;
  cada vendedor ve las suyas y los gerentes pueden revisar el equipo.
