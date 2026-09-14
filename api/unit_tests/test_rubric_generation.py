from types import SimpleNamespace
from unittest.mock import MagicMock
import json

import httpx
import openai
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import rubric as routes
from utilities.llm.rubric import rubric_generator as generation
from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections


BUILD_ID = "abcdefghij"
PARAMS = {
    "id": BUILD_ID,
    "total_points": 100,
    "levels": ["Proficient", "Developing"],
    "categories": ["Configuration"],
    "headers": ["Proficient", "Developing"],
}
CONTENT = {
    "categories": PARAMS["categories"],
    "headers": ["Proficient (60-100 points)", "Developing (0-59 points)"],
    "criteria": [
        {"category": "Configuration", "index": "0", "description": "Complete configuration."},
        {"category": "Configuration", "index": "1", "description": "Incomplete configuration."},
    ],
}


def completion(arguments):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(function_call=SimpleNamespace(arguments=arguments))
    )])


@pytest.fixture
def generator():
    instance = generation.RubricGenerator.__new__(generation.RubricGenerator)
    instance.db = MagicMock()
    instance.logger = MagicMock()
    instance.client = MagicMock()
    instance.client.chat.completions.create.return_value = completion(json.dumps(CONTENT))
    return instance


@pytest.fixture
def client(monkeypatch, generator):
    monkeypatch.setattr(routes, "RubricGenerator", MagicMock(return_value=generator))
    app = FastAPI()
    app.include_router(routes.rubric_router)
    app.dependency_overrides[routes.get_cloud_env] = lambda: {"project": "test-project"}
    app.dependency_overrides[routes.teacher_required] = lambda: SimpleNamespace(uid="test-instructor")
    with TestClient(app) as test_client:
        yield test_client


def test_exhausted_credits_returns_actionable_error_without_writing(
    client, generator, monkeypatch
):
    body = {
        "type": "insufficient_quota",
        "code": "credit_balance_exhausted",
        "message": "You have no credits remaining.",
    }
    error = openai.RateLimitError(
        "OpenAI quota exhausted",
        response=httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")),
        body=body,
    )
    generator.client.chat.completions.create.side_effect = error
    # Also exercise the old module-global client when reproducing this on main.
    monkeypatch.setattr(generation.openai, "chat", generator.client.chat)

    response = client.post(f"/rubrics/generate/{BUILD_ID}/", json=PARAMS)

    assert response.status_code == 503
    assert "credits" in response.json()["detail"].lower()
    generator.db.update.assert_not_called()


@pytest.mark.parametrize("error_class,status,body,expected_status,message", [
    (openai.RateLimitError, 429, {"type": "insufficient_quota"}, 503, "billing"),
    (openai.RateLimitError, 429, {"code": "insufficient_quota"}, 503, "billing"),
    (openai.RateLimitError, 429, {"code": "project_spend_limit_exceeded"}, 503, "billing"),
    (openai.RateLimitError, 429, {"code": "rate_limit_exceeded"}, 429, "wait"),
    (openai.AuthenticationError, 401, {"code": "invalid_api_key"}, 503, "API key"),
    (openai.PermissionDeniedError, 403, {}, 503, "permissions"),
    (openai.InternalServerError, 500, {}, 503, "try again"),
])
def test_provider_errors_are_translated_without_saving(
    client, generator, error_class, status, body, expected_status, message
):
    generator.client.chat.completions.create.side_effect = error_class(
        "Provider error details must stay out of the client response",
        response=httpx.Response(status, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")),
        body=body,
    )

    response = client.post(f"/rubrics/generate/{BUILD_ID}/", json=PARAMS)

    assert response.status_code == expected_status
    assert message in response.json()["detail"]
    assert "Provider error details" not in response.text
    generator.db.update.assert_not_called()


@pytest.mark.parametrize("error_class", [openai.APIConnectionError, openai.APITimeoutError])
def test_connection_failures_are_recoverable(client, generator, error_class):
    generator.client.chat.completions.create.side_effect = error_class(
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    )

    response = client.post(f"/rubrics/generate/{BUILD_ID}/", json=PARAMS)

    assert response.status_code == 503
    assert "try again" in response.json()["detail"]
    generator.db.update.assert_not_called()


def test_success_saves_complete_rubric_under_url_id(client, generator):
    # The route can derive the identifier from the URL when the body omits it.
    params = {key: value for key, value in PARAMS.items() if key != "id"}

    response = client.post(f"/rubrics/generate/{BUILD_ID}/", json=params)

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["id"] == BUILD_ID
    assert result["content"]["build_id"] == BUILD_ID
    assert result["content"]["headers"] == CONTENT["headers"]
    assert result["content"]["criteria"][0]["index"] == 0
    generator.db.update.assert_called_once_with(
        collection_name=DbCollections.RUBRIC,
        doc_id=BUILD_ID,
        data=result["content"],
    )
    # The provider schema must not require a field absent from its properties.
    schema = generator.client.chat.completions.create.call_args.kwargs["functions"][0]["parameters"]
    assert set(schema["required"]).issubset(schema["properties"])


@pytest.mark.parametrize("changes", [
    {"id": "another-id"}, {"levels": []}, {"levels": "Proficient"},
    {"categories": [""]}, {"total_points": 0}, {"total_points": True},
])
def test_invalid_request_does_not_call_provider(client, generator, changes):
    response = client.post(f"/rubrics/generate/{BUILD_ID}/", json={**PARAMS, **changes})

    assert response.status_code == 400
    generator.client.chat.completions.create.assert_not_called()
    generator.db.update.assert_not_called()


@pytest.mark.parametrize("provider_response", [
    SimpleNamespace(choices=[]),
    SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(function_call=None))]),
    completion("not JSON"),
    completion("null"),
    completion("{}"),
    completion(json.dumps({**CONTENT, "criteria": []})),
    completion(json.dumps({**CONTENT, "criteria": [CONTENT["criteria"][0]] * 2})),
])
def test_invalid_generated_content_does_not_overwrite_a_rubric(
    client, generator, provider_response
):
    generator.client.chat.completions.create.return_value = provider_response

    response = client.post(f"/rubrics/generate/{BUILD_ID}/", json=PARAMS)

    assert response.status_code == 503
    assert "incomplete or invalid" in response.json()["detail"]
    generator.db.update.assert_not_called()


def test_missing_rubric_is_expected_before_generation(client, generator, monkeypatch):
    rubric_handler = MagicMock()
    rubric_handler.get.return_value = None
    monkeypatch.setattr(routes, "Rubric", MagicMock(return_value=rubric_handler))

    response = client.get(f"/rubrics/{BUILD_ID}/")

    assert response.status_code == 200
    assert response.json()["data"] is None
    generator.client.chat.completions.create.assert_not_called()


def test_client_uses_deployment_credentials_without_automatic_retries(monkeypatch):
    env = SimpleNamespace(
        project="test-project", openai_api_key="test-only-key", get_env=lambda: {"project": "test-project"}
    )
    monkeypatch.setattr(generation, "CloudEnv", MagicMock(return_value=env))
    factory = MagicMock()
    monkeypatch.setattr(generation.DocumentDatabaseFactory, "create_db_object", factory)
    client_factory = MagicMock()
    monkeypatch.setattr(generation.openai, "OpenAI", client_factory)

    generation.RubricGenerator(env_dict=env.get_env())

    client_factory.assert_called_once_with(api_key="test-only-key", max_retries=0, timeout=60.0)
    factory.assert_called_once_with(
        db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME,
        log_name="api", project_id="test-project",
    )


def test_missing_api_key_is_an_actionable_configuration_error(monkeypatch):
    env = SimpleNamespace(project="test-project", openai_api_key=None, get_env=lambda: {})
    monkeypatch.setattr(generation, "CloudEnv", MagicMock(return_value=env))
    monkeypatch.setattr(generation.DocumentDatabaseFactory, "create_db_object", MagicMock())
    client_factory = MagicMock()
    monkeypatch.setattr(generation.openai, "OpenAI", client_factory)

    with pytest.raises(generation.ServiceUnavailable, match="configure the OpenAI API key"):
        generation.RubricGenerator(env_dict={})

    client_factory.assert_not_called()
