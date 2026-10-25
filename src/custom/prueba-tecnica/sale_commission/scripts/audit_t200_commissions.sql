BEGIN TRANSACTION READ ONLY;

WITH commission_candidates AS (
    SELECT
        order_record.id AS order_id,
        order_record.name AS order_name,
        order_record.date_order,
        order_record.user_id AS salesperson_id,
        salesperson_partner.name AS salesperson_name,
        order_record.write_uid AS order_last_writer_id,
        order_writer_partner.name AS order_last_writer_name,
        line.id AS order_line_id,
        line.product_id,
        line.price_subtotal,
        line.commission_percent AS saved_percent,
        COALESCE(rule.percent, salesperson.commission_percent, 0.0) AS expected_percent,
        line.commission_amount AS saved_amount,
        line.price_subtotal
            * COALESCE(rule.percent, salesperson.commission_percent, 0.0)
            / 100.0 AS expected_amount,
        line.write_uid AS line_last_writer_id,
        writer_partner.name AS line_last_writer_name,
        line.write_date,
        rule.id AS matched_rule_id
    FROM sale_order_line AS line
    JOIN sale_order AS order_record ON order_record.id = line.order_id
    JOIN res_users AS salesperson ON salesperson.id = order_record.user_id
    JOIN res_partner AS salesperson_partner ON salesperson_partner.id = salesperson.partner_id
    JOIN res_users AS order_writer ON order_writer.id = order_record.write_uid
    JOIN res_partner AS order_writer_partner ON order_writer_partner.id = order_writer.partner_id
    JOIN res_users AS line_writer ON line_writer.id = line.write_uid
    JOIN res_partner AS writer_partner ON writer_partner.id = line_writer.partner_id
    JOIN product_product AS product ON product.id = line.product_id
    JOIN product_template AS template ON template.id = product.product_tmpl_id
    JOIN product_category AS product_category ON product_category.id = template.categ_id
    LEFT JOIN LATERAL (
        SELECT commission_rule.id, commission_rule.percent
        FROM sale_commission_rule AS commission_rule
        JOIN product_category AS rule_category
            ON rule_category.id = commission_rule.categ_id
        WHERE product_category.parent_path LIKE rule_category.parent_path || '%'
          AND (
              commission_rule.company_id IS NULL
              OR commission_rule.company_id = order_record.company_id
          )
        ORDER BY length(rule_category.parent_path) DESC, commission_rule.id
        LIMIT 1
    ) AS rule ON TRUE
    WHERE order_record.state = 'sale'
      AND line.display_type IS NULL
      AND (
          line.write_uid <> order_record.user_id
          OR order_record.write_uid <> order_record.user_id
      )
)
SELECT
    order_id,
    order_name,
    date_order,
    salesperson_id,
    salesperson_name,
    order_last_writer_id,
    order_last_writer_name,
    order_line_id,
    product_id,
    line_last_writer_id,
    line_last_writer_name,
    saved_percent,
    expected_percent,
    price_subtotal,
    saved_amount,
    expected_amount,
    matched_rule_id,
    write_date
FROM commission_candidates
WHERE abs(saved_percent - expected_percent) > 0.005
ORDER BY date_order, order_id, order_line_id;

COMMIT;
