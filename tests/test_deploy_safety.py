from core.updater.deploy_safety import collect_deploy_safety_snapshot


def test_collect_deploy_safety_snapshot_reads_runtime_files(monkeypatch, tmp_path):
    app_dir = tmp_path / "app"
    processing_dir = app_dir / "data" / "voice" / "processing"
    blocker_dir = app_dir / "runtime" / "deploy-blockers"
    processing_dir.mkdir(parents=True)
    blocker_dir.mkdir(parents=True)
    (processing_dir / "chunk1.wav").write_text("x", encoding="utf-8")
    (blocker_dir / "manual.lock").write_text("x", encoding="utf-8")

    monkeypatch.setenv("APP_DIR", str(app_dir))
    monkeypatch.setenv("POSTGRES_USER", "fake")
    monkeypatch.setenv("POSTGRES_PASSWORD", "fake")
    monkeypatch.setattr(
        "core.updater.deploy_safety.psycopg2.connect",
        lambda **_: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    snapshot = collect_deploy_safety_snapshot()

    assert snapshot.voice_files_processing == 1
    assert snapshot.manual_blockers == 1
    assert snapshot.safe_to_deploy is False
