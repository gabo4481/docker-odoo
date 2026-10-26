# Shop Integration API (Odoo 17)

Addon para que una tienda consulte productos y cree cotizaciones en Odoo.

## Tramos completados

- **A:** `GET /api/v1/products` devuelve productos activos y vendibles, con
  categoría, stock y fecha de modificación como filtros.
- **B:** autentica con API keys nativas de Odoo, registra llamadas y crea
  cotizaciones. Los errores indican un código y el campo que debe corregirse.
- **C:** incluye paginación, idempotencia, consulta agrupada de stock y
  notificaciones webhook de entrega con reintentos.

## Instalar y configurar

La instancia `prueba-tecnica` ya incluye este módulo en su ruta de addons.
Actualiza la lista de aplicaciones e instala **Shop Integration API** en Odoo.
El usuario de integración necesita permisos de ventas para crear cotizaciones.

Genera una API key global en las preferencias del usuario de Odoo. Odoo solo la
muestra al crearla; envíala en la cabecera `Authorization` con el esquema
`Bearer`. Se valida con `res.users.apikeys` y no se guarda en el log.

Configura la URL HTTPS destino del webhook en Parámetros del sistema:

- Clave: `shop_api.webhook_url`
- Valor: URL de la tienda que recibirá el evento de entrega

Si no se configura esa URL, no se encolan ni se envían webhooks.

## Endpoints

La especificación completa está en [`openapi.yaml`](./openapi.yaml).

### Consultar productos

```bash
curl -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8073/api/v1/products?category_id=1&only_with_stock=true&page=1&limit=50"
```

Filtros opcionales: `category_id`, `only_with_stock` (`true`/`false`) y
`modified_since` (fecha ISO 8601). La respuesta incluye `total`, `page` y
`next` (número de la siguiente página o `null`).

### Crear una cotización

```bash
curl -X POST "http://localhost:8073/api/v1/orders" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Idempotency-Key: shop-order-100" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_rif": "J-12345678-0",
    "external_reference": "WEB-100",
    "lines": [{"default_code": "SHOP-001", "quantity": 2}]
  }'
```

El pedido se crea como cotización y no se confirma automáticamente. Si se
repite la misma clave y contenido, se devuelve el pedido original; si cambia
el contenido, se responde `409`.

### Errores

Los errores usan este formato:

```json
{
  "error": {
    "code": "PRODUCT_NOT_FOUND",
    "field": "lines[1].default_code",
    "message": "No existe un producto con el código ABC-123"
  }
}
```

| HTTP | Cuándo se devuelve |
|---|---|
| `400` | JSON inválido o falta `Idempotency-Key`. |
| `401` | No se envía una API key válida. |
| `409` | Se reutiliza una clave de idempotencia con contenido diferente. |
| `422` | Un filtro, fecha, RIF, producto, cantidad u otro dato no es válido. |

Cada solicitud, exitosa o fallida, registra endpoint, usuario si fue
autenticado, código HTTP y duración. El registro no guarda la API key.

Al validar una entrega de venta, Odoo encola un evento. Un cron lo envía sin
bloquear la validación y reintenta hasta cinco veces después del envío inicial;
la espera crece de 5 a 60 minutos. El evento tiene `event`,
`external_reference`, `order` y `delivery`.

## Cómo probar

Desde la raíz del repositorio:

```bash
./odoo test prueba-tecnica shop_integration_api
```

La prueba de stock compara el contador SQL al consultar 1 y 21 productos; la
prueba de entrega confirma un pedido, valida su picking y verifica que el
webhook se encole sin hacer una petición HTTP durante la validación.

La prueba conjunta de los cuatro módulos está en
[`../README.md`](../README.md). El nombre técnico cambió de `shop_api` a
`shop_integration_api`; una base con el módulo anterior requiere una migración
de nombre aparte, por lo que las pruebas se ejecutan en una base nueva.

## Supuestos y limitaciones

- La API usa una API key global de un usuario de Odoo con permisos suficientes
  para consultar productos y crear cotizaciones.
- El RIF debe coincidir con el campo de identificación fiscal del contacto;
  los productos se buscan por su referencia interna (`default_code`).
- El pedido queda como cotización para que Ventas lo revise antes de
  confirmarlo.
- La URL destino del webhook se configura en `shop_api.webhook_url`. Si no se
  configura, el módulo no envía avisos.
- El cambio de nombre técnico no migra automáticamente instalaciones que aún
  tengan `shop_api` instalado.
