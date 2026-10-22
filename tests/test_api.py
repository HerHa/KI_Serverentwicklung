from collections.abc import Generator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.pool import StaticPool

from web_shop.app import create_app
from web_shop.models import Base, Product


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
    assert response.json()["version"] == 1
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
    assert updated.json()["version"] == 2
    assert updated.headers["etag"] != original_etag
    assert updated.json()["detail"]["material"] == "Recycelter Edelstahl"

    stale_update = client.put(
        f"/products/{product_id}",
        json=product_payload(),
        headers={"If-Match": original_etag},
    )
    assert stale_update.status_code == 412


def test_put_requires_if_match_header(client: TestClient) -> None:
    product_id = client.post("/products", json=product_payload()).json()["id"]

    response = client.put(
        f"/products/{product_id}",
        json=product_payload(),
    )

    assert response.status_code == 428


def test_stale_database_session_cannot_overwrite_newer_product(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'versioning.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as setup_session:
        product = Product(
            name="Thermobecher",
            description="Becher aus Edelstahl",
            price=Decimal("19.90"),
            stock=12,
        )
        setup_session.add(product)
        setup_session.commit()
        product_id = product.id

    first_session = Session(engine)
    stale_session = Session(engine)
    try:
        first_product = first_session.get(Product, product_id)
        stale_product = stale_session.get(Product, product_id)
        assert first_product is not None
        assert stale_product is not None

        first_product.stock = 10
        first_product.version += 1
        first_session.commit()

        stale_product.stock = 5
        stale_product.version += 1
        with pytest.raises(StaleDataError):
            stale_session.commit()
        stale_session.rollback()
    finally:
        first_session.close()
        stale_session.close()
        engine.dispose()


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
