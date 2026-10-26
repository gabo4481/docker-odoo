# Inspecciones de vehículos (`fleet_inspection`)

Módulo de inspecciones de flota para **Odoo 17**. Conserva el checklist, los
estados, los permisos por grupo, el aviso de inspecciones vencidas y el reporte
PDF. El tipo de vehículo se administra como catálogo y la migración conserva
los valores de las instalaciones de la versión anterior.

## Cambios de la migración

| Qué cambió | Por qué | Cómo lo resolví |
|---|---|---|
| Ubicación del módulo | La carpeta `prueba-tecnica-odoo16` no forma parte de los addons de la instancia Odoo 17. | Moví el addon a `src/custom/prueba-tecnica/fleet_inspection` y permití esa ruta en Git. |
| Versión del manifiesto | El manifiesto declaraba una versión de Odoo 16. | La migración a Odoo 17 quedó en `17.0.1.0.0`; subí a `17.0.2.0.0` al convertir el tipo de vehículo a catálogo. |
| Modificadores de campos y botones | Odoo 17 ya no admite `attrs` ni `states` en las vistas, y el parámetro Python `states` está obsoleto. | Reemplacé las condiciones por expresiones `readonly`, `required` e `invisible` en las vistas. |
| Nombre visible de la inspección | `name_get` está obsoleto en Odoo 17. | Implementé `_compute_display_name` y ajusté la prueba para verificar `display_name`. |
| Tipo de vehículo | La selección limita las opciones a valores escritos en el código. | Añadí el catálogo `fleet.inspection.vehicle.type`, sus cuatro registros iniciales y el campo `Many2one`. |
| Datos existentes | Al convertir selección a relación, los textos no son identificadores de catálogo. | La migración `17.0.2.0.0` conserva temporalmente la columna anterior y asigna cada valor al tipo equivalente. |
| Volumen e idempotencia | La migración debe poder repetirse y no cargar todas las filas en memoria. | Procesa 1.000 filas por lote, valida valores desconocidos y retira la columna temporal al terminar. La prueba la ejecuta dos veces con lotes de dos registros. |
| Medición | El tiempo de una actualización grande debe medirse, no estimarse. | En una base de ensayo Odoo 17 con 10.000 filas, el `-u fleet_inspection` tardó 5,15 s el 25-10-2026; los datos y el plan están en [`MIGRATION_PLAN.md`](./MIGRATION_PLAN.md). |

## Tramos completados

- **A:** migré el módulo de Odoo 16 a Odoo 17 y conservé sus inspecciones,
  checklist, estados, permisos, avisos y reporte.
- **B:** convertí el tipo de vehículo en un catálogo y añadí la migración de
  `motorcycle`, `car`, `truck` y `other`.
- **C:** la migración procesa lotes de 1.000 registros y la prueba verifica que
  repetirla no cambie el resultado. La actualización con 10.000 inspecciones
  se midió en 5,15 segundos en el entorno descrito en
  [`MIGRATION_PLAN.md`](./MIGRATION_PLAN.md).

## Instalar y probar

Configura una instancia Odoo 17 que incluya `src/custom/prueba-tecnica` en su
`addons_path`. El módulo depende de `fleet` y `mail`, incluidos en Odoo.

```bash
./odoo test prueba-tecnica fleet_inspection
```

Para actualizar una base instalada con la versión anterior:

```bash
./odoo update prueba-tecnica -d <nombre_base> -m fleet_inspection
```

Antes de actualizar una base de cliente, sigue el respaldo, las verificaciones
y la reversión descritos en [`MIGRATION_PLAN.md`](./MIGRATION_PLAN.md).

## Supuestos y limitaciones

- Conservé los cuatro valores de tipo anteriores y asigné nombres visibles en
  español al catálogo.
- La migración espera que la columna anterior contenga solo
  `motorcycle`, `car`, `truck` u `other`. Si encuentra otro valor, detiene la
  actualización para que se revise en lugar de asignar un tipo incorrecto.
- La medición de 5,15 segundos corresponde al equipo y la base temporal del
  plan; no garantiza la misma duración en otra infraestructura.
