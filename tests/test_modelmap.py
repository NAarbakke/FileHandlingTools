import modelmap


def test_get_model_reads_config():
    assert modelmap.get_model("translate", "translate") == "gemma2:2b"
    assert modelmap.get_model("transcribe", "transcribe") == "qwen2.5vl:3b"
    assert modelmap.get_model("transcribe", "cleanup") == "gemma2:2b"


def test_get_model_unknown_returns_default():
    assert modelmap.get_model("nope", "nope") is None
    assert modelmap.get_model("transcribe", "nope", default="x") == "x"


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL_TRANSCRIBE_TRANSCRIBE", "moondream")
    assert modelmap.get_model("transcribe", "transcribe") == "moondream"
