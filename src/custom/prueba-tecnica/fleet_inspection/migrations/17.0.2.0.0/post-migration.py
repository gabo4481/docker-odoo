from odoo.addons.fleet_inspection.fleet_inspection_migration import (
    migrate_vehicle_types,
)


def migrate(cr, version):
    migrate_vehicle_types(cr)
