# Shop Integration API (Odoo 17)

Addon básico para la integración de la tienda con Odoo.

## Instalar y configurar

La instancia `prueba-tecnica` ya incluye este módulo en su ruta de addons.
Actualiza la lista de aplicaciones e instala **Shop Integration API** en Odoo.
El usuario de integración necesita permisos de ventas para crear cotizaciones.

Genera una API key global en las preferencias del usuario de Odoo. Odoo solo la
muestra al crearla; úsala en `Authorization: Bearer <API_KEY>`. La API key se
valida con el modelo nativo `res.users.apikeys` y no se guarda en el log.

Configura la URL destino del webhook en Parámetros del sistema:

- Clave: `shop_api.webhook_url`
- Valor: URL HTTPS de la tienda que recibirá el evento de entrega

Si no se configura esa URL, no se encolan ni se envían webhooks.

## Endpoints

La especificación completa está en [`openapi.yaml`](./openapi.yaml).

### Consultar productos

```bash
curl -H "Authorization: Bearer <API_KEY>" \
  "http://localhost:8073/api/v1/products?category_id=1&only_with_stock=true&page=1&limit=50"
```

Filtros opcionales: `category_id`, `only_with_stock` (`true`/`false`) y
`modified_since` (fecha ISO 8601). La respuesta incluye `total`, `page` y
`next` (número de la siguiente página o `null`).

### Crear una cotización

```bash
curl -X POST "http://localhost:8073/api/v1/orders" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Idempotency-Key: shop-order-100" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_rif": "J-12345678-0",
    "external_reference": "WEB-100",
    "lines": [{"default_code": "SHOP-001", "quantity": 2}]
  }'
```

El pedido se crea como cotización y no se confirma automáticamente. Si se
repite la misma clave con el mismo JSON, se devuelve la cotización original;
si cambia el JSON, se responde `409`.

Los errores usan `{"error":{"code":"...","field":"...","message":"..."}}`.
Cada solicitud, exitosa o fallida, registra endpoint, usuario si fue
autenticado, código HTTP y duración.

Al validar una entrega de venta, Odoo encola un evento. Un cron lo envía sin
bloquear la validación y reintenta hasta cinco veces después del envío inicial;
la espera crece de 5 a 60 minutos. El evento tiene `event`,
`external_reference`, `order` y `delivery`.

## Pruebas

Desde la raíz del repositorio, ejecuta
`./odoo test prueba-tecnica shop_integration_api`.

El nombre técnico cambió de `shop_api` a `shop_integration_api`. Para esta
versión, usa una base nueva; una base donde estuviera instalado el nombre
anterior requiere una migración aparte.
