import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from web_shop.app import create_app


@pytest.fixture
def postgres_client() -> Generator[TestClient]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("Set DATABASE_URL to run PostgreSQL integration tests")

    schema = f"test_web_shop_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    test_engine: Engine = admin_engine.execution_options(
        schema_translate_map={None: schema}
    )
    try:
        with TestClient(create_app(test_engine)) as client:
            yield client
    finally:
        admin_engine.dispose()
        cleanup_engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with cleanup_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            cleanup_engine.dispose()


@pytest.mark.integration
def test_postgres_api_flow_uses_isolated_schema(
    postgres_client: TestClient,
) -> None:
    payload = {
        "name": f"PostgreSQL Integration {uuid4().hex[:8]}",
        "description": "Integration test product",
        "price": "17.25",
        "stock": 6,
        "detail": {"material": "Steel", "dimensions": "250 ml"},
    }
    created = postgres_client.post("/products", json=payload)

    assert created.status_code == 201
    assert created.json()["version"] == 1
    assert created.json()["detail"]["material"] == "Steel"

    product_id = created.json()["id"]
    fetched = postgres_client.get(f"/products/{product_id}")
    assert fetched.status_code == 200

    etag = fetched.headers["etag"]
    unchanged = postgres_client.get(
        f"/products/{product_id}",
        headers={"If-None-Match": etag},
    )
    assert unchanged.status_code == 304

    review = postgres_client.post(
        f"/products/{product_id}/reviews",
        json={"rating": 5, "comment": "PostgreSQL persisted the review"},
    )
    assert review.status_code == 201
    reviews = postgres_client.get(f"/products/{product_id}/reviews")
    assert reviews.status_code == 200
    assert len(reviews.json()) == 1

    payload["stock"] = 4
    updated = postgres_client.put(
        f"/products/{product_id}",
        json=payload,
        headers={"If-Match": etag},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["stock"] == 4

    stale_update = postgres_client.put(
        f"/products/{product_id}",
        json=payload,
        headers={"If-Match": etag},
    )
    assert stale_update.status_code == 412
