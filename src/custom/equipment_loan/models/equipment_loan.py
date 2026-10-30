from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EquipmentLoan(models.Model):
    _name = "equipment.loan"
    _description = "Equipment Loan"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Equipment", required=True, ondelete="restrict"
    )
    recipient_id = fields.Many2one(
        "res.users", string="Recipient", required=True, default=lambda self: self.env.user
    )
    delivery_date = fields.Date(
        string="Delivery Date", required=True, default=fields.Date.context_today
    )
    expected_return_date = fields.Date(string="Expected Return Date", required=True)
    actual_return_date = fields.Date(string="Actual Return Date", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaned', 'Loaned'),
        ('returned', 'Returned')
    ], string="Status", default='draft', required=True)
    is_overdue = fields.Boolean(
        string="Overdue", compute="_compute_is_overdue"
    )
    overdue_activity_created = fields.Boolean(
        string="Overdue Activity Created", default=False, copy=False, readonly=True
    )

    @api.depends("state", "expected_return_date")
    def _compute_is_overdue(self):
        for loan in self:
            loan.is_overdue = (
                loan.state == "loaned"
                and bool(loan.expected_return_date)
                and loan.expected_return_date < fields.Date.context_today(loan)
            )

    @api.constrains("delivery_date", "expected_return_date")
    def _check_return_date(self):
        for loan in self:
            if (
                loan.delivery_date
                and loan.expected_return_date
                and loan.expected_return_date < loan.delivery_date
            ):
                raise ValidationError(
                    _("La fecha prevista de devolución no puede ser anterior a la fecha de entrega.")
                )

    @api.constrains("equipment_id", "state")
    def _check_one_active_loan_per_equipment(self):
        for loan in self.filtered(lambda item: item.state == "loaned" and item.equipment_id):
            active_loan = self.search([
                ("equipment_id", "=", loan.equipment_id.id),
                ("state", "=", "loaned"),
                ("id", "!=", loan.id),
            ], limit=1)
            if active_loan:
                raise ValidationError(
                    _("Este equipo ya tiene otro préstamo activo.")
                )

    def action_deliver(self):
        for loan in self:
            if loan.state != "draft":
                raise UserError(_("Solo se puede entregar un préstamo en borrador."))
            loan.state = "loaned"
        return True

    def action_return(self):
        for loan in self:
            if loan.state != "loaned":
                raise UserError(_("Solo se puede devolver un préstamo activo."))
            loan.write({
                "actual_return_date": fields.Date.context_today(loan),
                "state": "returned",
            })
        return True

    @api.model
    def _cron_schedule_overdue_activities(self):
        today = fields.Date.context_today(self)
        overdue_loans = self.search([
            ("state", "=", "loaned"),
            ("expected_return_date", "<", today),
            ("overdue_activity_created", "=", False),
        ])
        for loan in overdue_loans:
            loan.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=loan.recipient_id.id,
                date_deadline=today,
                summary=_("Préstamo vencido"),
                note=_("El préstamo del equipo %s venció el %s.")
                % (loan.equipment_id.display_name, loan.expected_return_date),
            )
            loan.overdue_activity_created = True
        return True