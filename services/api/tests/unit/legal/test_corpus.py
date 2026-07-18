"""Policy corpus loading + grounded retrieval tests (ADR-0002).

All policy documents referenced here are the packaged synthetic corpus,
clearly labelled "Chính sách tổng hợp (synthetic) — không phải chính sách
chính thức của SHB"; none is an official SHB policy.
"""

from __future__ import annotations

import json
from importlib import resources

import pytest

from creditops.application.legal.corpus import (
    PolicyCorpus,
    PolicyCorpusIntegrityError,
    load_corpus,
    try_load_default_corpus,
)


class TestLoadAndChecksum:
    def test_default_corpus_loads_and_is_labelled_synthetic(self) -> None:
        corpus = load_corpus()
        assert corpus.is_synthetic is True
        assert "synthetic" in corpus.disclaimer_vi.casefold() or (
            "không phải chính sách chính thức" in corpus.disclaimer_vi
        )
        assert "synthetic" in corpus.disclaimer_en.casefold()
        assert len(corpus.documents) >= 4

    def test_try_load_default_corpus_returns_a_corpus(self) -> None:
        corpus = try_load_default_corpus()
        assert corpus is not None
        assert corpus.corpus_id == "SHB-SYNTHETIC-POLICY-CORPUS"

    def test_checksum_mismatch_is_rejected(self, tmp_path, monkeypatch) -> None:
        config_text = (
            resources.files("creditops.policy_corpus")
            .joinpath("config_v1.json")
            .read_text(encoding="utf-8")
        )
        config = json.loads(config_text)
        config["checksum_sha256"] = "0" * 64
        tampered_dir = tmp_path / "policy_corpus"
        tampered_dir.mkdir()
        (tampered_dir / "config_v1.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
        (tampered_dir / "documents_v1.json").write_text(
            resources.files("creditops.policy_corpus")
            .joinpath("documents_v1.json")
            .read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        import creditops.application.legal.corpus as corpus_module

        def fake_read(filename: str) -> str:
            return (tampered_dir / filename).read_text(encoding="utf-8")

        monkeypatch.setattr(corpus_module, "_read_package_text", fake_read)
        monkeypatch.setattr(
            corpus_module.resources,
            "files",
            lambda pkg: tampered_dir if pkg == "creditops.policy_corpus" else resources.files(pkg),
        )
        with pytest.raises(PolicyCorpusIntegrityError):
            corpus_module.load_corpus()

    def test_try_load_returns_none_on_checksum_mismatch(self, monkeypatch) -> None:
        import creditops.application.legal.corpus as corpus_module

        def broken_load(version: str = "v1") -> PolicyCorpus:
            raise PolicyCorpusIntegrityError("tampered")

        monkeypatch.setattr(corpus_module, "load_corpus", broken_load)
        assert corpus_module.try_load_default_corpus() is None


class TestGroundedRetrieval:
    def test_search_returns_clause_level_hits_with_exact_quotes(self) -> None:
        corpus = load_corpus()
        hits = corpus.search("tài sản bảo đảm giấy chứng nhận quyền sử dụng đất", top_k=3)
        assert hits
        for hit in hits:
            clause = corpus.clause(hit.document_id, hit.clause_id)
            assert clause is not None
            assert hit.quoted_text_vi == clause.text_vi

    def test_retrieve_relevant_covers_every_document(self) -> None:
        corpus = load_corpus()
        hits = corpus.retrieve_relevant("kiểm tra pháp lý", top_k_per_document=1)
        document_ids = {hit.document_id for hit in hits}
        assert document_ids == {doc.document_id for doc in corpus.documents}

    def test_valid_citation_is_grounded(self) -> None:
        corpus = load_corpus()
        clause = corpus.clause("tai_san_bao_dam", "TSBD-01")
        assert clause is not None
        assert corpus.citation_is_grounded(
            corpus_id=corpus.corpus_id,
            corpus_version=corpus.version,
            document_id="tai_san_bao_dam",
            clause_id="TSBD-01",
            quoted_text_vi=clause.text_vi,
        )

    def test_citation_to_nonexistent_clause_is_rejected(self) -> None:
        corpus = load_corpus()
        assert not corpus.citation_is_grounded(
            corpus_id=corpus.corpus_id,
            corpus_version=corpus.version,
            document_id="tai_san_bao_dam",
            clause_id="TSBD-99",
            quoted_text_vi="Điều khoản không tồn tại.",
        )

    def test_citation_to_nonexistent_document_is_rejected(self) -> None:
        corpus = load_corpus()
        assert not corpus.citation_is_grounded(
            corpus_id=corpus.corpus_id,
            corpus_version=corpus.version,
            document_id="khong_ton_tai",
            clause_id="X-01",
            quoted_text_vi="Điều khoản không tồn tại.",
        )

    def test_citation_to_wrong_version_is_rejected(self) -> None:
        corpus = load_corpus()
        clause = corpus.clause("tai_san_bao_dam", "TSBD-01")
        assert clause is not None
        assert not corpus.citation_is_grounded(
            corpus_id=corpus.corpus_id,
            corpus_version="v999-nonexistent",
            document_id="tai_san_bao_dam",
            clause_id="TSBD-01",
            quoted_text_vi=clause.text_vi,
        )

    def test_citation_with_altered_quote_is_rejected(self) -> None:
        corpus = load_corpus()
        assert not corpus.citation_is_grounded(
            corpus_id=corpus.corpus_id,
            corpus_version=corpus.version,
            document_id="tai_san_bao_dam",
            clause_id="TSBD-01",
            quoted_text_vi="Một câu trích dẫn đã bị chỉnh sửa, không đúng nguyên văn.",
        )
