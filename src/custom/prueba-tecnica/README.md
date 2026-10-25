# Prueba técnica — Desarrollador Odoo

Esta carpeta es el directorio de addons de la prueba. Aquí van los módulos que
entregues. `fleet_inspection` está migrado a Odoo 17 y sus tipos de vehículo
usan un catálogo con migración de los datos existentes.

| Carpeta | Qué contiene |
|---|---|
| `src/custom/client-b/shop_integration_api` | **Ejercicio 1**: API de integración para consultar productos, crear cotizaciones y notificar entregas. |
| `src/custom/prueba-tecnica/fleet_inspection` | **Ejercicio 2**: inspecciones de flota migradas a Odoo 17. El paso de `Selection` a catálogo queda para el Tramo B. |
| `src/custom/prueba-tecnica/sale_commission` | **Ejercicio 3**: comisión del vendedor por línea y por categoría. Revisa su historial con `git log -- src/custom/prueba-tecnica/sale_commission`. |
| `src/custom/client-b/payment_request` | **Ejercicio 4**: solicitudes de pago y flujo de aprobación. |

## Levantar el entorno

1. Copia `instances.example.jsonc` a `instances.json` y agrega una instancia que use esta carpeta como addons
   (cambia la versión por la que elijas: 17.0, 18.0 o 19.0):

   ```jsonc
   "prueba-tecnica": {
     "odoo_version": "17.0",
     "external_port": 8073,
     "database": "v17-fleet-test",
     "odoo_config": "17.0_full",
     "overwrite_odoo_config": {
       "addons": ["src/custom/prueba-tecnica", "src/custom/client-b"],
       "db_filter": "^prueba",
       "max_cron_threads": 0,
       "dev_mode": true
     }
   }
   ```

   Define `v17-fleet-test` en `databases` como un servicio PostgreSQL 16 dedicado,
   con un puerto libre y `expose_host_port: false`. No reutilices `v17` mientras
   `client-b` lo use, salvo que configures aislamiento de PostgreSQL para ambas
   instancias. `17.0_full` ya está definido en la configuración del repositorio.
   No necesitas Odoo Enterprise.

2. Construye y levanta: `./odoo build` y `./odoo start`.
3. Corre las pruebas de cada módulo, por ejemplo:

   ```bash
   ./odoo test -d prueba_limpia \
     -m shop_integration_api,fleet_inspection,sale_commission,payment_request
   ```

   Si el CLI pregunta por la instancia, elige `prueba-tecnica`. La base nueva
   ejecuta juntas las pruebas de los cuatro módulos en Odoo 17.

Más detalles del CLI en el `readme.md` de la raíz del repositorio.
