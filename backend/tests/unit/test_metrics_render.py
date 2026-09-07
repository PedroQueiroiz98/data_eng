from __future__ import annotations

from nbplatform.core.metrics import render


def test_render_produces_prometheus_text() -> None:
    out = render(
        {
            "nbp_executions_total": 10,
            "nbp_executions_success_total": 7,
            "nbp_executions_failed_total": 3,
            "nbp_execution_duration_seconds_sum": 12.5,
            "nbp_jobs_running": 1,
        }
    )
    assert "# TYPE nbp_executions_total counter" in out
    assert "nbp_executions_total 10" in out
    assert "# TYPE nbp_jobs_running gauge" in out
    assert "nbp_jobs_running 1" in out
    assert "nbp_execution_duration_seconds_sum 12.5" in out
    # métricas ausentes do snapshot saem com 0
    assert "nbp_queue_size 0" in out
    assert out.endswith("\n")
