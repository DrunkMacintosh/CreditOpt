"""Synthetic versioned policy corpus + deterministic clause retrieval (ADR-0002).

Per ADR-0002 the Legal, Compliance and Collateral Agent retrieves policies
against an approved, versioned, checksum-verified SYNTHETIC corpus.  Every
document carries the mandatory disclaimer and must never be described as
official SHB policy (AGENTS.md).  Retrieval is deterministic keyword/lexical
scoring — no live embedding dependency — and every hit is, by construction,
an exact clause taken from the loaded corpus, so a hit can never itself be
ungrounded.  ``citation_is_grounded`` lets an arbitrary (e.g. LLM-claimed)
citation be checked against the loaded corpus independent of retrieval.

Fail closed: if no corpus is configured, or the packaged content does not
match its declared checksum, ``try_load_default_corpus`` returns ``None`` and
callers MUST treat that as "abstain on policy questions and record an
evidence gap" — never as a negative or positive policy conclusion.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any

DEFAULT_CORPUS_VERSION = "v1"
_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


class PolicyCorpusError(RuntimeError):
    """Base class for failures loading or validating the policy corpus."""


class PolicyCorpusIntegrityError(PolicyCorpusError):
    """The packaged corpus content does not match its declared checksum."""


class PolicyCorpusNotFoundError(PolicyCorpusError):
    """No packaged configuration/document file exists for the requested version."""


@dataclass(frozen=True, slots=True)
class PolicyClause:
    document_id: str
    clause_id: str
    text_vi: str


@dataclass(frozen=True, slots=True)
class PolicyDocument:
    document_id: str
    title_vi: str
    clauses: tuple[PolicyClause, ...]


@dataclass(frozen=True, slots=True)
class PolicyHit:
    """One clause-level retrieval hit with an exact quoted text span."""

    corpus_id: str
    corpus_version: str
    document_id: str
    document_title_vi: str
    clause_id: str
    quoted_text_vi: str
    score: int


@dataclass(frozen=True, slots=True)
class PolicyCorpus:
    """A loaded, checksum-verified, clearly-labelled synthetic policy corpus."""

    corpus_id: str
    version: str
    checksum_sha256: str
    is_synthetic: bool
    disclaimer_vi: str
    disclaimer_en: str
    documents: tuple[PolicyDocument, ...]

    def document(self, document_id: str) -> PolicyDocument | None:
        return next(
            (doc for doc in self.documents if doc.document_id == document_id), None
        )

    def clause(self, document_id: str, clause_id: str) -> PolicyClause | None:
        document = self.document(document_id)
        if document is None:
            return None
        return next(
            (c for c in document.clauses if c.clause_id == clause_id), None
        )

    def citation_is_grounded(
        self,
        *,
        corpus_id: str,
        corpus_version: str,
        document_id: str,
        clause_id: str,
        quoted_text_vi: str,
    ) -> bool:
        """A citation is grounded only if it names THIS loaded corpus/version
        and an exact clause whose text matches the quote exactly."""

        if corpus_id != self.corpus_id or corpus_version != self.version:
            return False
        clause = self.clause(document_id, clause_id)
        if clause is None:
            return False
        return clause.text_vi == quoted_text_vi

    def search(self, query_vi: str, *, top_k: int = 5) -> tuple[PolicyHit, ...]:
        """Deterministic lexical (token-overlap) search across every clause."""

        query_tokens = _tokenize(query_vi)
        scored: list[tuple[int, str, str, PolicyDocument, PolicyClause]] = []
        for document in self.documents:
            for clause in document.clauses:
                score = _overlap_score(query_tokens, _tokenize(clause.text_vi))
                if score > 0:
                    scored.append(
                        (score, document.document_id, clause.clause_id, document, clause)
                    )
        scored.sort(key=lambda row: (-row[0], row[1], row[2]))
        return tuple(
            PolicyHit(
                corpus_id=self.corpus_id,
                corpus_version=self.version,
                document_id=document.document_id,
                document_title_vi=document.title_vi,
                clause_id=clause.clause_id,
                quoted_text_vi=clause.text_vi,
                score=score,
            )
            for score, _, _, document, clause in scored[:top_k]
        )

    def retrieve_relevant(
        self, query_vi: str, *, top_k_per_document: int = 2
    ) -> tuple[PolicyHit, ...]:
        """Deterministic clause-level hits covering every policy document.

        For each document in the corpus, ranks its own clauses by lexical
        overlap with ``query_vi`` and keeps the top ``top_k_per_document``
        (ties broken by clause id order).  This keeps a small synthetic
        corpus useful for legal review even when the case-derived query does
        not literally overlap with every clause, while remaining fully
        deterministic and grounded (every hit is a real clause).
        """

        hits: list[PolicyHit] = []
        query_tokens = _tokenize(query_vi)
        for document in self.documents:
            scored = sorted(
                (
                    (_overlap_score(query_tokens, _tokenize(clause.text_vi)), clause)
                    for clause in document.clauses
                ),
                key=lambda row: (-row[0], row[1].clause_id),
            )
            for score, clause in scored[:top_k_per_document]:
                hits.append(
                    PolicyHit(
                        corpus_id=self.corpus_id,
                        corpus_version=self.version,
                        document_id=document.document_id,
                        document_title_vi=document.title_vi,
                        clause_id=clause.clause_id,
                        quoted_text_vi=clause.text_vi,
                        score=score,
                    )
                )
        return tuple(hits)


def _tokenize(text: str) -> frozenset[str]:
    return frozenset(match.group(0).casefold() for match in _TOKEN_PATTERN.finditer(text))


def _overlap_score(query_tokens: frozenset[str], clause_tokens: frozenset[str]) -> int:
    return len(query_tokens & clause_tokens)


def _read_package_text(filename: str) -> str:
    return (
        resources.files("creditops.policy_corpus")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )


def load_corpus(version: str = DEFAULT_CORPUS_VERSION) -> PolicyCorpus:
    """Load and checksum-verify the packaged synthetic corpus. Raises on failure.

    Fails closed by raising rather than returning a partially-trusted corpus;
    callers that must never hard-fail the whole task use
    ``try_load_default_corpus`` instead.
    """

    try:
        config_raw = _read_package_text(f"config_{version}.json")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise PolicyCorpusNotFoundError(
            f"no policy corpus configuration for version {version!r}"
        ) from exc
    config: dict[str, Any] = json.loads(config_raw)

    documents_filename = str(config["documents_file"])
    try:
        documents_bytes = (
            resources.files("creditops.policy_corpus")
            .joinpath(documents_filename)
            .read_bytes()
        )
    except FileNotFoundError as exc:
        raise PolicyCorpusNotFoundError(
            f"policy corpus document file missing: {documents_filename}"
        ) from exc

    actual_checksum = hashlib.sha256(documents_bytes).hexdigest()
    expected_checksum = str(config["checksum_sha256"])
    if actual_checksum != expected_checksum:
        raise PolicyCorpusIntegrityError(
            "policy corpus checksum mismatch: packaged content does not match "
            f"the configured checksum for version {version!r}"
        )

    documents_raw = json.loads(documents_bytes.decode("utf-8"))
    documents = tuple(
        PolicyDocument(
            document_id=str(doc["document_id"]),
            title_vi=str(doc["title_vi"]),
            clauses=tuple(
                PolicyClause(
                    document_id=str(doc["document_id"]),
                    clause_id=str(clause["clause_id"]),
                    text_vi=str(clause["text_vi"]),
                )
                for clause in doc["clauses"]
            ),
        )
        for doc in documents_raw["documents"]
    )

    return PolicyCorpus(
        corpus_id=str(config["corpus_id"]),
        version=str(config["version"]),
        checksum_sha256=actual_checksum,
        is_synthetic=bool(config.get("is_synthetic", True)),
        disclaimer_vi=str(config["disclaimer_vi"]),
        disclaimer_en=str(config["disclaimer_en"]),
        documents=documents,
    )


def try_load_default_corpus(
    version: str = DEFAULT_CORPUS_VERSION,
) -> PolicyCorpus | None:
    """Fail-closed load: any corpus problem yields ``None`` (abstain), never
    a partially-trusted corpus and never an exception the caller must guess
    how to interpret."""

    try:
        return load_corpus(version)
    except PolicyCorpusError:
        return None


__all__ = [
    "DEFAULT_CORPUS_VERSION",
    "PolicyClause",
    "PolicyCorpus",
    "PolicyCorpusError",
    "PolicyCorpusIntegrityError",
    "PolicyCorpusNotFoundError",
    "PolicyDocument",
    "PolicyHit",
    "load_corpus",
    "try_load_default_corpus",
]
