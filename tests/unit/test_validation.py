from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal

import pytest

from glue_lab.validation import reconcile_summaries, write_redacted_result


def source_summary() -> dict[str, object]:
    return {
        "orders": [
            {
                "order_id": 1001,
                "customer": {"id": 42, "name": "Ava Smith", "email": "ava@example.com"},
                "ordered_at": "2026-08-01T14:30:00Z",
                "updated_at": "2026-08-01T15:10:00Z",
                "status": "SHIPPED",
                "items": [
                    {
                        "id": 5001,
                        "line_number": 1,
                        "sku": "KB-101",
                        "quantity": 2,
                        "unit_price": "25.00",
                        "line_total": "50.00",
                    },
                    {
                        "id": 5002,
                        "line_number": 2,
                        "sku": "MS-205",
                        "quantity": 1,
                        "unit_price": "19.95",
                        "line_total": "19.95",
                    },
                ],
                "order_total": "69.95",
            },
            {
                "order_id": 1002,
                "customer": {
                    "id": 77,
                    "name": "Mateo Garcia",
                    "email": "mateo@example.com",
                },
                "ordered_at": "2026-08-02T16:15:00Z",
                "updated_at": "2026-08-02T16:45:00Z",
                "status": "PROCESSING",
                "items": [
                    {
                        "id": 5003,
                        "line_number": 1,
                        "sku": "MON-24",
                        "quantity": 1,
                        "unit_price": "199.99",
                        "line_total": "199.99",
                    }
                ],
                "order_total": "199.99",
            },
        ],
        "deleted_order_ids": [1004],
        "deleted_item_ids": [5009],
    }


def target_summary() -> dict[str, object]:
    source = source_summary()
    documents = []
    for order in source["orders"]:
        order = deepcopy(order)
        documents.append(
            {
                "_id": order["order_id"],
                "customer": order["customer"],
                "orderedAt": order["ordered_at"],
                "updatedAt": order["updated_at"],
                "status": order["status"],
                "items": [
                    {
                        "id": item["id"],
                        "lineNumber": item["line_number"],
                        "sku": item["sku"],
                        "quantity": item["quantity"],
                        "unitPrice": item["unit_price"],
                        "lineTotal": item["line_total"],
                    }
                    for item in order["items"]
                ],
                "orderTotal": order["order_total"],
                "migration": {"source": "postgresql", "mode": "snapshot"},
            }
        )
    return {"documents": documents}


def test_matching_summaries_pass_with_exact_counts_and_no_record_data() -> None:
    result = reconcile_summaries(source_summary(), target_summary())

    assert result == {
        "schema_version": 1,
        "passed": True,
        "counts": {
            "active_source_orders": 2,
            "active_source_items": 3,
            "target_documents": 2,
            "target_embedded_items": 3,
        },
        "mismatch_categories": {},
        "mismatch_count": 0,
    }
    serialized = json.dumps(result, sort_keys=True)
    for forbidden in ("Ava", "ava@example.com", "KB-101", "1001", "5001"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("mutate", "categories"),
    [
        (lambda t: t["documents"].pop(), {"active_order_count", "missing_target_key"}),
        (
            lambda t: t["documents"].append(deepcopy(t["documents"][0]) | {"_id": 9999}),
            {"active_order_count", "stale_target"},
        ),
        (
            lambda t: t["documents"][0]["items"].pop(),
            {"active_item_count", "per_order_item_count", "item_keys", "order_total"},
        ),
        (
            lambda t: t["documents"][0].update(orderTotal="69.9500000000000000001"),
            {"order_total"},
        ),
        (
            lambda t: t["documents"][0]["items"].reverse(),
            {"line_ordering", "item_keys"},
        ),
        (
            lambda t: t["documents"][0]["customer"].update(email="Ava@Example.com"),
            {"normalization"},
        ),
    ],
)
def test_reconciliation_reports_each_bounded_mismatch_category(mutate, categories) -> None:
    target = target_summary()
    mutate(target)

    result = reconcile_summaries(source_summary(), target)

    assert result["passed"] is False
    assert categories <= set(result["mismatch_categories"])
    assert result["mismatch_count"] == sum(result["mismatch_categories"].values())


def test_deleted_entities_and_stale_soft_deleted_target_are_detected() -> None:
    target = target_summary()
    stale = deepcopy(target["documents"][0])
    stale["_id"] = 1004
    stale["items"][0]["id"] = 5009
    target["documents"].append(stale)

    result = reconcile_summaries(source_summary(), target)

    assert result["passed"] is False
    assert result["mismatch_categories"]["deleted_order_present"] == 1
    assert result["mismatch_categories"]["deleted_item_present"] == 1
    assert result["mismatch_categories"]["stale_target"] == 1


def test_duplicate_and_invalid_keys_fail_closed_without_exposing_keys() -> None:
    source = source_summary()
    source["orders"].append(deepcopy(source["orders"][0]))
    target = target_summary()
    target["documents"].append(deepcopy(target["documents"][0]))

    result = reconcile_summaries(source, target)

    assert result["passed"] is False
    assert result["mismatch_categories"]["duplicate_source_key"] == 1
    assert result["mismatch_categories"]["duplicate_target_key"] == 1
    assert "1001" not in json.dumps(result)


@pytest.mark.parametrize("value", [1.1, "NaN", "Infinity", "not-money"])
def test_decimal_boundary_rejects_float_or_nonfinite_values(value) -> None:
    target = target_summary()
    target["documents"][0]["orderTotal"] = value

    result = reconcile_summaries(source_summary(), target)

    assert result["passed"] is False
    assert result["mismatch_categories"]["invalid_summary"] >= 1


def test_exact_decimal_comparison_accepts_equivalent_scale() -> None:
    target = target_summary()
    target["documents"][0]["orderTotal"] = "69.950"
    target["documents"][0]["items"][0]["unitPrice"] = "25.0"

    result = reconcile_summaries(source_summary(), target)

    assert result["passed"] is True
    assert Decimal("69.950") == Decimal("69.95")


def test_result_artifact_is_mode_0600_and_contains_only_redacted_summary(tmp_path) -> None:
    result = reconcile_summaries(source_summary(), target_summary())
    output = tmp_path / "nested" / "result.json"

    write_redacted_result(output, result)

    assert output.stat().st_mode & 0o777 == 0o600
    assert output.parent.stat().st_mode & 0o777 == 0o700
    assert json.loads(output.read_text()) == result
