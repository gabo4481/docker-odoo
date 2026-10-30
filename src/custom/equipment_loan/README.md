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
  registro del pago y el cambio de estado comparten una transacción. Una
  prueba con dos transacciones concurrentes verifica que solo una aprobación
  puede cambiar el estado.

## Preparar usuarios y aprobación

El botón **Enviar** aparece en una solicitud guardada en estado **Borrador**
solo para usuarios que pertenezcan al grupo **Solicitante de pagos**. Para
asignarlo en Odoo 17:

1. Inicia sesión con un usuario administrador y abre **Ajustes → Usuarios y
   compañías → Usuarios**.
2. Abre el usuario que creará solicitudes y entra en **Permisos de acceso**.
3. En la sección **Gestión de Pagos**, selecciona **Solicitante de pagos**.
   Guarda los cambios. Si esa sección no aparece, verifica que el módulo
   `payment_request` esté instalado y recarga el formulario de usuario.
4. Cierra y vuelve a iniciar sesión con ese usuario. Crea y guarda una
   solicitud; debe quedar en **Borrador** y mostrar el botón **Enviar**.

Los grupos **Aprobador de pagos** y **Tesorería de pagos** también están en
**Gestión de Pagos**. Los dos incluyen el acceso de solicitante. Asigna
**Aprobador de pagos** a quien aprobará y **Tesorería de pagos** a quien
registrará el pago; no asignes esos grupos a quien solo necesita solicitar.

Antes de enviar, un administrador debe configurar al menos un nivel en
**Gestión de Pagos → Configuración → Niveles de aprobación**. El nivel debe
coincidir con la compañía y moneda de la solicitud, y su monto mínimo debe
ser menor o igual al monto solicitado. Si hay varios niveles aplicables, se
elige el de monto mínimo más alto que no exceda el monto. Sin coincidencia,
el botón se seguirá viendo, pero al pulsarlo Odoo informará que falta el
nivel; la configuración no es lo que oculta el botón.

En el formulario, proveedor, monto, moneda, fecha y concepto se pueden
completar o corregir mientras la solicitud está en **Borrador**. El
solicitante se muestra como dato de solo lectura. El aprobador se muestra
después de enviar; quién aprobó y cuándo aparecen al aprobar; el motivo solo
aparece si se rechaza; y el pago aparece cuando Tesorería lo registra. Esos
datos de seguimiento son de solo lectura y no se muestran vacíos al inicio.

## Cómo probar

Desde la raíz del repositorio:

```bash
./odoo test prueba-tecnica payment_request
```

La prueba conjunta de los cuatro addons está documentada en
[`../README.md`](../README.md).

## Supuestos y preguntas al cliente

Leí el correo como una necesidad concreta: cualquier empleado debe poder
solicitar un pago, la solicitud enviada queda fija, los pagos normales los
aprueba el jefe del área y los grandes gerencia, Tesorería registra el pago,
el rechazo explica el motivo y el pago puede ser en una moneda distinta de la
solicitud. El correo no define montos, responsables ni varias reglas
operativas; para completar el ejercicio tomé estas decisiones:

### Lo que le preguntaría a Carolina

- ¿Desde qué monto el pago deja de ser normal y debe aprobarlo gerencia?
  ¿Hay más de dos niveles?
- ¿Quiénes son los jefes de cada área y quiénes integran gerencia? ¿La
  aprobación se determina por el área del solicitante, por el proveedor o
  solo por el monto?
- ¿Qué empleados deben recibir el grupo para solicitar pagos? ¿Un aprobador
  puede aprobar una solicitud propia?
- ¿Tesorería debe pagar el monto completo en una sola operación? ¿Qué diarios
  puede usar?
- ¿Qué tasa de cambio se debe aplicar a pagos en bolívares y quién mantiene
  esa tasa en Odoo?
- ¿Se deben adjuntar facturas u otros soportes a la solicitud?

### Lo que asumí para avanzar

- Los empleados autorizados reciben el grupo **Solicitante**. Una vez enviada,
  la solicitud no se edita; si hay que corregirla, se crea otra.
- Configuro niveles por compañía y moneda con un monto mínimo y una persona
  aprobadora. Se asigna el nivel con el monto mínimo más alto que no supere el
  monto solicitado. El módulo no decide por área: esa relación debe acordarse
  con Carolina y reflejarse en quién se configura como aprobador para cada
  nivel.
- No se puede aprobar ni rechazar la propia solicitud; solo la persona
  asignada puede hacerlo. El rechazo requiere un motivo que queda en el
  chatter.
- Tesorería registra un solo pago total desde un diario bancario o de caja.
  No incluí pagos parciales ni varios pagos para una solicitud.
- La solicitud conserva el monto y la moneda solicitados. Al pagar desde un
  diario en otra moneda, convierto el monto con la tasa registrada en Odoo
  para la fecha del pago y la compañía de la solicitud.
- No exigí adjuntos porque el correo no los pide; es una política que
  confirmaría antes de poner el flujo en producción.

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
