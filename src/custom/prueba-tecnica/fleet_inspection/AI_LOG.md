# AI_LOG — fleet_inspection

## Herramientas
- Usé Copilot en VS Code como apoyo para revisar, corregir y probar el módulo.

## Prompts clave

1. Le pedí ayuda para migrar el módulo a Odoo 17 y revisar qué faltaba.
2. Le pedí cambiar el tipo de vehículo a un catálogo y conservar los datos existentes.
3. Le pedí preparar pruebas para los cuatro tipos y comprobar la actualización con 10.000 inspecciones.
4. Le pedí documentar los pasos para respaldar, actualizar, verificar y revertir.

Revisé los cambios y confirmé el resultado ejecutando la instalación, la actualización y las pruebas.

## Lo que la IA hizo mal

- En los primeros intentos, la actualización falló porque el catálogo todavía no estaba disponible cuando Odoo cargaba el valor por defecto. Lo detecté al probar la actualización y ajusté el código antes de continuar.

## Lo que hice yo

- Yo revisé los requisitos, preparé los datos de prueba y ejecuté manualmente la actualización con 10.000 inspecciones.
- También revisé los resultados, comprobé que los cuatro tipos se conservaran y decidí qué cambios dejar en el módulo.
- Usé la IA como apoyo; no dejé el trabajo sin revisar ni validar.
