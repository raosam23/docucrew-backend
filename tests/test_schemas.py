"""Request and response schema validation."""

import pytest
from pydantic import ValidationError

from app.models.document import DocumentStatus, FileType
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.schemas.collection import CollectionCreate, CollectionResponse
from app.schemas.document import DocumentResponse
from app.schemas.query import Citations, QueryAnswer, QueryHistoryResponse, QueryRequest, QueryResponse
from tests.factories import QUERY_ID, make_collection, make_document, make_history, make_user


def test_register_and_login_requests() -> None:
    registered = RegisterRequest(email="ada@example.com", password="secret")
    assert registered.name is None

    named = RegisterRequest(email="ada@example.com", password="secret", name="Ada")
    assert named.name == "Ada"
    assert LoginRequest(email="ada@example.com", password="secret").email == "ada@example.com"

    with pytest.raises(ValidationError):
        RegisterRequest(email="ada@example.com")


def test_user_and_collection_responses_read_from_models() -> None:
    user = UserResponse.model_validate(make_user())
    assert user.email == "ada@example.com"
    assert user.name == "Ada Lovelace"

    created = CollectionCreate(name="Notes")
    assert created.description is None

    collection = CollectionResponse.model_validate(make_collection())
    assert collection.name == "Policies"
    assert collection.chroma_collection_id.startswith("col_")


def test_document_response_uses_status_enums() -> None:
    document = DocumentResponse.model_validate(make_document())

    assert document.file_type is FileType.PDF
    assert document.status is DocumentStatus.READY
    assert document.chunk_count is None
    assert document.error_message is None
    assert FileType.MD == "md"
    assert DocumentStatus.FAILED == "failed"


def test_query_schemas_coerce_citations() -> None:
    request = QueryRequest(question="Where is the office?")
    assert request.question == "Where is the office?"

    answer = QueryAnswer(answer="London.")
    assert answer.citations == []

    citation = Citations(filename="policy.pdf", chunk_index=2)
    assert citation.relevance_score is None

    response = QueryResponse(
        answer="London.",
        citations=[{"filename": "policy.pdf", "chunk_index": 2, "relevance_score": 0.4}],
        query_id=QUERY_ID,
    )
    assert response.citations is not None
    assert response.citations[0].filename == "policy.pdf"

    history = QueryHistoryResponse.model_validate(make_history())
    assert history.question.startswith("What is")
    assert history.citations is not None
    assert history.citations[0].chunk_index == 1

    with pytest.raises(ValidationError):
        QueryRequest()
