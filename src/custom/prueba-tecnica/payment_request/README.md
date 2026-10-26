# Solicitudes de pago (`payment_request`)

Permite solicitar, aprobar y registrar pagos a proveedores desde Odoo.

## Tramos completados

- **A:** añadí solicitudes con secuencia, proveedor, solicitante, monto,
  moneda, fecha, concepto y estados. Incluye grupos, vistas y reglas para que
  el solicitante vea sus solicitudes y no pueda aprobarlas.
- **B:** añadí niveles de aprobación por monto y moneda, actividad para el
  aprobador, rechazo con motivo en el chatter, wizard de pago y reporte PDF.
- **C:** el pago convierte el monto a la moneda del diario según la tasa de la
  fecha de pago. Las solicitudes y los niveles se limitan por compañía; las
  transiciones usan bloqueo de filas para evitar acciones simultáneas y el
  registro del pago y el cambio de estado comparten una transacción.

## Cómo probar

Desde la raíz del repositorio:

```bash
./odoo test prueba-tecnica payment_request
```

La prueba conjunta de los cuatro addons está documentada en
[`../README.md`](../README.md).

## Supuestos y preguntas al cliente

Antes de desplegarlo, le preguntaría a Carolina:

- ¿Qué montos y monedas definen cada nivel, y quiénes serán los aprobadores
  por área y compañía?
- ¿Puede un empleado aprobar una solicitud de otra persona? ¿Se permite que
  quien solicita pertenezca al grupo de aprobadores?
- ¿Qué diarios puede usar Tesorería y se permiten pagos parciales o varios
  pagos para una solicitud?
- ¿Qué política se aplica a proveedores, conceptos y documentos de respaldo?

Para avanzar sin respuesta, asumí que:

- Los niveles se configuran por compañía y moneda, y gana el nivel con el
  monto mínimo más alto que no supere el monto solicitado.
- El solicitante no puede aprobar ni rechazar su propia solicitud; solo el
  aprobador asignado puede hacerlo.
- Una solicitud genera un pago total desde un diario bancario o de caja; no
  se permiten pagos parciales ni un segundo pago vinculado.
- La solicitud conserva el monto y moneda originales. Si el diario usa otra
  moneda, Odoo convierte el monto con la tasa de la fecha de pago.
- Las solicitudes enviadas ya no se editan; para cambiar sus datos se debe
  crear una nueva solicitud.

## Limitaciones conocidas

- Si no hay un nivel de aprobación configurado para la compañía, moneda y
  monto, no se puede enviar la solicitud.
- El módulo no adjunta ni exige una factura o documento de respaldo.
- El flujo registra un único pago total por solicitud; no incluye pagos
  parciales ni aprobación delegada.
- Las tasas de cambio dependen de las tasas configuradas en Odoo para la
  compañía y fecha seleccionadas.

La explicación de multi-compañía, bloqueo y conversión está en
[`ARCHITECTURE.md`](./ARCHITECTURE.md).
