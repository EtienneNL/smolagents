# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging

from nat.data_models.intermediate_step import IntermediateStep
from nat.observability.exporter.base_exporter import IsolatedAttribute
from nat.observability.exporter.raw_exporter import RawExporter
from nat.utils.type_utils import override

logger = logging.getLogger(__name__)


class MlflowTraceExporter(RawExporter[IntermediateStep, IntermediateStep]):
    """Minimal MLflow exporter that sets observability_trace_id to the MLflow run ID."""

    _run_id: IsolatedAttribute[str | None] = IsolatedAttribute(lambda: None)
    _run_started: IsolatedAttribute[bool] = IsolatedAttribute(lambda: False)

    def __init__(self,
                 experiment_name: str,
                 tracking_uri: str | None = None,
                 run_name: str | None = None,
                 context_state=None):
        super().__init__(context_state=context_state)
        self._experiment_name = experiment_name
        self._tracking_uri = tracking_uri
        self._run_name = run_name

    def _ensure_run(self) -> None:
        if self._run_started:
            return
        from mlflow.tracking import MlflowClient

        client = MlflowClient(tracking_uri=self._tracking_uri)
        experiment = client.get_experiment_by_name(self._experiment_name)
        if experiment is None:
            experiment_id = client.create_experiment(self._experiment_name)
        else:
            experiment_id = experiment.experiment_id

        tags = {}
        if self._run_name:
            tags["mlflow.runName"] = self._run_name

        run = client.create_run(experiment_id=experiment_id, tags=tags)
        self._run_id = run.info.run_id
        self._run_started = True

        if self._context_state.observability_trace_id.get() is None:
            self._context_state.observability_trace_id.set(self._run_id)

        try:
            client.set_tag(self._run_id, "nat.observability_trace_id", self._run_id)
        except Exception as exc:
            logger.debug("Failed to set MLflow trace tag: %s", exc)

    @override
    async def export_processed(self, item: IntermediateStep) -> None:
        self._ensure_run()
        # Intentionally minimal: do not log every step by default.
        # You can add custom logging here if needed.

    @override
    async def _cleanup(self) -> None:
        if self._run_started and self._run_id:
            try:
                from mlflow.tracking import MlflowClient

                client = MlflowClient(tracking_uri=self._tracking_uri)
                client.set_terminated(self._run_id)
            except Exception as exc:
                logger.debug("Failed to terminate MLflow run: %s", exc)

        await super()._cleanup()
