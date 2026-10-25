from odoo import fields, models


class FleetInspectionVehicleType(models.Model):
    _name = "fleet.inspection.vehicle.type"
    _description = "Tipo de vehículo para inspección"
    _order = "sequence, name"

    name = fields.Char(string="Nombre", required=True, translate=True)
    code = fields.Char(string="Código", required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código del tipo de vehículo debe ser único."),
    ]
