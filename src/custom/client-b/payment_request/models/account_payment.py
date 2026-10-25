from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_request_ids = fields.One2many("payment.request", "payment_id", string="Payment Requests")