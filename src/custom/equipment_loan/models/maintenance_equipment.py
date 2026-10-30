from odoo import _, api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    equipment_loan_ids = fields.One2many(
        "equipment.loan", "equipment_id", string="Loans"
    )
    equipment_loan_count = fields.Integer(
        string="Equipment Loans", compute="_compute_equipment_loan_count"
    )

    @api.depends("equipment_loan_ids")
    def _compute_equipment_loan_count(self):
        for equipment in self:
            equipment.equipment_loan_count = len(equipment.equipment_loan_ids)

    def action_view_equipment_loans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Equipment Loans"),
            "res_model": "equipment.loan",
            "view_mode": "tree,form",
            "domain": [("equipment_id", "=", self.id)],
            "context": {"default_equipment_id": self.id},
        }
