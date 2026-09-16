import importlib

import api.store_aurora as sa


def test_build_store_selects_aurora(monkeypatch):
    monkeypatch.setenv("CENTRALDOGMA_STORE_BACKEND", "aurora")
    monkeypatch.setenv("CENTRALDOGMA_EMBEDDER", "hashing")  # dependency-light embedder
    monkeypatch.setenv("CENTRALDOGMA_AURORA_CLUSTER_ARN", "arn:c")
    monkeypatch.setenv("CENTRALDOGMA_AURORA_SECRET_ARN", "arn:s")
    monkeypatch.setenv("CENTRALDOGMA_AURORA_DATABASE", "cd")
    sa._client = lambda region=None: object()  # avoid real boto3

    import api.config

    importlib.reload(api.config)
    import api.main

    importlib.reload(api.main)  # re-execute module-level _build_store() with fresh settings

    store = api.main._build_store()
    assert store.name == "aurora"
