# Incidente T-200 — vendedores no pueden confirmar pedidos

## Resumen

Tras desplegar `sale_commission` 1.1.0, los vendedores recibían un error al
confirmar pedidos. El gerente podía confirmarlos. El modelo de reglas de
comisión no tenía permiso de lectura para vendedores, aunque el código nuevo
consultaba ese modelo durante la confirmación.

La revisión también encontró que, si no había una regla aplicable por
categoría, la comisión se tomaba del usuario que confirmaba y no del vendedor
asignado al pedido. Por eso los pedidos que el gerente confirmó pueden tener
una comisión diferente a la esperada.

## Cómo reproducir

1. Instalar `sale_commission` 1.1.0.
2. Usar un usuario con `sales_team.group_sale_salesman`, sin el grupo de
   gerente.
3. Crear un pedido con una línea y confirmarlo.
4. Si no hay regla de categoría, el vendedor recibe un `AccessError` al
   consultar `sale.commission.rule`.
5. Al repetir la confirmación como gerente, no hay error de permisos; si no
   existe una regla aplicable, la comisión puede quedar con el porcentaje del
   gerente en lugar del vendedor del pedido.

Las pruebas `test_salesman_can_confirm_order_without_manager_access` y
`test_manager_confirmation_uses_assigned_salesman_commission` fallaron antes
del cambio: la primera recibió el error de acceso de `sale.commission.rule`;
la segunda obtuvo 25 % en vez del 5 % asignado al vendedor.

## Causa raíz y corrección

El commit que introdujo el problema en el código fue **`8a1581f`** (`[FEAT]
sale_commission: porcentaje de comisión por categoría de producto`). Añadió la
búsqueda de `sale.commission.rule` al confirmar, pero solo declaró acceso para
gerentes. También cambió el porcentaje de respaldo de `order_id.user_id` a
`env.user`.

La corrección es acotada:

- Di al grupo de vendedores permiso **solo de lectura** sobre las reglas. No
  les di permisos de gerente, escritura, creación ni eliminación. Una regla
  limita la lectura a compañías permitidas y reglas compartidas.
- Cuando no aplica una regla de categoría, uso el porcentaje del vendedor
  asignado al pedido, aunque otra persona lo confirme.
- El botón *Recalcular comisiones* también consulta el mismo modelo y está
  disponible en el formulario del pedido. El permiso de lectura resuelve el
  mismo error allí.

La revisión no detectó el fallo porque las pruebas confirmaban los pedidos con
el usuario de pruebas, no con el vendedor. En el commit de la regla por
categoría también se quitó el `with_user(user)` de la creación de pedidos de
prueba. Faltaba una prueba de confirmación con un vendedor sin permisos de
gerente.

## Contención durante los primeros 15 minutos

Antes de tener la corrección lista, mantendría la entrada de pedidos y dejaría
temporalmente al gerente confirmarlos, siempre verificando que cada pedido
conserve asignado a su vendedor real. Anotaría los pedidos confirmados durante
la contingencia y pausaría el cierre o pago de comisiones hasta revisar sus
porcentajes. No cambiaría porcentajes de usuarios ni reglas para ocultar el
error.

Esto permite seguir vendiendo y se puede dejar de hacer en cuanto se instale
la corrección. El riesgo es que los reportes de comisión sean temporalmente
incorrectos, que haya que revisar pedidos uno por uno y que el gerente se
convierta en un cuello de botella. La consulta de
[`scripts/audit_t200_commissions.sql`](./scripts/audit_t200_commissions.sql)
lista candidatos, no confirma por sí sola que un pedido deba cambiarse.

## Revisión de datos y corrección

El script SQL es de solo lectura. Compara la comisión guardada con la regla
vigente más específica y, cuando no hay regla, con el porcentaje actual del
vendedor asignado. Lista pedidos confirmados cuyo último escritor no es el
vendedor y cuyo porcentaje no coincide con ese cálculo.

Los resultados son **candidatos**, porque el último escritor puede haber
cambiado después de la confirmación y las reglas o porcentajes actuales podrían
ser distintos de los que existían esa tarde. Para cada candidato:

1. Comparar el pedido y su fecha de confirmación con el registro de ventas de
   la contingencia y el historial disponible en Odoo.
2. Confirmar con Comercial el vendedor responsable, el porcentaje acordado en
   la fecha del pedido y si había una regla de categoría aplicable.
3. Registrar el pedido, valor actual, valor aprobado y responsable de la
   revisión. No modificar pedidos que no se puedan verificar.
4. Con autorización de Comercial, corregir los porcentajes de las líneas
   afectadas desde Odoo con un usuario autorizado y recalcular la comisión.
   Volver a consultar el pedido y el reporte de comisiones para comprobar el
   resultado. No ejecutar actualizaciones SQL para cambiar importes.

## Despliegue y verificación

1. Hacer respaldo de la base y del filestore, y desplegar el commit del hotfix
   aprobado por el pull request en la instancia afectada.
2. Actualizar **solo** `sale_commission`:

   ```bash
   ./odoo update prueba-tecnica -d <base> -m sale_commission
   ```

3. Revisar que la actualización termine sin errores y que los vendedores sigan
   teniendo solo lectura en las reglas.
4. Probar con un vendedor sin grupo de gerente: confirmar un pedido con una
   regla de categoría y otro sin ella. Comprobar el porcentaje y el importe.
5. Probar con un gerente un pedido asignado a otro vendedor y confirmar que se
   aplica la comisión del vendedor asignado. Verificar también el reporte.
6. Ejecutar `./odoo test prueba-tecnica sale_commission` y revisar
   `scripts/audit_t200_commissions.sql` con Comercial antes de normalizar el
   cierre de comisiones.

## Mensaje al cliente

Identificamos por qué los vendedores no podían confirmar pedidos y ya preparamos una corrección.

Mientras la instalamos, el gerente puede seguir confirmando y dejando cada pedido a nombre de su vendedor.

Revisaremos las comisiones de los pedidos de hoy antes de cerrar el reporte.

Les confirmaremos cuando la corrección esté instalada y probada.

## Prevención

- Toda búsqueda de un modelo nuevo debe incluir una revisión de sus permisos
  de lectura para cada grupo que ejecute esa búsqueda.
- Añadir una prueba que confirme un pedido con `with_user(vendedor)` y otra
  donde el gerente confirme un pedido asignado a un vendedor distinto.
- En revisión de código, comprobar que las pruebas de permisos no ejecuten
  acciones como administrador y que las comisiones usen al vendedor del pedido,
  no al usuario que inició la acción.
