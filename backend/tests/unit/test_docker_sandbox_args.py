from __future__ import annotations

from nbplatform.worker.sandbox.docker_sandbox import build_docker_args


def test_docker_args_are_hardened() -> None:
    args = build_docker_args(
        container_name="nbp-exec-abc",
        workdir="/data/executions/abc",
        env={"MY_SECRET": "v", "ENVIRONMENT": "prod"},
        image="nbplatform-backend",
        cpus="1",
        memory="512m",
        pids_limit=256,
    )
    joined = " ".join(args)

    # não-privilegiado, sem socket do Docker
    assert "--privileged" not in joined
    assert "/var/run/docker.sock" not in joined

    # limites e isolamento
    assert "--cpus 1" in joined
    assert "--memory 512m" in joined
    assert "--pids-limit 256" in joined
    assert "--read-only" in args
    assert "--network" in args and "none" in args
    assert "no-new-privileges" in joined
    assert "--cap-drop" in args and "ALL" in args
    assert "/tmp:rw,size=128m" in joined

    # env vars repassadas
    assert "MY_SECRET=v" in args
    assert "ENVIRONMENT=prod" in args

    # roda o runner do papermill dentro do container
    assert "python" in args
    assert "nbplatform.worker.papermill_runner" in args
    assert args[-3:] == [
        "/work/input.ipynb",
        "/work/output.ipynb",
        "/work/params.json",
    ]
