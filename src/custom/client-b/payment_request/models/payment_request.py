from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


REQUESTER_GROUP = "payment_request.group_payment_request_requester"
APPROVER_GROUP = "payment_request.group_payment_request_approver"
TREASURY_GROUP = "payment_request.group_payment_request_treasury"

class PaymentRequest(models.Model):
    _name = "payment.request"
    _description = "Payment Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Name", required=True, readonly=True, copy=False, default= "New")
    partner_id = fields.Many2one("res.partner", string="Proveedor", required=True)
    requester_id = fields.Many2one("res.users", string="Solicitante", required=True, default=lambda self: self.env.user)
    amount = fields.Monetary(string="Monto", required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Moneda", required=True, default=lambda self: self.env.company.currency_id)
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    concept = fields.Text(string="Concepto", required=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("sent", "Enviado"), ("approved", "Aprobado"), ("rejected", "Rechazada"),("paid", "Pagado")],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one("res.company", string="Compañía", required=True, default=lambda self: self.env.company)
    approver_id = fields.Many2one("res.users", string="Aprobador")
    approved_by_id = fields.Many2one("res.users", string="Aprobado por")
    approved_at = fields.Datetime(string="Aprobado el", readonly=True, copy=False)
    rejection_reason = fields.Text(string="Motivo de Rechazo")
    payment_id = fields.Many2one("account.payment", string="Pago")

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals = []
        for values in vals_list:
            values = dict(values)
            values.update({
                "name": self.env["ir.sequence"].next_by_code("payment.request") or _("New"),
                "requester_id": self.env.user.id,
                "company_id": self.env.company.id,
                "state": "draft",
                "approver_id": False,
                "approved_by_id": False,
                "approved_at": False,
                "rejection_reason": False,
                "payment_id": False,
            })
            prepared_vals.append(values)
        return super().create(prepared_vals)


    _REQUEST_FIELDS = {
        "partner_id",
        "amount",
        "currency_id",
        "date",
        "concept",
    }

    def _get_approval_level(self):
        self.ensure_one()
        return self.env["payment.approval.level"].sudo().search(
            [
                ("company_id", "=", self.company_id.id),
                ("currency_id", "=", self.currency_id.id),
                ("min_amount", "<=", self.amount),
            ],
            order="min_amount desc, id",
            limit=1,
        )

    def write(self, vals):
        vals = dict(vals)

        if "state" in vals:
            self._lock_for_update()

        if self.filtered(lambda request: request.state != "draft") and (
            self._REQUEST_FIELDS.intersection(vals)
        ):
            raise UserError(_("No puedes modificar una solicitud después de enviarla."))

        if "requester_id" in vals or "company_id" in vals:
            raise AccessError(_("No puedes cambiar el solicitante ni la compañía."))

        target_state = vals.get("state")
        if "approver_id" in vals and target_state != "sent":
            raise AccessError(_("El aprobador se asigna al enviar la solicitud."))

        if "payment_id" in vals and target_state != "paid":
            raise AccessError(_("El pago solo se vincula al marcar pagada la solicitud."))

        if target_state:
            for request in self:
                if target_state == request.state:
                    raise UserError(_("La solicitud ya está en ese estado."))



                if target_state == "sent":
                    if request.state != "draft":
                        raise UserError(_("Solo puedes enviar una solicitud en borrador."))
                    if not self.env.user.has_group(REQUESTER_GROUP):
                        raise AccessError(_("Necesitas el grupo Solicitante para enviar."))
                    if request.requester_id != self.env.user:
                        raise AccessError(_("Solo el solicitante puede enviar su solicitud."))
                    level = request._get_approval_level()
                    if not level:
                        raise UserError(
                            _("No hay un nivel de aprobación para el monto y moneda de esta solicitud.")
                        )
                    if vals.get("approver_id") != level.approver_id.id:
                        raise AccessError(_("El aprobador asignado no corresponde al nivel configurado."))
                    if self._REQUEST_FIELDS.intersection(vals):
                        raise UserError(_("Guarda los cambios del borrador antes de enviarlo."))

                elif target_state == "approved":
                    if request.state != "sent":
                        raise UserError(_("Solo puedes aprobar una solicitud enviada."))
                    if not self.env.user.has_group(APPROVER_GROUP):
                        raise AccessError(_("Necesitas el grupo Aprobador para aprobar."))
                    if request.requester_id == self.env.user:
                        raise AccessError(_("No puedes aprobar tu propia solicitud."))
                    if request.approver_id != self.env.user:
                        raise AccessError(_("Solo el aprobador asignado puede aprobar esta solicitud."))

                    if vals.get("approved_by_id") != self.env.user.id:
                        raise AccessError(_("La aprobación debe quedar registrada a tu nombre."))
                    if not vals.get("approved_at"):
                        raise UserError(_("Debes registrar la fecha de aprobación."))

                elif target_state == "rejected":
                    if request.state != "sent":
                        raise UserError(_("Solo puedes rechazar una solicitud enviada."))
                    if not self.env.user.has_group(APPROVER_GROUP):
                        raise AccessError(_("Necesitas el grupo Aprobador para rechazar."))
                    if request.requester_id == self.env.user:
                        raise AccessError(_("No puedes rechazar tu propia solicitud."))
                    if request.approver_id != self.env.user:
                        raise AccessError(_("Solo el aprobador asignado puede rechazar esta solicitud."))

                    reason = (vals.get("rejection_reason") or "").strip()
                    if not reason:
                        raise ValidationError(_("Debes indicar el motivo del rechazo."))
                    vals["rejection_reason"] = reason

                elif target_state == "paid":
                    if request.state != "approved":
                        raise UserError(_("Solo puedes pagar una solicitud aprobada."))
                    if not self.env.user.has_group(TREASURY_GROUP):
                        raise AccessError(_("Necesitas el grupo Tesorería para pagar."))
                    if request.payment_id:
                        raise UserError(_("La solicitud ya tiene un pago vinculado."))
                    payment = (
                        self.env["account.payment"]
                        .sudo()
                        .browse(vals.get("payment_id"))
                        .exists()
                    )
                    if not payment or payment.state != "posted":
                        raise UserError(_("Debes vincular un pago contable publicado."))
                    if (
                        payment.partner_id != request.partner_id
                        or payment.company_id != request.company_id
                        or payment.payment_type != "outbound"
                        or payment.partner_type != "supplier"
                        or payment.journal_id.type not in ("bank", "cash")
                    ):
                        raise ValidationError(
                            _("El pago no coincide con el proveedor, compañía y tipo de pago solicitado.")
                        )
                    journal_currency = (
                        payment.journal_id.currency_id
                        or request.company_id.currency_id
                    )
                    expected_amount = request.currency_id._convert(
                        request.amount,
                        journal_currency,
                        request.company_id,
                        payment.date,
                    )
                    if (
                        payment.currency_id != journal_currency
                        or journal_currency.compare_amounts(
                            payment.amount,
                            expected_amount,
                        ) != 0
                    ):
                        raise ValidationError(
                            _("El monto del pago no coincide con la conversión a la fecha del pago.")
                        )

                else:
                    raise UserError(_("La transición de estado solicitada no está permitida."))

        if "rejection_reason" in vals and target_state != "rejected":
            raise AccessError(_("El motivo solo se puede establecer al rechazar la solicitud."))

        if {"approved_by_id", "approved_at"}.intersection(vals) and target_state != "approved":
            raise AccessError(_("Los datos de aprobación solo se cambian al aprobar."))

        result = super().write(vals)

        if target_state == "rejected":
            for request in self:
                request.message_post(
                    body=_("Solicitud rechazada. Motivo: %s") % request.rejection_reason
                )
        elif target_state == "sent":
            activity_type = self.env.ref("mail.mail_activity_data_todo")
            for request in self:
                request.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=request.approver_id.id,
                    summary=_("Aprobar solicitud de pago"),
                    note=_("Revisa y aprueba o rechaza la solicitud %s.") % request.name,
                )

        return result

    @api.constrains("amount")
    def _check_amount_positive(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError("El monto debe ser positivo.")

    @api.constrains("partner_id")
    def _check_partner_is_supplier(self):
        for request in self:
            if request.partner_id and not request.partner_id.supplier_rank:
                raise ValidationError(_("El proveedor debe ser un contacto marcado como proveedor."))

    def action_submit(self):
        self.ensure_one()
        level = self._get_approval_level()
        if not level:
            raise UserError(
                _("No hay un nivel de aprobación para el monto y moneda de esta solicitud.")
            )
        self.write({"state": "sent", "approver_id": level.approver_id.id})
        return True

    def action_approve(self):
        self.ensure_one()
        self.write({
            "state": "approved",
            "approved_by_id": self.env.user.id,
            "approved_at": fields.Datetime.now(),
        })
        return True

    def action_reject(self, reason):
        self.ensure_one()
        if not reason or not reason.strip():
            raise ValidationError(_("Debes indicar el motivo del rechazo."))

        self.write({
            "state": "rejected",
            "rejection_reason": reason.strip(),
        })
        return True

    def action_open_reject_wizard(self):
        self.ensure_one()

        if not self.env.user.has_group(APPROVER_GROUP):
            raise AccessError(_("Solo un aprobador puede rechazar solicitudes."))

        if self.state != "sent":
            raise UserError(_("Solo puedes rechazar una solicitud enviada."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar solicitud"),
            "res_model": "payment.request.reject.wizard",
            "view_mode": "form",
            "view_id": self.env.ref(
                "payment_request.view_payment_request_reject_wizard_form"
            ).id,
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_open_payment_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group(TREASURY_GROUP):
            raise AccessError(_("Solo Tesorería puede registrar el pago."))
        if self.state != "approved":
            raise UserError(_("Solo puedes pagar una solicitud aprobada."))
        if self.payment_id:
            raise UserError(_("La solicitud ya tiene un pago vinculado."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Registrar pago"),
            "res_model": "payment.request.payment.wizard",
            "view_mode": "form",
            "view_id": self.env.ref(
                "payment_request.view_payment_request_payment_wizard_form"
            ).id,
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _lock_for_update(self):
        """Bloquea las solicitudes hasta que termine la transacción actual."""
        if not self:
            return

        self.flush_recordset(["state", "payment_id"])
        self.env.cr.execute(
            f"SELECT id FROM {self._table} "
            "WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
            [self.ids],
        )
        self.invalidate_recordset(["state", "payment_id", "approver_id"])