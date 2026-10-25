VEHICLE_TYPE_XMLIDS = {
    "motorcycle": "vehicle_type_motorcycle",
    "car": "vehicle_type_car",
    "truck": "vehicle_type_truck",
    "other": "vehicle_type_other",
}


def _column_exists(cr, column_name):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'fleet_inspection'
              AND column_name = %s
        )
        """,
        [column_name],
    )
    return cr.fetchone()[0]


def prepare_vehicle_type_column(cr):
    if _column_exists(cr, "vehicle_type") and not _column_exists(
        cr, "vehicle_type_legacy"
    ):
        cr.execute(
            "ALTER TABLE fleet_inspection "
            "RENAME COLUMN vehicle_type TO vehicle_type_legacy"
        )
    # Remove obsolete Selection metadata before Odoo cleans up the changed field.
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
        WHERE field_id IN (
            SELECT id
            FROM ir_model_fields
            WHERE model = 'fleet.inspection'
              AND name = 'vehicle_type'
        )
        """
    )


def migrate_vehicle_types(cr, batch_size=1000):
    if batch_size < 1:
        raise ValueError("batch_size debe ser mayor que cero")
    if not _column_exists(cr, "vehicle_type_legacy"):
        return 0
    if not _column_exists(cr, "vehicle_type"):
        raise RuntimeError("No existe la columna nueva fleet_inspection.vehicle_type")

    xmlids = list(VEHICLE_TYPE_XMLIDS.values())
    cr.execute(
        """
        SELECT name, res_id
        FROM ir_model_data
        WHERE module = 'fleet_inspection'
          AND model = 'fleet.inspection.vehicle.type'
          AND name = ANY(%s)
        """,
        [xmlids],
    )
    type_ids = {name: res_id for name, res_id in cr.fetchall()}
    missing_xmlids = set(xmlids) - set(type_ids)
    if missing_xmlids:
        raise RuntimeError(
            "Faltan tipos de vehículo de fleet_inspection: %s"
            % ", ".join(sorted(missing_xmlids))
        )

    type_ids_by_code = {
        code: type_ids[xmlid] for code, xmlid in VEHICLE_TYPE_XMLIDS.items()
    }
    last_id = 0
    migrated = 0
    while True:
        cr.execute(
            """
            SELECT id, vehicle_type_legacy
            FROM fleet_inspection
            WHERE id > %s
            ORDER BY id
            LIMIT %s
            """,
            [last_id, batch_size],
        )
        rows = cr.fetchall()
        if not rows:
            break

        updates = []
        for inspection_id, legacy_code in rows:
            if legacy_code not in type_ids_by_code:
                raise RuntimeError(
                    "Tipo de vehículo desconocido en inspección %s: %r"
                    % (inspection_id, legacy_code)
                )
            updates.append((inspection_id, type_ids_by_code[legacy_code]))

        values_sql = ", ".join(["(%s, %s)"] * len(updates))
        cr.execute(
            """
            UPDATE fleet_inspection AS inspection
            SET vehicle_type = type_map.type_id
            FROM (VALUES %s) AS type_map(inspection_id, type_id)
            WHERE inspection.id = type_map.inspection_id
              AND inspection.vehicle_type IS DISTINCT FROM type_map.type_id
            """
            % values_sql,
            [value for update in updates for value in update],
        )
        last_id = rows[-1][0]
        migrated += len(rows)

    cr.execute("ALTER TABLE fleet_inspection DROP COLUMN vehicle_type_legacy")
    return migrated
