\set ON_ERROR_STOP on

-- Synthetic deterministic fixtures:
-- mixed-case-email, offset-timestamp, soft-deleted-order
INSERT INTO sales.orders (
    order_id,
    customer_id,
    customer_first_name,
    customer_last_name,
    customer_email,
    order_status,
    ordered_at,
    updated_at,
    is_deleted
) VALUES
    (1001, 42, ' Ava ', ' Smith ', ' Ava.Smith@Example.COM ', ' shipped ',
        '2026-08-01 10:30:00-04', '2026-08-01 11:10:00-04', FALSE),
    (1002, 77, 'Mateo', 'Garcia', ' MATEO.GARCIA@example.com', ' processing ',
        '2026-08-02 18:15:00+02', '2026-08-02 18:45:00+02', FALSE),
    (1003, 91, 'Li', 'Wei', 'li.wei@example.com ', ' new ',
        '2026-08-03 09:00:00+09', '2026-08-03 09:05:00+09', FALSE),
    (1004, 55, 'Noah', 'Jones', 'noah.jones@example.com', 'cancelled',
        '2026-08-04 08:00:00Z', '2026-08-04 08:30:00Z', TRUE),
    (1005, 66, 'Sara', 'Ahmed', ' sara.ahmed@example.com ', ' paid ',
        '2026-08-05 12:00:00-07', '2026-08-05 12:20:00-07', FALSE)
ON CONFLICT (order_id) DO UPDATE SET
    customer_id = EXCLUDED.customer_id,
    customer_first_name = EXCLUDED.customer_first_name,
    customer_last_name = EXCLUDED.customer_last_name,
    customer_email = EXCLUDED.customer_email,
    order_status = EXCLUDED.order_status,
    ordered_at = EXCLUDED.ordered_at,
    updated_at = EXCLUDED.updated_at,
    is_deleted = EXCLUDED.is_deleted;

-- multiple-items, single-item, decimal-total, soft-deleted-item
INSERT INTO sales.order_items (
    order_item_id,
    order_id,
    line_number,
    sku,
    quantity,
    unit_price,
    updated_at,
    is_deleted
) VALUES
    (5001, 1001, 1, 'KB-101', 2, 25.00, '2026-08-01 11:00:00-04', FALSE),
    (5002, 1001, 2, 'MS-205', 1, 19.95, '2026-08-01 11:05:00-04', FALSE),
    (5003, 1002, 1, 'MON-24', 1, 199.99, '2026-08-02 18:30:00+02', FALSE),
    (5004, 1002, 2, 'CBL-2M', 3, 7.50, '2026-08-02 18:31:00+02', FALSE),
    (5005, 1002, 3, 'PAD-XL', 1, 12.25, '2026-08-02 18:32:00+02', FALSE),
    (5006, 1003, 1, 'USB-C-65W', 1, 49.90, '2026-08-03 09:02:00+09', FALSE),
    (5007, 1004, 1, 'OLD-001', 1, 5.00, '2026-08-04 08:10:00Z', FALSE),
    (5008, 1005, 1, 'CAM-1080', 1, 74.40, '2026-08-05 12:10:00-07', FALSE),
    (5009, 1005, 2, 'CAM-CASE', 1, 9.60, '2026-08-05 12:11:00-07', TRUE)
ON CONFLICT (order_item_id) DO UPDATE SET
    order_id = EXCLUDED.order_id,
    line_number = EXCLUDED.line_number,
    sku = EXCLUDED.sku,
    quantity = EXCLUDED.quantity,
    unit_price = EXCLUDED.unit_price,
    updated_at = EXCLUDED.updated_at,
    is_deleted = EXCLUDED.is_deleted;
