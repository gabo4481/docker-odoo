import json

import requests

from odoo import fields, models


class ShopApiWebhookJob(models.Model):
    _name = "shop.api.webhook.job"
    _description = "Shop API Delivery Webhook"
    _order = "create_date"

    picking_id = fields.Many2one("stock.picking", required=True, ondelete="cascade")
    payload = fields.Text(required=True)
    state = fields.Selection(
        [("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")],
        default="pending",
        required=True,
        index=True,
    )
    attempts = fields.Integer(default=0, required=True)
    next_retry_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    last_error = fields.Text()

    _sql_constraints = [
        ("picking_unique", "unique(picking_id)", "A delivery can only be queued once."),
    ]

    def process_pending(self):
        webhook_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("shop_api.webhook_url")
        )
        if not webhook_url:
            return

        jobs = self.sudo().search(
            [
                ("state", "=", "pending"),
                ("next_retry_at", "<=", fields.Datetime.now()),
            ],
            limit=50,
            order="next_retry_at, id",
        )
        for job in jobs:
            try:
                response = requests.post(
                    webhook_url,
                    json=json.loads(job.payload),
                    timeout=5,
                )
                response.raise_for_status()
            except requests.RequestException as error:
                attempts = job.attempts + 1
                retry_minutes = min(60, 5 * (2 ** (attempts - 1)))
                values = {
                    "attempts": attempts,
                    "last_error": str(error)[:1000],
                }
                if attempts >= 6:
                    values["state"] = "failed"
                else:
                    values["next_retry_at"] = fields.Datetime.add(
                        fields.Datetime.now(),
                        minutes=retry_minutes,
                    )
                job.write(values)
            else:
                job.write(
                    {
                        "state": "sent",
                        "attempts": job.attempts + 1,
                        "last_error": False,
                    }
                )


class ShopApiStockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        result = super().button_validate()
        webhook_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("shop_api.webhook_url")
        )
        if not webhook_url:
            return result

        jobs = self.env["shop.api.webhook.job"].sudo()
        for picking in self.filtered(
            lambda item: item.state == "done"
            and item.picking_type_code == "outgoing"
            and item.sale_id
        ):
            if jobs.search_count([("picking_id", "=", picking.id)]):
                continue
            jobs.create(
                {
                    "picking_id": picking.id,
                    "payload": json.dumps(
                        {
                            "event": "delivery_validated",
                            "external_reference": picking.sale_id.client_order_ref or "",
                            "order": picking.sale_id.name,
                            "delivery": picking.name,
                        }
                    ),
                }
            )
        return result
