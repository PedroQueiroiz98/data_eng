"""Kernel Python interativo (jupyter_client) — execução por célula com estado.

Processo dedicado `python -m nbplatform.kernel_worker`. Produção (Jobs, agendamentos,
`POST /api/workspaces/{id}/execute`) continua sendo Papermill — ver `nbplatform.worker`.
"""
