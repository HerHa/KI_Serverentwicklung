from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from web_shop.app import create_app


@pytest.fixture
def client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with TestClient(create_app(engine)) as test_client:
        yield test_client


def product_payload() -> dict[str, object]:
    return {
        "name": "Thermobecher",
        "description": "Becher aus Edelstahl",
        "price": "19.90",
        "stock": 12,
        "detail": {"material": "Edelstahl", "dimensions": "500 ml"},
    }


def test_product_creation_validates_and_returns_one_to_one_detail(
    client: TestClient,
) -> None:
    response = client.post("/products", json=product_payload())

    assert response.status_code == 201
    assert response.json()["detail"] == {
        "material": "Edelstahl",
        "dimensions": "500 ml",
    }
    assert client.get("/products?name=Thermo").json()[0]["name"] == "Thermobecher"


def test_conditional_get_and_put_rejects_lost_update(client: TestClient) -> None:
    created = client.post("/products", json=product_payload())
    product_id = created.json()["id"]

    fetched = client.get(f"/products/{product_id}")
    original_etag = fetched.headers["etag"]
    unchanged = client.get(
        f"/products/{product_id}",
        headers={"If-None-Match": original_etag},
    )
    assert unchanged.status_code == 304

    updated_payload = product_payload()
    updated_payload["stock"] = 8
    updated_payload["detail"] = {
        "material": "Recycelter Edelstahl",
        "dimensions": "500 ml",
    }
    updated = client.put(
        f"/products/{product_id}",
        json=updated_payload,
        headers={"If-Match": original_etag},
    )
    assert updated.status_code == 200
    assert updated.json()["stock"] == 8
    assert updated.json()["detail"]["material"] == "Recycelter Edelstahl"

    stale_update = client.put(
        f"/products/{product_id}",
        json=product_payload(),
        headers={"If-Match": original_etag},
    )
    assert stale_update.status_code == 412


def test_reviews_form_one_to_many_relation_and_validate(client: TestClient) -> None:
    product_id = client.post("/products", json=product_payload()).json()["id"]

    first = client.post(
        f"/products/{product_id}/reviews",
        json={"rating": 5, "comment": "Sehr gut"},
    )
    second = client.post(
        f"/products/{product_id}/reviews",
        json={"rating": 4, "comment": "Gut"},
    )
    invalid = client.post(
        f"/products/{product_id}/reviews",
        json={"rating": 6, "comment": "Ungültige Bewertung"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert invalid.status_code == 422
    assert len(client.get(f"/products/{product_id}/reviews").json()) == 2
