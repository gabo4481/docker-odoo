from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


TREASURY_GROUP = "payment_request.group_payment_request_treasury"


class PaymentRequestPaymentWizard(models.TransientModel):
    _name = "payment.request.payment.wizard"
    _description = "Registrar pago de solicitud"

    request_id = fields.Many2one(
        "payment.request",
        string="Solicitud",
        required=True,
        readonly=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', request_company_id)]",
    )
    request_company_id = fields.Many2one(
        related="request_id.company_id",
        readonly=True,
    )
    date = fields.Date(
        string="Fecha de pago",
        required=True,
        default=fields.Date.context_today,
    )

    def action_confirm(self):
        self.ensure_one()

        if not self.env.user.has_group(TREASURY_GROUP):
            raise AccessError(_("Solo Tesorería puede registrar el pago."))

        request = self.request_id.with_company(self.request_id.company_id)
        request._lock_for_update()
        request.invalidate_recordset(["state", "payment_id"])

        if request.state != "approved":
            raise UserError(_("Solo puedes pagar una solicitud aprobada."))
        if request.payment_id:
            raise UserError(_("La solicitud ya tiene un pago vinculado."))
        if self.journal_id.company_id != request.company_id:
            raise UserError(_("El diario debe pertenecer a la compañía de la solicitud."))
        if self.journal_id.type not in ("bank", "cash"):
            raise UserError(_("Selecciona un diario de banco o caja."))

        payment_currency = self.journal_id.currency_id or request.company_id.currency_id

        payment_amount = request.currency_id._convert(
            request.amount,
            payment_currency,
            request.company_id,
            self.date,
        )

        payment_method = self.journal_id.outbound_payment_method_line_ids[:1]
        if not payment_method:
            raise UserError(
                _("Configura un método de pago saliente en el diario seleccionado.")
            )

        with self.env.cr.savepoint():
            payment = (
                self.env["account.payment"]
                .with_company(request.company_id)
                .sudo()
                .create({
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                    "partner_id": request.partner_id.id,
                    "amount": payment_amount,
                    "currency_id": payment_currency.id,
                    "date": self.date,
                    "journal_id": self.journal_id.id,
                    "payment_method_line_id": payment_method.id,
                    "ref": request.name,
                    "company_id": request.company_id.id,
                })
            )
            payment.action_post()
            request.write({
                "state": "paid",
                "payment_id": payment.id,
            })

        return {"type": "ir.actions.act_window_close"}
