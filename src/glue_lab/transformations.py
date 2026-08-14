"""Credential-free Spark transformations for the snapshot migration."""

from __future__ import annotations

from functools import reduce

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType

UNIT_PRICE = DecimalType(12, 2)
LINE_MONEY = DecimalType(22, 2)
ORDER_MONEY = DecimalType(38, 2)


def _fail_if_rows(frame: DataFrame, message: str) -> None:
    """Raise a stable validation error without bringing the dataset to the driver."""
    if frame.limit(1).count() != 0:
        raise ValueError(message)


def _validate_source(orders: DataFrame, items: DataFrame) -> tuple[DataFrame, DataFrame]:
    _fail_if_rows(orders.where(F.col("is_deleted").isNull()), "null order deletion flag")
    _fail_if_rows(items.where(F.col("is_deleted").isNull()), "null item deletion flag")
    active_orders = orders.where(F.col("is_deleted") == F.lit(False))
    active_items = items.where(F.col("is_deleted") == F.lit(False))

    _fail_if_rows(active_orders.where(F.col("order_id").isNull()), "null order key")
    _fail_if_rows(
        active_orders.groupBy("order_id").count().where(F.col("count") > 1),
        "duplicate order key",
    )
    _fail_if_rows(active_items.where(F.col("order_item_id").isNull()), "null item key")
    _fail_if_rows(
        active_items.groupBy("order_item_id").count().where(F.col("count") > 1),
        "duplicate item key",
    )
    _fail_if_rows(
        active_items.where(F.col("order_id").isNull() | F.col("line_number").isNull()),
        "null item business key",
    )
    _fail_if_rows(
        active_items.groupBy("order_id", "line_number").count().where(F.col("count") > 1),
        "duplicate item business key",
    )
    _fail_if_rows(
        active_items.join(orders.select("order_id"), "order_id", "left_anti"),
        "orphan item",
    )
    _fail_if_rows(
        active_items.where(F.col("quantity").isNull() | (F.col("quantity") <= 0)),
        "invalid quantity: null or nonpositive quantity",
    )
    _fail_if_rows(
        active_items.where(F.col("unit_price").isNull() | (F.col("unit_price") < 0)),
        "invalid price: null or negative price",
    )

    required_order_columns = [
        "customer_id",
        "customer_first_name",
        "customer_last_name",
        "customer_email",
        "order_status",
        "ordered_at",
        "updated_at",
    ]
    _fail_if_rows(
        active_orders.where(
            reduce(
                lambda left, right: left | right,
                [F.col(name).isNull() for name in required_order_columns],
            )
        ),
        "null required order value",
    )
    _fail_if_rows(
        active_items.where(F.col("sku").isNull() | F.col("updated_at").isNull()),
        "null required item value",
    )

    relevant_items = active_items.join(active_orders.select("order_id"), "order_id", "left_semi")
    _fail_if_rows(
        active_orders.join(relevant_items.select("order_id").distinct(), "order_id", "left_anti"),
        "active order without active items",
    )
    return active_orders, relevant_items


def _utc_text(column_name: str):
    return F.date_format(F.col(column_name), "yyyy-MM-dd'T'HH:mm:ss'Z'")


def build_order_documents(orders: DataFrame, items: DataFrame) -> DataFrame:
    """Validate relational rows and return deterministic nested order documents.

    Active orders with zero active items fail validation rather than producing an
    ambiguous empty document. All validation and transformation work stays in Spark;
    only bounded existence checks execute as actions.
    """
    orders.sparkSession.conf.set("spark.sql.session.timeZone", "UTC")
    active_orders, active_items = _validate_source(orders, items)

    item_values = active_items.withColumn(
        "_line_total", (F.col("quantity") * F.col("unit_price")).cast(LINE_MONEY)
    )
    _fail_if_rows(
        item_values.where(F.col("_line_total").isNull()),
        "null or overflow line total",
    )
    item_rows = item_values.select(
        "order_id",
        F.struct(
            F.col("line_number").alias("sortKey"),
            F.struct(
                F.col("order_item_id").alias("id"),
                F.col("line_number").alias("lineNumber"),
                F.trim(F.col("sku")).alias("sku"),
                F.col("quantity").alias("quantity"),
                F.col("unit_price").cast(UNIT_PRICE).alias("unitPrice"),
                F.col("_line_total").alias("lineTotal"),
            ).alias("document"),
        ).alias("sortableItem"),
        F.col("_line_total").alias("lineTotal"),
    )
    nested_items = (
        item_rows.groupBy("order_id")
        .agg(
            F.sort_array(F.collect_list("sortableItem")).alias("sortedItems"),
            F.sum(F.col("lineTotal").cast(ORDER_MONEY)).cast(ORDER_MONEY).alias("orderTotal"),
        )
        .select(
            "order_id",
            F.transform("sortedItems", lambda item: item["document"]).alias("items"),
            "orderTotal",
        )
    )
    _fail_if_rows(
        nested_items.where(F.col("orderTotal").isNull()),
        "null or overflow order total",
    )

    normalized_orders = active_orders.select(
        F.col("order_id"),
        F.col("order_id").alias("_id"),
        F.struct(
            F.col("customer_id").alias("id"),
            F.concat_ws(
                " ",
                F.trim(F.col("customer_first_name")),
                F.trim(F.col("customer_last_name")),
            ).alias("name"),
            F.lower(F.trim(F.col("customer_email"))).alias("email"),
        ).alias("customer"),
        _utc_text("ordered_at").alias("orderedAt"),
        _utc_text("updated_at").alias("updatedAt"),
        F.upper(F.trim(F.col("order_status"))).alias("status"),
    )

    return (
        normalized_orders.join(nested_items, "order_id", "inner")
        .select(
            "_id",
            "customer",
            "orderedAt",
            "updatedAt",
            "status",
            "items",
            "orderTotal",
            F.struct(
                F.lit("postgresql").alias("source"),
                F.lit("snapshot").alias("mode"),
            ).alias("migration"),
        )
        .orderBy("_id")
    )
