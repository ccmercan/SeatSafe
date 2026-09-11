from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatsafe.api.correlation import CORRELATION_HEADER
from seatsafe.api.problem_details import PROBLEM_MEDIA_TYPE, ProblemException
from seatsafe.config import Settings
from seatsafe.main import create_app


def test_health_reports_process_status_and_correlation_id() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "seatsafe-api"}
    UUID(response.headers[CORRELATION_HEADER])


def test_safe_client_correlation_id_is_preserved() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/health", headers={CORRELATION_HEADER: "test-request-123"})

    assert response.headers[CORRELATION_HEADER] == "test-request-123"


def test_domain_problem_uses_standard_contract() -> None:
    app = create_app(Settings(environment="test"))
    _add_problem_route(app)
    client = TestClient(app)

    response = client.get("/example-problem")

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert response.json() == {
        "type": "urn:seatsafe:problem:seat-unavailable",
        "title": "Seat unavailable",
        "status": 409,
        "detail": "The selected seat is no longer available.",
        "code": "seat_unavailable",
        "correlation_id": response.headers[CORRELATION_HEADER],
    }


def test_validation_problem_does_not_echo_invalid_input() -> None:
    app = create_app(Settings(environment="test"))
    _add_validation_route(app)
    client = TestClient(app)

    response = client.get("/example-validation/not-an-integer")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body = response.json()
    assert body["code"] == "validation_failed"
    assert body["correlation_id"] == response.headers[CORRELATION_HEADER]
    assert body["errors"][0]["location"] == ["path", "item_id"]
    assert "input" not in body["errors"][0]


def test_missing_route_uses_problem_contract() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["code"] == "resource_not_found"
    assert response.json()["correlation_id"] == response.headers[CORRELATION_HEADER]


def _add_problem_route(app: FastAPI) -> None:
    @app.get("/example-problem")
    async def example_problem() -> None:
        raise ProblemException(
            status=409,
            code="seat_unavailable",
            title="Seat unavailable",
            detail="The selected seat is no longer available.",
        )


def _add_validation_route(app: FastAPI) -> None:
    @app.get("/example-validation/{item_id}")
    async def example_validation(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}
