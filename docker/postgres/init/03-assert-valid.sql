\set ON_ERROR_STOP on

DO $assert$
DECLARE
    actual BIGINT;
BEGIN
    SELECT COUNT(*) INTO actual FROM sales.orders;
    IF actual <> 5 THEN RAISE EXCEPTION 'orders_total expected 5, got %', actual; END IF;
    RAISE NOTICE 'orders_total=5';

    SELECT COUNT(*) INTO actual FROM sales.orders WHERE NOT is_deleted;
    IF actual <> 4 THEN RAISE EXCEPTION 'active_orders expected 4, got %', actual; END IF;
    RAISE NOTICE 'active_orders=4';

    SELECT COUNT(*) INTO actual FROM sales.order_items;
    IF actual <> 9 THEN RAISE EXCEPTION 'items_total expected 9, got %', actual; END IF;
    RAISE NOTICE 'items_total=9';

    SELECT COUNT(*) INTO actual
    FROM sales.order_items AS item
    JOIN sales.orders AS order_row USING (order_id)
    WHERE NOT item.is_deleted AND NOT order_row.is_deleted;
    IF actual <> 7 THEN
        RAISE EXCEPTION 'active_items_for_active_orders expected 7, got %', actual;
    END IF;
    RAISE NOTICE 'active_items_for_active_orders=7';

    SELECT COUNT(*) INTO actual
    FROM sales.order_items AS item
    LEFT JOIN sales.orders AS order_row USING (order_id)
    WHERE order_row.order_id IS NULL;
    IF actual <> 0 THEN RAISE EXCEPTION 'orphan_items expected 0, got %', actual; END IF;
    RAISE NOTICE 'orphan_items=0';

    SELECT COUNT(*) INTO actual
    FROM (
        SELECT order_id, line_number
        FROM sales.order_items
        GROUP BY order_id, line_number
        HAVING COUNT(*) > 1
    ) AS duplicate_lines;
    IF actual <> 0 THEN
        RAISE EXCEPTION 'duplicate_line_numbers expected 0, got %', actual;
    END IF;
    RAISE NOTICE 'duplicate_line_numbers=0';

    SELECT COUNT(*) INTO actual FROM sales.order_items WHERE quantity <= 0;
    IF actual <> 0 THEN RAISE EXCEPTION 'invalid_quantities expected 0, got %', actual; END IF;
    RAISE NOTICE 'invalid_quantities=0';

    SELECT COUNT(*) INTO actual FROM sales.order_items WHERE unit_price < 0;
    IF actual <> 0 THEN RAISE EXCEPTION 'invalid_prices expected 0, got %', actual; END IF;
    RAISE NOTICE 'invalid_prices=0';

    IF (
        SELECT SUM(quantity * unit_price)
        FROM sales.order_items
        WHERE order_id = 1001 AND NOT is_deleted
    ) <> 69.95::NUMERIC(12,2) THEN
        RAISE EXCEPTION 'decimal total fixture for order 1001 is incorrect';
    END IF;
    RAISE NOTICE 'decimal_total_order_1001=69.95';
END
$assert$;

SELECT 'source assertions: PASS' AS result;
