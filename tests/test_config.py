from api.config import Settings

def test_new_aws_demo_settings_have_defaults():
    s = Settings()
    assert s.aws_region == "us-east-1"
    assert "claude-haiku-4-5" in s.bedrock_generation_model
    assert s.bedrock_embedding_model.startswith("amazon.titan-embed")
    assert s.demo_corpus_path.endswith("demo_corpus.json")
    assert s.allowed_origins == "*"
    assert s.demo_daily_cap == 500

def test_env_prefix_overrides(monkeypatch):
    monkeypatch.setenv("CENTRALDOGMA_AWS_REGION", "us-west-2")
    assert Settings().aws_region == "us-west-2"
