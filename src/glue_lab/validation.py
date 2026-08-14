"""Pure, deterministic reconciliation for bounded lab summaries.

The inputs contain only projected synthetic fields.  The returned result deliberately
contains counts and mismatch categories, never keys or records, so it is safe to retain
as user-run evidence.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

Result = dict[str, Any]


def _money(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("money must be an exact decimal string or integer")
    if not isinstance(value, str | int | Decimal):
        raise ValueError("money has an unsupported type")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("money is not decimal") from error
    if not number.is_finite():
        raise ValueError("money must be finite")
    return number


def _list(value: object, mismatches: Counter[str]) -> list[Any]:
    if not isinstance(value, list):
        mismatches["invalid_summary"] += 1
        return []
    return value


def _index(
    records: list[Any],
    key_name: str,
    duplicate_category: str,
    mismatches: Counter[str],
) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            mismatches["invalid_summary"] += 1
            continue
        key = record.get(key_name)
        if isinstance(key, bool) or not isinstance(key, int):
            mismatches["invalid_summary"] += 1
            continue
        if key in indexed:
            mismatches[duplicate_category] += 1
            continue
        indexed[key] = record
    return indexed


def _decimal_equal(left: object, right: object, mismatches: Counter[str], category: str) -> bool:
    try:
        equal = _money(left) == _money(right)
    except ValueError:
        mismatches["invalid_summary"] += 1
        return False
    if not equal:
        mismatches[category] += 1
    return equal


def _source_totals_are_exact(order: dict[str, Any], mismatches: Counter[str]) -> None:
    items = _list(order.get("items"), mismatches)
    try:
        calculated_lines = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("item is not an object")
            quantity = item.get("quantity")
            if isinstance(quantity, bool) or not isinstance(quantity, int):
                raise ValueError("quantity is not an integer")
            calculated = Decimal(quantity) * _money(item.get("unit_price"))
            calculated_lines.append(calculated)
            if calculated != _money(item.get("line_total")):
                mismatches["source_line_total"] += 1
        if sum(calculated_lines, Decimal(0)) != _money(order.get("order_total")):
            mismatches["source_order_total"] += 1
    except ValueError:
        mismatches["invalid_summary"] += 1


def _compare_order(
    source: dict[str, Any], target: dict[str, Any], mismatches: Counter[str]
) -> None:
    source_items = _list(source.get("items"), mismatches)
    target_items = _list(target.get("items"), mismatches)
    if len(source_items) != len(target_items):
        mismatches["per_order_item_count"] += 1

    source_ids: list[object] = []
    source_lines: list[object] = []
    target_ids: list[object] = []
    target_lines: list[object] = []
    valid_source_items: list[dict[str, Any]] = []
    valid_target_items: list[dict[str, Any]] = []
    for item in source_items:
        if not isinstance(item, dict):
            mismatches["invalid_summary"] += 1
            continue
        valid_source_items.append(item)
        source_ids.append(item.get("id"))
        source_lines.append(item.get("line_number"))
    for item in target_items:
        if not isinstance(item, dict):
            mismatches["invalid_summary"] += 1
            continue
        valid_target_items.append(item)
        target_ids.append(item.get("id"))
        target_lines.append(item.get("lineNumber"))

    if source_ids != target_ids or source_lines != target_lines:
        mismatches["item_keys"] += 1
    if any(
        isinstance(line, bool) or not isinstance(line, int) for line in target_lines
    ) or target_lines != sorted(target_lines):
        mismatches["line_ordering"] += 1

    target_line_sum = Decimal(0)
    target_line_sum_valid = True
    for source_item, target_item in zip(valid_source_items, valid_target_items, strict=False):
        scalar_pairs = (
            ("id", "id"),
            ("line_number", "lineNumber"),
            ("sku", "sku"),
            ("quantity", "quantity"),
        )
        if any(source_item.get(left) != target_item.get(right) for left, right in scalar_pairs):
            mismatches["item_values"] += 1
        _decimal_equal(
            source_item.get("unit_price"),
            target_item.get("unitPrice"),
            mismatches,
            "item_values",
        )
        _decimal_equal(
            source_item.get("line_total"),
            target_item.get("lineTotal"),
            mismatches,
            "line_total",
        )
    for target_item in valid_target_items:
        try:
            target_line_sum += _money(target_item.get("lineTotal"))
        except ValueError:
            target_line_sum_valid = False

    normalization_pairs = (
        (source.get("customer"), target.get("customer")),
        (source.get("ordered_at"), target.get("orderedAt")),
        (source.get("updated_at"), target.get("updatedAt")),
        (source.get("status"), target.get("status")),
        ({"source": "postgresql", "mode": "snapshot"}, target.get("migration")),
    )
    if any(left != right for left, right in normalization_pairs):
        mismatches["normalization"] += 1
    if target_line_sum_valid:
        try:
            if target_line_sum != _money(target.get("orderTotal")):
                mismatches["order_total"] += 1
        except ValueError:
            mismatches["invalid_summary"] += 1
    else:
        mismatches["invalid_summary"] += 1
    _decimal_equal(source.get("order_total"), target.get("orderTotal"), mismatches, "order_total")


def _valid_deleted_keys(value: object, mismatches: Counter[str]) -> set[int]:
    keys: set[int] = set()
    for key in _list(value, mismatches):
        if isinstance(key, bool) or not isinstance(key, int):
            mismatches["invalid_summary"] += 1
        else:
            keys.add(key)
    return keys


def reconcile_summaries(source: object, target: object) -> Result:
    """Reconcile bounded source/target summaries and return a redacted result.

    Any malformed boundary value is reported as ``invalid_summary`` rather than
    raising with record content.  Mismatches never include actual identifiers.
    """

    mismatches: Counter[str] = Counter()
    if not isinstance(source, dict) or not isinstance(target, dict):
        mismatches["invalid_summary"] += 1
        source = source if isinstance(source, dict) else {}
        target = target if isinstance(target, dict) else {}

    source_orders = _list(source.get("orders"), mismatches)
    target_documents = _list(target.get("documents"), mismatches)
    source_index = _index(source_orders, "order_id", "duplicate_source_key", mismatches)
    target_index = _index(target_documents, "_id", "duplicate_target_key", mismatches)

    source_item_count = sum(
        len(order.get("items", []))
        for order in source_index.values()
        if isinstance(order.get("items"), list)
    )
    target_item_count = sum(
        len(document.get("items", []))
        for document in target_index.values()
        if isinstance(document.get("items"), list)
    )
    if len(source_index) != len(target_index):
        mismatches["active_order_count"] += abs(len(source_index) - len(target_index)) or 1
    if source_item_count != target_item_count:
        mismatches["active_item_count"] += abs(source_item_count - target_item_count) or 1

    source_keys = set(source_index)
    target_keys = set(target_index)
    missing = source_keys - target_keys
    stale = target_keys - source_keys
    mismatches["missing_target_key"] += len(missing)
    mismatches["stale_target"] += len(stale)

    deleted_orders = _valid_deleted_keys(source.get("deleted_order_ids"), mismatches)
    deleted_items = _valid_deleted_keys(source.get("deleted_item_ids"), mismatches)
    mismatches["deleted_order_present"] += len(target_keys & deleted_orders)
    target_item_ids: set[int] = set()
    for document in target_index.values():
        for item in _list(document.get("items"), mismatches):
            if isinstance(item, dict):
                item_id = item.get("id")
                if isinstance(item_id, int) and not isinstance(item_id, bool):
                    target_item_ids.add(item_id)
                else:
                    mismatches["invalid_summary"] += 1
            else:
                mismatches["invalid_summary"] += 1
    mismatches["deleted_item_present"] += len(target_item_ids & deleted_items)

    for key in sorted(source_keys & target_keys):
        _source_totals_are_exact(source_index[key], mismatches)
        _compare_order(source_index[key], target_index[key], mismatches)

    categories = {name: count for name, count in sorted(mismatches.items()) if count}
    counts = {
        "active_source_orders": len(source_index),
        "active_source_items": source_item_count,
        "target_documents": len(target_index),
        "target_embedded_items": target_item_count,
    }
    return {
        "schema_version": 1,
        "passed": not categories,
        "counts": counts,
        "mismatch_categories": categories,
        "mismatch_count": sum(categories.values()),
    }


def write_redacted_result(path: str | os.PathLike[str], result: Result) -> None:
    """Write a redacted result to a private directory and mode-0600 file."""

    destination = Path(path)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.parent.chmod(0o700)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".reconciliation-",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            temporary_path.chmod(0o600)
            json.dump(result, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        destination.chmod(0o600)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
