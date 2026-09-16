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

def test_upload_guardrail_defaults():
    from api.config import Settings
    s = Settings()
    assert (s.max_zip_mb, s.max_pdf_mb, s.upload_daily_cap, s.upload_url_ttl_s) == (25, 20, 50, 900)
    assert s.max_pdfs_per_zip == 20
