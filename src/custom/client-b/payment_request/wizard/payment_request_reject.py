from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

APPROVER_GROUP = "payment_request.group_payment_request_approver"


class PaymentRequestRejectWizard(models.TransientModel):
    _name = "payment.request.reject.wizard"
    _description = "Rechazar solicitud de pago"

    request_id = fields.Many2one(
        "payment.request",
        string="Solicitud",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Motivo del rechazo",
        required=True,
    )

    def action_confirm(self):
        self.ensure_one()

        if not self.env.user.has_group(APPROVER_GROUP):
            raise AccessError(_("Solo un aprobador puede rechazar solicitudes."))

        if self.request_id.state != "sent":
            raise UserError(_("Solo puedes rechazar una solicitud enviada."))

        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("El motivo de rechazo es obligatorio."))

        self.request_id.action_reject(reason)

        return {"type": "ir.actions.act_window_close"}