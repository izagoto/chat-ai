from pathlib import Path

from app.services.rag import RagService


def test_rag_retrieve_from_sample_docs(tmp_path: Path, monkeypatch):
    docs = tmp_path / "docs"
    sample = docs / "sample"
    sample.mkdir(parents=True)
    (sample / "privacy.md").write_text(
        "Privacy principle: all inference stays on the local machine using Ollama.",
        encoding="utf-8",
    )

    svc = RagService()
    monkeypatch.setattr(
        "app.services.rag.settings.docs_path",
        str(docs),
    )
    count = svc.rebuild_index()
    assert count >= 1

    hits = svc.retrieve("local privacy Ollama inference", top_k=2)
    assert hits
    assert "privacy.md" in hits[0][0].file
