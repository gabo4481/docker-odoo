from odoo import fields, models


class ShopApiCallLog(models.Model):
    _name = "shop.api.call.log"
    _description = "Shop API Call Log"
    _order = "create_date desc"

    endpoint = fields.Char(required=True, index=True)
    user_id = fields.Many2one("res.users", ondelete="set null", index=True)
    response_code = fields.Integer(required=True, index=True)
    duration_ms = fields.Float(required=True)


class ShopApiIdempotency(models.Model):
    _name = "shop.api.idempotency"
    _description = "Shop API Idempotency Key"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    key = fields.Char(required=True, index=True)
    payload_hash = fields.Char(required=True)
    order_id = fields.Many2one("sale.order", ondelete="set null")

    _sql_constraints = [
        (
            "user_key_unique",
            "unique(user_id, key)",
            "An idempotency key can only be used once per user.",
        ),
    ]
