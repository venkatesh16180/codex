# test_download_models.py -- Phase 20
from download_models import missing_ollama_models


def test_bare_name_matches_the_latest_tag():
    assert missing_ollama_models(['llama3.2'], ['llama3.2:latest']) == []


def test_exact_tagged_name_matches():
    assert missing_ollama_models(['qwen3:4b'], ['qwen3:4b']) == []


def test_only_the_missing_model_is_reported():
    assert missing_ollama_models(['qwen3:4b', 'llama3.2'], ['llama3.2:latest']) == ['qwen3:4b']


def test_a_different_tag_is_not_a_match():
    assert missing_ollama_models(['qwen3:4b'], ['qwen3:8b']) == ['qwen3:4b']
