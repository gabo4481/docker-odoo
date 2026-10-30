from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from psycopg2 import IntegrityError


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
    def init(self):
        # A Python constraint cannot serialize simultaneous deliveries; PostgreSQL enforces this atomically.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS equipment_loan_one_active_per_equipment_idx
            ON equipment_loan (equipment_id)
            WHERE state = 'loaned'
        """)

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
        if not self.env.user.has_group("equipment_loan.group_equipment_loan_manager"):
            raise AccessError(_("Solo un gestor de préstamos puede entregar equipos."))
        for loan in self:
            if loan.state != "draft":
                raise UserError(_("Solo se puede entregar un préstamo en borrador."))
            try:
                with self.env.cr.savepoint():
                    loan.state = "loaned"
            except IntegrityError as error:
                if error.diag.constraint_name != "equipment_loan_one_active_per_equipment_idx":
                    raise
                raise ValidationError(
                    _("Este equipo ya tiene otro préstamo activo.")
                ) from error
        return True

    def action_return(self):
        if not self.env.user.has_group("equipment_loan.group_equipment_loan_manager"):
            raise AccessError(_("Solo un gestor de préstamos puede devolver equipos."))
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
        ])
        if not overdue_loans:
            return True

        manager = self.env.ref("equipment_loan.group_equipment_loan_manager").users.filtered(
            lambda user: user.active
        ).sorted("id")[:1]
        if not manager:
            raise UserError(_("Asigna al menos un usuario al grupo «Gestor de préstamos»."))

        activity_type = self.env.ref("mail.mail_activity_data_todo")
        existing_activities = self.env["mail.activity"].search([
            ("res_model_id", "=", self.env["ir.model"]._get_id("equipment.loan")),
            ("res_id", "in", overdue_loans.ids),
            ("activity_type_id", "=", activity_type.id),
            ("summary", "=", _("Préstamo vencido")),
        ])
        loans_with_activity = set(existing_activities.mapped("res_id"))
        for loan in overdue_loans:
            if loan.id in loans_with_activity:
                continue
            loan.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=manager.id,
                date_deadline=today,
                summary=_("Préstamo vencido"),
                note=_("El préstamo del equipo %s venció el %s.")
                % (loan.equipment_id.display_name, loan.expected_return_date),
            )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("equipment_loan.group_equipment_loan_manager"):
            if any(vals.get("state", "draft") != "draft" for vals in vals_list):
                raise AccessError(_("Solo un gestor de préstamos puede cambiar el estado."))
        return super().create(vals_list)

    def write(self, vals):
        if (
            "state" in vals
            and not self.env.user.has_group("equipment_loan.group_equipment_loan_manager")
        ):
            raise AccessError(_("Solo un gestor de préstamos puede cambiar el estado."))
        return super().write(vals)