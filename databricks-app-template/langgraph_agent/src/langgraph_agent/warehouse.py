from __future__ import annotations

import os

from databricks import sql

from .config import load_config


UC_CATALOG = os.environ.get(
    "DATABRICKS_UC_CATALOG",
    "uc-specializednutrition-rnd-prd-001",
)
UC_SCHEMA = os.environ.get(
    "DATABRICKS_UC_SCHEMA",
    "sn_quality_control_dev",
)


def get_warehouse_connection():
    config = load_config(require_model_endpoint=False)
    return sql.connect(
        server_hostname=config.server_hostname,
        http_path=config.http_path,
        access_token=config.token,
    )


def _execute_statement(connection, statement: str):
    with connection.cursor() as cursor:
        cursor.execute(statement)
        return cursor.fetchall()


def get_data_from_warehouse(statement: str):
    connection = get_warehouse_connection()
    try:
        return _execute_statement(connection, statement)
    except Exception as exc:
        if "Invalid SessionHandle" in str(exc):
            try:
                connection.close()
            except Exception:
                pass
            connection = get_warehouse_connection()
            return _execute_statement(connection, statement)
        raise
    finally:
        try:
            connection.close()
        except Exception:
            pass
