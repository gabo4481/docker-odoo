# Plan de migración de `fleet_inspection`

## Alcance y decisión

La versión `17.0.2.0.0` convierte `fleet.inspection.vehicle_type` de selección
a `Many2one` sobre `fleet.inspection.vehicle.type`. Se conservan las claves:

| Valor anterior | Código del catálogo | Nombre |
|---|---|---|
| `motorcycle` | `motorcycle` | Moto |
| `car` | `car` | Carro |
| `truck` | `truck` | Camión |
| `other` | `other` | Otro |

El pre-script renombra la columna anterior y elimina sus metadatos de selección
obsoletos. El post-script lee y actualiza 1.000 inspecciones por iteración,
comprueba que cada clave tenga correspondencia y solo elimina la columna
temporal al completar el mapeo. Un valor desconocido detiene la actualización
con el ID de la inspección afectada.

## Evidencia de volumen y tiempo

Medición realizada el **25-10-2026** en una base temporal aislada: Odoo
17.0-20261019, PostgreSQL 16, módulo anterior `17.0.1.0.0`, 10.000 inspecciones
con 2.500 registros por cada código. El tiempo de pared de la orden Odoo
`-u fleet_inspection` fue **5,15 segundos**. El tiempo incluye el arranque y la
carga del registro de Odoo, pero no la generación de los datos ni el respaldo.
Es una medición local de referencia, no una garantía de duración en producción.

Para repetir el conjunto de datos en una base de ensayo con el módulo anterior
instalado y al menos un vehículo, se puede usar SQL. El ejemplo usa el primer
vehículo existente y el usuario administrador:

```sql
INSERT INTO fleet_inspection
    (name, vehicle_id, inspector_id, vehicle_type, state, date,
     create_uid, write_uid, create_date, write_date)
SELECT
    'MIG/20261025/' || lpad(n::text, 5, '0'),
    (SELECT id FROM fleet_vehicle ORDER BY id LIMIT 1),
    1,
    CASE n % 4
        WHEN 1 THEN 'motorcycle'
        WHEN 2 THEN 'car'
        WHEN 3 THEN 'truck'
        ELSE 'other'
    END,
    'draft',
    CURRENT_DATE,
    1,
    1,
    now(),
    now()
FROM generate_series(1, 10000) AS n;
```

El SQL inserta filas mínimas para medir esta conversión de datos; no crea líneas
de checklist. Para validar el comportamiento funcional, se ejecutan también
las pruebas del módulo.

## Ejecución en una base de producción

1. **Preparar y respaldar**
   - Programar una ventana de mantenimiento y detener escrituras de Odoo.
   - Confirmar el nombre de la base, el servicio PostgreSQL, usuario de respaldo
     y la ruta `data_dir` configurada para Odoo.
   - Guardar un dump verificable de PostgreSQL y una copia del filestore de esa
     base fuera del volumen que se va a actualizar:

     ```bash
     docker compose exec -T <servicio_postgres> \
       pg_dump -U <usuario_postgres> -Fc <nombre_base> \
       > <respaldo_seguro>/<nombre_base>-antes-fleet-inspection.dump
     ```

     Copiar también el directorio
     `<data_dir>/filestore/<nombre_base>` a `<respaldo_seguro>`.
   - Comprobar que el dump existe y que `pg_restore --list <archivo.dump>`
     puede leer su índice.

2. **Verificar antes de actualizar**
   - Confirmar en `ir_module_module` que `fleet_inspection` está instalado en
     `17.0.1.0.0`.
   - Guardar el total y la distribución original:

     ```sql
     SELECT count(*) FROM fleet_inspection;
     SELECT vehicle_type, count(*)
     FROM fleet_inspection
     GROUP BY vehicle_type
     ORDER BY vehicle_type;
     ```

   - Confirmar que no haya valores fuera de las cuatro claves esperadas:

     ```sql
     SELECT id, vehicle_type
     FROM fleet_inspection
     WHERE vehicle_type NOT IN ('motorcycle', 'car', 'truck', 'other')
     LIMIT 20;
     ```

     Si hay resultados, detenerse y revisar esos registros antes de actualizar.

3. **Actualizar**
   - Mantener detenidas las escrituras y ejecutar:

     ```bash
     ./odoo update <instancia> -d <nombre_base> -m fleet_inspection
     ```

   - Esperar código de salida exitoso y revisar el log de Odoo. Deben aparecer
     las etapas `pre-migration` y `post-migration` de `17.0.2.0.0`, sin
     excepciones.

4. **Verificar después**
   - Confirmar que el módulo quedó en `17.0.2.0.0`.
   - Confirmar que no hay inspecciones sin tipo:

     ```sql
     SELECT count(*)
     FROM fleet_inspection
     WHERE vehicle_type IS NULL;
     ```

     El resultado debe ser `0`.
   - Revisar la distribución migrada y compararla con la distribución guardada
     antes del cambio:

     ```sql
     SELECT t.code, count(*)
     FROM fleet_inspection i
     JOIN fleet_inspection_vehicle_type t ON t.id = i.vehicle_type
     GROUP BY t.code
     ORDER BY t.code;
     ```

     Deben coincidir el total y cada conteo por código; `other` debe seguir
     presente si existía antes.
   - Confirmar que la columna temporal `vehicle_type_legacy` ya no existe y
     probar una inspección de cada tipo desde la interfaz.

5. **Reversión**
   - Si falla la actualización o cualquier verificación, mantener Odoo detenido
     y restaurar **la base y el filestore juntos** desde el respaldo previo.
   - No intentar bajar el manifiesto ni ejecutar el módulo nuevo contra una base
     parcialmente migrada. Esta migración no ofrece una reversión automática
     del catálogo a selección; la recuperación soportada es restaurar el
     respaldo completo.

## Validación realizada

- Instalé `17.0.1.0.0` en una base temporal nueva, generé los 10.000 valores
  anteriores y ejecuté Odoo con `-u fleet_inspection`.
- Resultado: 10.000 filas en total; 2.500 por cada tipo; cero valores sin tipo;
  columna temporal eliminada y versión final `17.0.2.0.0`.
- La prueba automatizada `test_vehicle_type_migration_is_batched_and_idempotent`
  recorre los cuatro tipos usando lotes de dos filas y vuelve a ejecutar la
  función para comprobar que la segunda pasada no altera datos.
