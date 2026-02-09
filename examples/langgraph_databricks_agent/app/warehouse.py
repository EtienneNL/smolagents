from __future__ import annotations

import os

from databricks import sql

UC_CATALOG = os.environ.get(
    "DATABRICKS_UC_CATALOG",
    "uc-specializednutrition-rnd-prd-001",
)
UC_SCHEMA = os.environ.get(
    "DATABRICKS_UC_SCHEMA",
    "sn_quality_control_dev",
)


def get_warehouse_connection():
    return sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def get_data_from_warehouse(statement: str):
    connection = get_warehouse_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement)
            rows = cursor.fetchall()
            return rows
    except Exception as exc:
        if "Invalid SessionHandle" in str(exc):
            connection = get_warehouse_connection()
            with connection.cursor() as cursor:
                cursor.execute(statement)
                rows = cursor.fetchall()
                return rows
        raise
