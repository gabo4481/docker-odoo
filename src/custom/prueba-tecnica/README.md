# Prueba técnica — Desarrollador Odoo

Esta carpeta es el directorio de addons de la prueba. Aquí van los módulos que
entregues. `fleet_inspection` está migrado a Odoo 17; el cambio de tipo de
vehículo de selección a catálogo corresponde al Tramo B.

| Carpeta | Qué contiene |
|---|---|
| `src/custom/prueba-tecnica/fleet_inspection` | **Ejercicio 2**: inspecciones de flota migradas a Odoo 17. El paso de `Selection` a catálogo queda para el Tramo B. |
| `src/custom/prueba-tecnica/sale_commission` | **Ejercicio 3**: comisión del vendedor por línea y por categoría. Revisa su historial con `git log -- src/custom/prueba-tecnica/sale_commission`. |

## Levantar el entorno

1. Copia `instances.example.jsonc` a `instances.json` y agrega una instancia que use esta carpeta como addons
   (cambia la versión por la que elijas: 17.0, 18.0 o 19.0):

   ```jsonc
   "prueba-tecnica": {
     "odoo_version": "17.0",
     "external_port": 8073,
     "database": "v17",
     "odoo_config": "17.0_full",
     "overwrite_odoo_config": {
       "addons": ["src/custom/prueba-tecnica"],
       "dev_mode": true
     }
   }
   ```

   La configuración local de este repositorio ya incluye `17.0_full` y `v17`.
   No necesitas Odoo Enterprise.

2. Construye y levanta: `./odoo build` y `./odoo start`.
3. Corre las pruebas de cada módulo, por ejemplo:

   ```bash
   ./odoo test prueba-tecnica fleet_inspection
   ./odoo test prueba-tecnica sale_commission
   ```

Más detalles del CLI en el `readme.md` de la raíz del repositorio.
