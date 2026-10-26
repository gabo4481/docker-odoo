# AI_LOG — shop_integration_api

## Herramientas

- GitHub Copilot en VS Code.
- Pruebas `HttpCase` del entorno Odoo 17 para validar la implementación.

## Prompts clave

1. Revisar el estado del repositorio y confirmar dónde debía ir el módulo para la instancia Odoo 17.
   - El módulo quedó dentro de `src/custom/prueba-tecnica`, junto con los otros ejercicios.
2. Preparar un plan MVP sencillo para cubrir los requisitos del ejercicio.
   - Se propuso separar el trabajo en consulta de productos, pedidos, autenticación, registro, idempotencia, webhook, documentación y pruebas.
3. Implementar el alcance básico del ejercicio en el módulo `shop_integration_api`.
   - Copilot ayudó a crear el esqueleto del addon, los endpoints, modelos, pruebas `HttpCase`, README y `openapi.yaml`. La implementación se revisó y se corrigió usando los resultados de las pruebas.
4. Contrastar después la implementación con los criterios de aceptación.
   - La revisión identificó que las pruebas no demostraban el conteo de consultas SQL ni el encolado al validar una entrega real; añadí esas verificaciones y las ejecuté en Odoo 17.

## Lo que la IA hizo mal o quedó incompleto

- En la primera versión de las pruebas, la API key se generaba para el usuario interno especial de Odoo. Las llamadas HTTP devolvían `401`; se detectó al ejecutar `HttpCase` y se corrigió usando un usuario activo de integración.
- La primera prueba de stock usaba un producto consumible; Odoo 17 no permite crear quants para ese tipo. El error apareció al correr los tests y se corrigió usando un producto almacenable.
- La prueba inicial de stock solo contaba llamadas al helper, por lo que no demostraba la cantidad de consultas SQL. La reemplacé por una comparación del contador SQL del cursor con 1 y 21 productos.
- La prueba inicial del webhook solo comprobaba el reintento de un trabajo ya encolado. Añadí una prueba que confirma un pedido, valida su entrega real y comprueba que el evento queda encolado sin hacer una llamada HTTP durante la validación.

## Lo que escribiste tú sin IA

- Yo definí el alcance del MVP, elegí Odoo 17 y decidí que el pedido se cree como cotización.
- Revisé manualmente la configuración de la instancia y el destino de los cuatro módulos; mantuve los ajustes de entorno fuera de los cambios del addon.
- Revisé las respuestas de la API y el resultado de las pruebas antes de aceptar los cambios. Copilot fue apoyo de implementación, revisión y verificación; no dejé las decisiones sin supervisión.
