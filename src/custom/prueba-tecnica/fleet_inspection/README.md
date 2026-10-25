# Inspecciones de vehículos (`fleet_inspection`)

Módulo de inspecciones de flota migrado a **Odoo 17**. Conserva el checklist,
los estados, los permisos por grupo, el aviso de inspecciones vencidas y el
reporte PDF. En este tramo, el tipo de vehículo sigue siendo una selección;
el paso a catálogo corresponde al Tramo B.

## Cambios de la migración

| Qué cambió | Por qué | Cómo lo resolví |
|---|---|---|
| Ubicación del módulo | La carpeta `prueba-tecnica-odoo16` no forma parte de los addons de la instancia Odoo 17. | Moví el addon a `src/custom/prueba-tecnica/fleet_inspection` y permití esa ruta en Git. |
| Versión del manifiesto | El manifiesto declaraba una versión de Odoo 16. | Actualicé la versión del módulo a `17.0.1.0.0`. |
| Modificadores de campos y botones | Odoo 17 ya no admite `attrs` ni `states` en las vistas, y el parámetro Python `states` está obsoleto. | Reemplacé las condiciones por expresiones `readonly`, `required` e `invisible` en las vistas. |
| Nombre visible de la inspección | `name_get` está obsoleto en Odoo 17. | Implementé `_compute_display_name` y ajusté la prueba para verificar `display_name`. |

## Instalar y probar

Configura una instancia Odoo 17 que incluya `src/custom/prueba-tecnica` en su
`addons_path`. El módulo depende de `fleet` y `mail`, incluidos en Odoo.

```bash
./odoo test prueba-tecnica fleet_inspection
```
