# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from pydantic import BaseModel

from nat.builder.workflow_builder import WorkflowBuilder
from nat.front_ends.fastapi.fastapi_front_end_plugin_worker import FastApiFrontEndPluginWorker
from nat.runtime.session import SessionManager
from nat.utils.type_utils import override

logger = logging.getLogger(__name__)


class MlflowFeedbackPayload(BaseModel):
    """Payload for adding feedback to an MLflow run."""

    observability_trace_id: str
    reaction_type: str
    comment: str | None = None


class MlflowFeedbackResponse(BaseModel):
    """Response for feedback submission."""

    message: str


class MlflowFastAPIPluginWorker(FastApiFrontEndPluginWorker):
    """FastAPI plugin worker that adds an MLflow-backed feedback endpoint."""

    @override
    async def add_routes(self, app: FastAPI, builder: WorkflowBuilder) -> None:
        await super().add_routes(app, builder)
        await self._add_mlflow_feedback_route(app, builder)

    async def _add_mlflow_feedback_route(self, app: FastAPI, builder: WorkflowBuilder) -> None:
        mlflow_config = None
        for exporter_config in builder._telemetry_exporters.values():
            if exporter_config.config.__class__.__name__ == 'MlflowTelemetryExporter':
                mlflow_config = exporter_config.config
                break

        if not mlflow_config:
            logger.debug("MLflow telemetry not configured, skipping feedback endpoint")
            return

        try:
            session_manager = await SessionManager.create(config=self._config, shared_builder=builder)

            async def add_chat_feedback(request: Request,
                                        payload: MlflowFeedbackPayload) -> MlflowFeedbackResponse:
                async with session_manager.session(http_connection=request,
                                                   user_authentication_callback=self._http_flow_handler.authenticate):
                    run_id = payload.observability_trace_id
                    reaction_type = payload.reaction_type

                    reaction_value = 0.0
                    if reaction_type == "👍":
                        reaction_value = 1.0
                    elif reaction_type == "👎":
                        reaction_value = -1.0

                    try:
                        from mlflow.tracking import MlflowClient

                        client = MlflowClient(tracking_uri=mlflow_config.tracking_uri)
                        client.log_metric(run_id, "feedback", reaction_value)
                        client.set_tag(run_id, "feedback.reaction", reaction_type)
                        if payload.comment:
                            client.set_tag(run_id, "feedback.comment", payload.comment)
                        return MlflowFeedbackResponse(
                            message=f"Recorded feedback '{reaction_type}' for run {run_id}")
                    except Exception as exc:
                        logger.exception("Failed to log feedback to MLflow")
                        raise HTTPException(status_code=500,
                                            detail=f"Failed to log feedback: {exc}") from exc

            app.add_api_route(
                path="/feedback",
                endpoint=add_chat_feedback,
                methods=["POST"],
                description="Set reaction feedback for an assistant message via observability trace ID",
                responses={
                    500: {
                        "description": "Internal Server Error",
                        "content": {
                            "application/json": {
                                "example": {
                                    "detail": "Internal server error occurred"
                                }
                            }
                        },
                    }
                },
            )

            logger.info("Registered MLflow feedback endpoint at /feedback")
        except Exception as exc:
            logger.warning("Failed to register MLflow feedback endpoint: %s", exc)
