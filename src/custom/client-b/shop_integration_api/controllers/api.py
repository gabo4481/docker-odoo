import hashlib
import json
import math
import time
from datetime import datetime, timezone

from psycopg2.errors import UniqueViolation

from odoo import fields, http
from odoo.http import request


PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 100


def _error(code, field, message):
    return {"error": {"code": code, "field": field, "message": message}}


class ShopApiController(http.Controller):
    def _response(self, status, payload):
        response = request.make_response(
            json.dumps(payload, ensure_ascii=False),
            headers=[("Content-Type", "application/json; charset=utf-8")],
        )
        response.status_code = status
        return response

    def _log_and_respond(self, endpoint, started_at, status, payload, user_id=None):
        duration_ms = (time.perf_counter() - started_at) * 1000
        request.env["shop.api.call.log"].sudo().create(
            {
                "endpoint": endpoint,
                "user_id": user_id,
                "response_code": status,
                "duration_ms": duration_ms,
            }
        )
        return self._response(status, payload)

    def _authenticate(self):
        authorization = request.httprequest.headers.get("Authorization", "")
        scheme, separator, key = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not key.strip():
            return None
        user_id = request.env["res.users.apikeys"].sudo()._check_credentials(
            scope="rpc",
            key=key.strip(),
        )
        if user_id:
            request.update_env(user=user_id)
            return user_id
        return None

    def _read_json_body(self):
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, _error("INVALID_JSON", None, "El cuerpo debe contener JSON válido")
        if not isinstance(payload, dict):
            return None, _error("INVALID_JSON", None, "El cuerpo debe ser un objeto JSON")
        return payload, None

    def _available_quantities(self, products):
        quantities = {}
        if not products:
            return quantities

        groups = request.env["stock.quant"].sudo().read_group(
            [
                ("product_id", "in", products.ids),
                ("location_id.usage", "=", "internal"),
                ("company_id", "=", request.env.company.id),
            ],
            ["quantity:sum", "reserved_quantity:sum"],
            ["product_id"],
            lazy=False,
        )
        for group in groups:
            product = group.get("product_id")
            if product:
                quantities[product[0]] = max(
                    0.0,
                    (group.get("quantity") or 0.0)
                    - (group.get("reserved_quantity") or 0.0),
                )
        return quantities

    @http.route(
        "/api/v1/products",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_products(self, **kwargs):
        started_at = time.perf_counter()
        user_id = self._authenticate()
        if not user_id:
            return self._log_and_respond(
                "/api/v1/products",
                started_at,
                401,
                _error(
                    "AUTHENTICATION_REQUIRED",
                    "Authorization",
                    "Envía una API key válida en Authorization: Bearer.",
                ),
            )

        args = request.httprequest.args
        domain = [
            ("active", "=", True),
            ("sale_ok", "=", True),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", request.env.company.id),
        ]

        category_id = args.get("category_id")
        if category_id:
            try:
                category_id = int(category_id)
            except ValueError:
                return self._log_and_respond(
                    "/api/v1/products",
                    started_at,
                    422,
                    _error(
                        "INVALID_CATEGORY",
                        "category_id",
                        "category_id debe ser un identificador numérico.",
                    ),
                    user_id,
                )
            if category_id <= 0:
                return self._log_and_respond(
                    "/api/v1/products",
                    started_at,
                    422,
                    _error(
                        "INVALID_CATEGORY",
                        "category_id",
                        "category_id debe ser mayor que cero.",
                    ),
                    user_id,
                )
            domain.append(("categ_id", "=", category_id))

        only_with_stock = args.get("only_with_stock", "false").lower()
        if only_with_stock not in ("true", "false", "1", "0"):
            return self._log_and_respond(
                "/api/v1/products",
                started_at,
                422,
                _error(
                    "INVALID_STOCK_FILTER",
                    "only_with_stock",
                    "Usa true, false, 1 o 0.",
                ),
                user_id,
            )
        only_with_stock = only_with_stock in ("true", "1")

        modified_since = args.get("modified_since")
        if modified_since:
            try:
                parsed_date = datetime.fromisoformat(
                    modified_since.replace("Z", "+00:00")
                )
            except ValueError:
                return self._log_and_respond(
                    "/api/v1/products",
                    started_at,
                    422,
                    _error(
                        "INVALID_DATE",
                        "modified_since",
                        "Usa una fecha ISO 8601, por ejemplo 2025-01-31T10:00:00Z.",
                    ),
                    user_id,
                )
            if parsed_date.tzinfo:
                parsed_date = parsed_date.astimezone(timezone.utc).replace(tzinfo=None)
            domain.append(("write_date", ">=", fields.Datetime.to_string(parsed_date)))

        try:
            page = int(args.get("page", "1"))
            limit = int(args.get("limit", str(PAGE_SIZE_DEFAULT)))
        except ValueError:
            return self._log_and_respond(
                "/api/v1/products",
                started_at,
                422,
                _error("INVALID_PAGINATION", "page", "page y limit deben ser números."),
                user_id,
            )
        if page < 1 or limit < 1 or limit > PAGE_SIZE_MAX:
            return self._log_and_respond(
                "/api/v1/products",
                started_at,
                422,
                _error(
                    "INVALID_PAGINATION",
                    "page",
                    f"page debe ser positivo y limit debe estar entre 1 y {PAGE_SIZE_MAX}.",
                ),
                user_id,
            )

        products = request.env["product.product"].search(domain, order="id")
        quantities = self._available_quantities(products)
        if only_with_stock:
            products = products.filtered(lambda product: quantities.get(product.id, 0) > 0)

        total = len(products)
        page_products = products[(page - 1) * limit : page * limit]
        result = [
            {
                "id": product.id,
                "default_code": product.default_code or "",
                "name": product.name,
                "price": product.list_price,
                "available_quantity": quantities.get(product.id, 0.0),
            }
            for product in page_products
        ]
        return self._log_and_respond(
            "/api/v1/products",
            started_at,
            200,
            {
                "products": result,
                "total": total,
                "page": page,
                "next": page + 1 if page * limit < total else None,
            },
            user_id,
        )

    @http.route(
        "/api/v1/orders",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def create_order(self, **kwargs):
        started_at = time.perf_counter()
        user_id = self._authenticate()
        if not user_id:
            return self._log_and_respond(
                "/api/v1/orders",
                started_at,
                401,
                _error(
                    "AUTHENTICATION_REQUIRED",
                    "Authorization",
                    "Envía una API key válida en Authorization: Bearer.",
                ),
            )

        payload, body_error = self._read_json_body()
        if body_error:
            return self._log_and_respond(
                "/api/v1/orders", started_at, 400, body_error, user_id
            )

        idempotency_key = request.httprequest.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return self._log_and_respond(
                "/api/v1/orders",
                started_at,
                400,
                _error(
                    "IDEMPOTENCY_KEY_REQUIRED",
                    "Idempotency-Key",
                    "La cabecera Idempotency-Key es obligatoria.",
                ),
                user_id,
            )

        try:
            canonical_payload = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except ValueError:
            return self._log_and_respond(
                "/api/v1/orders",
                started_at,
                400,
                _error("INVALID_JSON", None, "El cuerpo contiene un número JSON inválido."),
                user_id,
            )
        payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        idempotency_model = request.env["shop.api.idempotency"].sudo()
        existing = idempotency_model.search(
            [("user_id", "=", user_id), ("key", "=", idempotency_key)],
            limit=1,
        )
        if existing:
            if existing.payload_hash != payload_hash:
                return self._log_and_respond(
                    "/api/v1/orders",
                    started_at,
                    409,
                    _error(
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key",
                        "Esta clave ya fue usada con un contenido diferente.",
                    ),
                    user_id,
                )
            order = existing.order_id
            if order:
                return self._log_and_respond(
                    "/api/v1/orders",
                    started_at,
                    200,
                    {
                        "id": order.id,
                        "name": order.name,
                        "state": order.state,
                    },
                    user_id,
                )

        rif = payload.get("customer_rif")
        if not isinstance(rif, str) or not rif.strip():
            return self._log_and_respond(
                "/api/v1/orders",
                started_at,
                422,
                _error("CUSTOMER_RIF_REQUIRED", "customer_rif", "Indica el RIF del cliente."),
                user_id,
            )
        external_reference = payload.get("external_reference")
        if not isinstance(external_reference, str) or not external_reference.strip():
            return self._log_and_respond(
                "/api/v1/orders",
                started_at,
                422,
                _error(
                    "EXTERNAL_REFERENCE_REQUIRED",
                    "external_reference",
                    "Indica la referencia externa del pedido.",
                ),
                user_id,
            )
        lines = payload.get("lines")
        if not isinstance(lines, list) or not lines:
            return self._log_and_respond(
                "/api/v1/orders",
                started_at,
                422,
                _error("LINES_REQUIRED", "lines", "Incluye al menos una línea."),
                user_id,
            )

        requested_lines = []
        for index, line in enumerate(lines):
            if not isinstance(line, dict):
                return self._log_and_respond(
                    "/api/v1/orders",
                    started_at,
                    422,
                    _error("INVALID_LINE", f"lines[{index}]", "La línea debe ser un objeto."),
                    user_id,
                )
            code = line.get("default_code")
            if not isinstance(code, str) or not code.strip():
                return self._log_and_respond(
                    "/api/v1/orders",
                    started_at,
                    422,
                    _error(
                        "PRODUCT_CODE_REQUIRED",
                        f"lines[{index}].default_code",
                        "Indica el código del producto.",
                    ),
                    user_id,
                )
            quantity = line.get("quantity")
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                quantity = 0
            if not math.isfinite(quantity) or quantity <= 0:
                return self._log_and_respond(
                    "/api/v1/orders",
                    started_at,
                    422,
                    _error(
                        "INVALID_QUANTITY",
                        f"lines[{index}].quantity",
                        "La cantidad debe ser mayor que cero.",
                    ),
                    user_id,
                )
            requested_lines.append((code.strip(), quantity))

        partner = request.env["res.partner"].search(
            [("vat", "=", rif.strip())],
            limit=1,
        )
        if not partner:
            return self._log_and_respond(
                "/api/v1/orders",
                started_at,
                422,
                _error("CUSTOMER_NOT_FOUND", "customer_rif", f"No existe un cliente con RIF {rif}."),
                user_id,
            )

        product_codes = list({code for code, quantity in requested_lines})
        products = request.env["product.product"].search(
            [
                ("default_code", "in", product_codes),
                ("active", "=", True),
                ("sale_ok", "=", True),
            ]
        )
        products_by_code = {product.default_code: product for product in products}
        order_line_values = []
        for index, (code, quantity) in enumerate(requested_lines):
            product = products_by_code.get(code)
            if not product:
                return self._log_and_respond(
                    "/api/v1/orders",
                    started_at,
                    422,
                    _error(
                        "PRODUCT_NOT_FOUND",
                        f"lines[{index}].default_code",
                        f"No existe un producto con el código {code}.",
                    ),
                    user_id,
                )
            order_line_values.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_uom": product.uom_id.id,
                        "product_uom_qty": quantity,
                        "price_unit": product.list_price,
                    },
                )
            )

        try:
            with request.env.cr.savepoint():
                order = request.env["sale.order"].create(
                    {
                        "partner_id": partner.id,
                        "client_order_ref": external_reference.strip(),
                        "order_line": order_line_values,
                    }
                )
                idempotency_model.create(
                    {
                        "user_id": user_id,
                        "key": idempotency_key,
                        "payload_hash": payload_hash,
                        "order_id": order.id,
                    }
                )
        except UniqueViolation as error:
            if error.diag.constraint_name != "shop_api_idempotency_user_key_unique":
                raise
            existing = idempotency_model.search(
                [("user_id", "=", user_id), ("key", "=", idempotency_key)],
                limit=1,
            )
            if existing and existing.payload_hash == payload_hash and existing.order_id:
                order = existing.order_id
                return self._log_and_respond(
                    "/api/v1/orders",
                    started_at,
                    200,
                    {"id": order.id, "name": order.name, "state": order.state},
                    user_id,
                )
            return self._log_and_respond(
                "/api/v1/orders",
                started_at,
                409,
                _error(
                    "IDEMPOTENCY_CONFLICT",
                    "Idempotency-Key",
                    "Esta clave ya fue usada con un contenido diferente.",
                ),
                user_id,
            )

        return self._log_and_respond(
            "/api/v1/orders",
            started_at,
            201,
            {"id": order.id, "name": order.name, "state": order.state},
            user_id,
        )
