{
    "name": "Equipment Loan",
    "version": "17.0.1.0.0",
    "category": "Sales",
    "summary": "Equipment Loan module for Odoo 17",
    "depends": ["maintenance", "mail"],
    "data": [
        "security/equipment_loan_groups.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/equipment_loan_views.xml",
        "views/maintenance_equipment_views.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
