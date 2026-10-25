from odoo import models, fields, api

class PaymentApprovalLevel(models.Model):
    _name = "payment.approval.level"
    _description = "Payment Approval Level"

    name = fields.Char(string="Name", required=True)
    min_amount = fields.Monetary(string="Minimum Amount", required=True, currency_field="currency_id")
    approver_id = fields.Many2one("res.users", string="Approver", required=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True, default=lambda self: self.env.company.currency_id)
