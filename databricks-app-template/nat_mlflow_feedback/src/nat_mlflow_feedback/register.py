# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.cli.register_workflow import register_telemetry_exporter
from nat.data_models.telemetry_exporter import TelemetryExporterBaseConfig

from .mlflow_exporter import MlflowTraceExporter

logger = logging.getLogger(__name__)


class MlflowTelemetryExporter(TelemetryExporterBaseConfig, name="mlflow"):
    """Telemetry exporter that writes trace IDs to MLflow runs."""

    experiment_name: str = Field(description="MLflow experiment name.")
    tracking_uri: str | None = Field(default=None, description="Optional MLflow tracking URI.")
    run_name: str | None = Field(default=None, description="Optional MLflow run name.")


@register_telemetry_exporter(config_type=MlflowTelemetryExporter)
async def mlflow_telemetry_exporter(config: MlflowTelemetryExporter, builder: Builder):
    try:
        exporter = MlflowTraceExporter(
            experiment_name=config.experiment_name,
            tracking_uri=config.tracking_uri,
            run_name=config.run_name,
        )
        yield exporter
    except Exception as exc:
        logger.error("Failed to initialize MLflow telemetry exporter: %s", exc)
        raise
