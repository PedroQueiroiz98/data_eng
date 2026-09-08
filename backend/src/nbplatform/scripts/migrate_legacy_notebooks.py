"""Migra os notebooks do módulo global (tabela `notebooks`) para arquivos `.ipynb`
dentro de um Workspace "Importação" por usuário criador.

Uso (uma vez, após `alembic upgrade head`):

    python -m nbplatform.scripts.migrate_legacy_notebooks [--dry-run]

Idempotente: rodar de novo não duplica arquivos nem religa tasks já religadas.
As tabelas `notebooks`/`notebook_versions` são preservadas (histórico de execuções).
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.errors import NotFoundError
from nbplatform.db.session import dispose_engine, session_scope
from nbplatform.domain.workspace_layout import slugify
from nbplatform.models.notebook import Notebook, NotebookVersion
from nbplatform.models.user import User
from nbplatform.models.workflow import WorkflowTask
from nbplatform.models.workspace import Workspace
from nbplatform.services.workspace_fs_service import WorkspaceFsService
from nbplatform.services.workspace_service import WorkspaceService

_WS_NAME = "Importação"
_WS_DESC = "Notebooks migrados do módulo antigo de notebooks."


def _fs(svc: WorkspaceService, workspace_id: uuid.UUID) -> WorkspaceFsService:
    s = get_settings()
    return WorkspaceFsService(
        svc.root_for(workspace_id),
        max_upload_bytes=s.workspace_max_upload_bytes,
        max_nodes=s.workspace_tree_max_nodes,
        max_depth=s.workspace_tree_max_depth,
    )


async def _admin_id(session: AsyncSession) -> uuid.UUID | None:
    row = await session.scalar(
        select(User.id).where(User.role == "admin").order_by(User.created_at).limit(1)
    )
    if row is not None:
        return row
    return await session.scalar(select(User.id).order_by(User.created_at).limit(1))


async def _find_or_create_ws(svc: WorkspaceService, owner_id: uuid.UUID) -> Workspace:
    existing = await svc.session.scalar(
        select(Workspace)
        .where(
            Workspace.name == _WS_NAME,
            Workspace.owner_id == owner_id,
            Workspace.is_active.is_(True),
        )
        .order_by(Workspace.created_at)
        .limit(1)
    )
    if existing is not None:
        return existing
    return await svc.create(name=_WS_NAME, description=_WS_DESC, owner_id=owner_id)


async def run(dry_run: bool) -> dict[str, int]:
    stats = {"users": 0, "workspaces": 0, "files": 0, "skipped": 0, "tasks_relinked": 0}
    async with session_scope() as session:
        svc = WorkspaceService(session)
        admin = await _admin_id(session)

        notebooks = list(await session.scalars(select(Notebook).order_by(Notebook.created_at)))
        if not notebooks:
            print("nenhum notebook legado — nada a migrar.")
            return stats

        by_owner: dict[uuid.UUID, list[Notebook]] = {}
        for nb in notebooks:
            owner = nb.created_by or admin
            if owner is None:
                print("sem usuário admin no banco; abortando.", file=sys.stderr)
                return stats
            by_owner.setdefault(owner, []).append(nb)

        mapping: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}

        for owner_id, group in by_owner.items():
            stats["users"] += 1
            if dry_run:
                print(f"[dry-run] usuário {owner_id}: {len(group)} notebook(s) → {_WS_NAME}")
                continue
            ws = await _find_or_create_ws(svc, owner_id)
            stats["workspaces"] += 1
            fs = _fs(svc, ws.id)

            for nb in group:
                version = await session.scalar(
                    select(NotebookVersion).where(
                        NotebookVersion.notebook_id == nb.id,
                        NotebookVersion.version_number == nb.current_version,
                    )
                )
                if version is None:
                    stats["skipped"] += 1
                    continue
                rel = f"notebooks/{slugify(nb.name) or 'notebook'}-{nb.id.hex[:8]}.ipynb"
                try:
                    await fs.read_file(rel)
                    stats["skipped"] += 1  # já migrado
                except NotFoundError:
                    await fs.write_file(rel, text=None, notebook=version.content)
                    stats["files"] += 1
                mapping[nb.id] = (ws.id, rel)

        if not dry_run and mapping:
            for nb_id, (ws_id, rel) in mapping.items():
                result = await session.execute(
                    update(WorkflowTask)
                    .where(
                        WorkflowTask.notebook_id == nb_id,
                        WorkflowTask.workspace_id.is_(None),
                    )
                    .values(workspace_id=ws_id, notebook_path=rel)
                )
                stats["tasks_relinked"] += int(getattr(result, "rowcount", 0) or 0)

    return stats


def main() -> int:
    dry_run = "--dry-run" in sys.argv[1:]
    stats = asyncio.run(_main(dry_run))
    print(
        "migração concluída: "
        f"{stats['users']} usuário(s), {stats['workspaces']} workspace(s), "
        f"{stats['files']} arquivo(s) escrito(s), {stats['skipped']} pulado(s), "
        f"{stats['tasks_relinked']} task(s) de workflow religada(s)."
    )
    return 0


async def _main(dry_run: bool) -> dict[str, int]:
    try:
        return await run(dry_run)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
