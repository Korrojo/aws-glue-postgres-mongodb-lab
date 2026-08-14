from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    BooleanType,
    DecimalType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from glue_lab.transformations import build_order_documents  # noqa: E402

ORDER_SCHEMA = StructType(
    [
        StructField("order_id", LongType(), True),
        StructField("customer_id", LongType(), True),
        StructField("customer_first_name", StringType(), True),
        StructField("customer_last_name", StringType(), True),
        StructField("customer_email", StringType(), True),
        StructField("order_status", StringType(), True),
        StructField("ordered_at", TimestampType(), True),
        StructField("updated_at", TimestampType(), True),
        StructField("is_deleted", BooleanType(), True),
    ]
)
ITEM_SCHEMA = StructType(
    [
        StructField("order_item_id", LongType(), True),
        StructField("order_id", LongType(), True),
        StructField("line_number", IntegerType(), True),
        StructField("sku", StringType(), True),
        StructField("quantity", IntegerType(), True),
        StructField("unit_price", DecimalType(12, 2), True),
        StructField("updated_at", TimestampType(), True),
        StructField("is_deleted", BooleanType(), True),
    ]
)
UTC = UTC
EST = timezone(timedelta(hours=-5))


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    session = (
        SparkSession.builder.master("local[2]")
        .appName("glue-lab-unit-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    yield session
    session.stop()


def valid_orders() -> list[dict[str, object]]:
    return [
        {
            "order_id": 1001,
            "customer_id": 42,
            "customer_first_name": "  Ava ",
            "customer_last_name": " Smith  ",
            "customer_email": " AVA@Example.COM ",
            "order_status": " shipped ",
            "ordered_at": datetime(2026, 8, 1, 9, 30, tzinfo=EST),
            "updated_at": datetime(2026, 8, 1, 15, 10, tzinfo=UTC),
            "is_deleted": False,
        },
        {
            "order_id": 1002,
            "customer_id": 43,
            "customer_first_name": "Noah",
            "customer_last_name": "Jones",
            "customer_email": "noah@example.com",
            "order_status": "NEW",
            "ordered_at": datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
            "updated_at": datetime(2026, 8, 2, 10, 5, tzinfo=UTC),
            "is_deleted": False,
        },
        {
            "order_id": 1003,
            "customer_id": 44,
            "customer_first_name": "Deleted",
            "customer_last_name": "Order",
            "customer_email": "deleted@example.com",
            "order_status": "NEW",
            "ordered_at": datetime(2026, 8, 3, tzinfo=UTC),
            "updated_at": datetime(2026, 8, 3, tzinfo=UTC),
            "is_deleted": True,
        },
    ]


def valid_items() -> list[dict[str, object]]:
    return [
        {
            "order_item_id": 5001,
            "order_id": 1001,
            "line_number": 2,
            "sku": " MOUSE-2 ",
            "quantity": 3,
            "unit_price": Decimal("0.10"),
            "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
            "is_deleted": False,
        },
        {
            "order_item_id": 5002,
            "order_id": 1001,
            "line_number": 1,
            "sku": " KB-101 ",
            "quantity": 2,
            "unit_price": Decimal("25.00"),
            "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
            "is_deleted": False,
        },
        {
            "order_item_id": 5003,
            "order_id": 1001,
            "line_number": 3,
            "sku": "DELETED",
            "quantity": 1,
            "unit_price": Decimal("99.99"),
            "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
            "is_deleted": True,
        },
        {
            "order_item_id": 5004,
            "order_id": 1002,
            "line_number": 1,
            "sku": "CABLE-1",
            "quantity": 1,
            "unit_price": Decimal("7.25"),
            "updated_at": datetime(2026, 8, 2, tzinfo=UTC),
            "is_deleted": False,
        },
        {
            "order_item_id": 5005,
            "order_id": 1003,
            "line_number": 1,
            "sku": "DELETED-ORDER-ITEM",
            "quantity": 1,
            "unit_price": Decimal("1.00"),
            "updated_at": datetime(2026, 8, 3, tzinfo=UTC),
            "is_deleted": False,
        },
    ]


def frames(spark: SparkSession, orders=None, items=None):
    return (
        spark.createDataFrame(valid_orders() if orders is None else orders, ORDER_SCHEMA),
        spark.createDataFrame(valid_items() if items is None else items, ITEM_SCHEMA),
    )


def test_builds_normalized_nested_documents_for_multiple_orders(spark: SparkSession) -> None:
    orders, items = frames(spark)

    documents = {
        row["_id"]: row.asDict(recursive=True)
        for row in build_order_documents(orders, items).collect()
    }

    assert set(documents) == {1001, 1002}
    first = documents[1001]
    assert first["customer"] == {"id": 42, "name": "Ava Smith", "email": "ava@example.com"}
    assert first["status"] == "SHIPPED"
    assert first["orderedAt"] == "2026-08-01T14:30:00Z"
    assert first["updatedAt"] == "2026-08-01T15:10:00Z"
    assert [item["lineNumber"] for item in first["items"]] == [1, 2]
    assert [item["sku"] for item in first["items"]] == ["KB-101", "MOUSE-2"]
    assert first["items"][0]["lineTotal"] == Decimal("50.00")
    assert first["items"][1]["lineTotal"] == Decimal("0.30")
    assert first["orderTotal"] == Decimal("50.30")
    assert first["migration"] == {"source": "postgresql", "mode": "snapshot"}
    assert documents[1002]["orderTotal"] == Decimal("7.25")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda orders, items: orders.__setitem__(0, orders[0] | {"order_id": None}),
            "null order key",
        ),
        (lambda orders, items: orders.append(dict(orders[0])), "duplicate order key"),
        (
            lambda orders, items: items.__setitem__(0, items[0] | {"order_item_id": None}),
            "null item key",
        ),
        (lambda orders, items: items.append(dict(items[0])), "duplicate item key"),
        (
            lambda orders, items: items.append(
                dict(items[0]) | {"order_item_id": 5999, "line_number": items[1]["line_number"]}
            ),
            "duplicate item business key",
        ),
        (lambda orders, items: items.__setitem__(0, items[0] | {"order_id": 9999}), "orphan item"),
        (
            lambda orders, items: items.__setitem__(0, items[0] | {"quantity": 0}),
            "nonpositive quantity",
        ),
        (
            lambda orders, items: items.__setitem__(0, items[0] | {"unit_price": Decimal("-0.01")}),
            "negative price",
        ),
    ],
)
def test_invalid_active_source_fails_before_transformation(
    spark: SparkSession, mutate, message: str
) -> None:
    orders = valid_orders()
    items = valid_items()
    mutate(orders, items)
    order_frame, item_frame = frames(spark, orders, items)

    with pytest.raises(ValueError, match=message):
        build_order_documents(order_frame, item_frame)


def test_active_order_with_zero_active_items_fails_deterministically(spark: SparkSession) -> None:
    items = [item for item in valid_items() if item["order_id"] != 1002]
    orders, item_frame = frames(spark, items=items)

    with pytest.raises(ValueError, match="active order without active items"):
        build_order_documents(orders, item_frame)


def test_maximum_integer_quantity_times_numeric_price_is_exact(spark: SparkSession) -> None:
    orders = [valid_orders()[0]]
    items = [
        valid_items()[0]
        | {
            "line_number": 1,
            "quantity": 2147483647,
            "unit_price": Decimal("9999999999.99"),
        }
    ]
    order_frame, item_frame = frames(spark, orders, items)

    document = build_order_documents(order_frame, item_frame).first().asDict(recursive=True)

    expected = Decimal("21474836469978525163.53")
    assert document["items"][0]["lineTotal"] == expected
    assert document["orderTotal"] == expected
    assert (
        dict(build_order_documents(order_frame, item_frame).dtypes)["orderTotal"] == "decimal(38,2)"
    )


@pytest.mark.parametrize(
    ("target", "field", "message"),
    [
        ("orders", "is_deleted", "null order deletion flag"),
        ("items", "is_deleted", "null item deletion flag"),
        ("items", "order_id", "null item business key"),
        ("items", "line_number", "null item business key"),
        ("items", "quantity", "invalid quantity"),
        ("items", "unit_price", "invalid price"),
        ("orders", "customer_id", "null required order value"),
        ("orders", "customer_first_name", "null required order value"),
        ("orders", "customer_last_name", "null required order value"),
        ("orders", "customer_email", "null required order value"),
        ("orders", "order_status", "null required order value"),
        ("orders", "ordered_at", "null required order value"),
        ("orders", "updated_at", "null required order value"),
        ("items", "sku", "null required item value"),
        ("items", "updated_at", "null required item value"),
    ],
)
def test_null_source_values_fail_explicitly(
    spark: SparkSession, target: str, field: str, message: str
) -> None:
    orders = valid_orders()
    items = valid_items()
    rows = orders if target == "orders" else items
    rows[0] = rows[0] | {field: None}
    order_frame, item_frame = frames(spark, orders, items)

    with pytest.raises(ValueError, match=message):
        build_order_documents(order_frame, item_frame)


def test_negative_quantity_fails_explicitly(spark: SparkSession) -> None:
    items = valid_items()
    items[0] = items[0] | {"quantity": -1}
    orders, item_frame = frames(spark, items=items)

    with pytest.raises(ValueError, match="invalid quantity"):
        build_order_documents(orders, item_frame)
