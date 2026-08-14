\set ON_ERROR_STOP on
BEGIN;
INSERT INTO sales.order_items (
    order_item_id, order_id, line_number, sku, quantity, unit_price, updated_at, is_deleted
) VALUES (9902, 1001, 99, 'INVALID-PRICE', 1, -0.01, NOW(), FALSE);
ROLLBACK;
