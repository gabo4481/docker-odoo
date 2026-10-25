# Prueba técnica — Desarrollador Odoo

Esta carpeta es el directorio de addons de la prueba. Aquí van los módulos que
entregues. `fleet_inspection` está migrado a Odoo 17 y sus tipos de vehículo
usan un catálogo con migración de los datos existentes.

| Carpeta | Qué contiene |
|---|---|
| `shop_integration_api` | **Ejercicio 1**: API de integración para consultar productos, crear cotizaciones y notificar entregas. |
| `fleet_inspection` | **Ejercicio 2**: inspecciones de flota migradas a Odoo 17, con catálogo de tipos de vehículo y migración de datos. |
| `sale_commission` | **Ejercicio 3**: comisión del vendedor por línea y por categoría. Revisa su historial con `git log -- src/custom/prueba-tecnica/sale_commission`. |
| `payment_request` | **Ejercicio 4**: solicitudes de pago y flujo de aprobación. |

## Levantar el entorno

1. Configura la instancia `prueba-tecnica` de Odoo 17 para que use esta carpeta
   como ruta de addons:

   ```jsonc
   "prueba-tecnica": {
     "odoo_version": "17.0",
     "external_port": 8073,
     "database": "v17-fleet-test",
     "odoo_config": "17.0_full",
     "overwrite_odoo_config": {
       "addons": ["src/custom/prueba-tecnica"],
       "db_filter": "^prueba",
       "max_cron_threads": 0,
       "dev_mode": true
     }
   }
   ```

   La instancia y la base PostgreSQL 16 dedicada ya están configuradas en este
   repositorio. No necesitas Odoo Enterprise.

2. Construye y levanta: `./odoo build` y `./odoo start`.
3. Corre las pruebas de los cuatro módulos juntos sobre una base nueva:

   ```bash
   ./odoo test -d prueba_limpia \
     -m shop_integration_api,fleet_inspection,sale_commission,payment_request
   ```

   Si el CLI pregunta por la instancia, elige `prueba-tecnica`. Los cuatro
   módulos están bajo la ruta de addons de esa instancia.

Más detalles del CLI en el `readme.md` de la raíz del repositorio.
