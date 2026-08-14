"""Thin AWS Glue entrypoint for the PostgreSQL orders snapshot."""

from __future__ import annotations

import logging
import sys
import time

from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

from glue_lab.transformations import build_order_documents

ARGUMENTS = [
    "JOB_NAME",
    "CATALOG_DATABASE",
    "ORDERS_TABLE",
    "ORDER_ITEMS_TABLE",
    "MONGODB_CONNECTION",
    "MONGODB_DATABASE",
    "MONGODB_COLLECTION",
    "SNAPSHOT_MODE",
]
LOGGER = logging.getLogger(__name__)


def _duration(started: float) -> float:
    return max(0.0, time.monotonic() - started)


def main() -> None:
    overall_started = time.monotonic()
    phase = "arguments"
    logger = LOGGER
    orders = None
    items = None
    documents = None
    try:
        args = getResolvedOptions(sys.argv, ARGUMENTS)
        if args["SNAPSHOT_MODE"] != "snapshot":
            raise ValueError("SNAPSHOT_MODE must be snapshot")

        glue_context = GlueContext(SparkContext.getOrCreate())
        logger = glue_context.get_logger()
        job = Job(glue_context)
        job.init(args["JOB_NAME"], args)

        phase = "catalog_read"
        phase_started = time.monotonic()
        orders = (
            glue_context.create_dynamic_frame.from_catalog(
                database=args["CATALOG_DATABASE"],
                table_name=args["ORDERS_TABLE"],
                transformation_ctx="orders_source",
            )
            .toDF()
            .cache()
        )
        items = (
            glue_context.create_dynamic_frame.from_catalog(
                database=args["CATALOG_DATABASE"],
                table_name=args["ORDER_ITEMS_TABLE"],
                transformation_ctx="order_items_source",
            )
            .toDF()
            .cache()
        )
        orders_count = orders.count()
        items_count = items.count()
        logger.info(
            f"phase=catalog_read outcome=success orders_count={orders_count} "
            f"items_count={items_count} duration_seconds={_duration(phase_started):.3f}"
        )

        phase = "transform"
        phase_started = time.monotonic()
        documents = build_order_documents(orders, items).cache()
        documents_count = documents.count()
        logger.info(
            f"phase=transform outcome=success documents_count={documents_count} "
            f"duration_seconds={_duration(phase_started):.3f}"
        )

        phase = "mongodb_write"
        phase_started = time.monotonic()
        glue_context.write_dynamic_frame.from_options(
            frame=DynamicFrame.fromDF(documents, glue_context, "order_documents"),
            connection_type="mongodb",
            connection_options={
                "connectionName": args["MONGODB_CONNECTION"],
                "database": args["MONGODB_DATABASE"],
                "collection": args["MONGODB_COLLECTION"],
                "replaceDocument": "true",
            },
            transformation_ctx="mongodb_orders_sink",
        )
        logger.info(
            f"phase=mongodb_write outcome=success documents_count={documents_count} "
            f"duration_seconds={_duration(phase_started):.3f}"
        )
        job.commit()
        logger.info(f"phase=job outcome=success duration_seconds={_duration(overall_started):.3f}")
    except Exception:
        logger.error(
            f"phase={phase} outcome=failed duration_seconds={_duration(overall_started):.3f}"
        )
        raise
    finally:
        for frame in (documents, items, orders):
            if frame is not None:
                frame.unpersist()


if __name__ == "__main__":
    main()
