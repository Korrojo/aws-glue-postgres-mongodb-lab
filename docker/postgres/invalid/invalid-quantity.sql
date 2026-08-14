\set ON_ERROR_STOP on
BEGIN;
INSERT INTO sales.order_items (
    order_item_id, order_id, line_number, sku, quantity, unit_price, updated_at, is_deleted
) VALUES (9903, 1001, 98, 'INVALID-QUANTITY', 0, 1.00, NOW(), FALSE);
ROLLBACK;
