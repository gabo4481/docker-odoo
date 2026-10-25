from odoo.addons.fleet_inspection.fleet_inspection_migration import (
    prepare_vehicle_type_column,
)


def migrate(cr, version):
    prepare_vehicle_type_column(cr)
