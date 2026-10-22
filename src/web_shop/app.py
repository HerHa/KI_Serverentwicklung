"""FastAPI application for the minimal web shop."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, selectinload
from starlette import status

from web_shop.db import create_engine_from_env, create_session_factory
from web_shop.models import Base, Product, ProductDetail, ProductReview
from web_shop.schemas import (
    ProductCreate,
    ProductResponse,
    ProductReviewCreate,
    ProductReviewResponse,
    ProductUpdate,
)


def get_session(request: Request) -> Iterator[Session]:
    """Yield one database session per request."""
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session


def _etag_for(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f'"{hashlib.sha256(encoded).hexdigest()}"'


def _matches_if_none_match(header: str | None, etag: str) -> bool:
    if header is None:
        return False
    return "*" in (tag.strip() for tag in header.split(",")) or etag in (
        tag.strip() for tag in header.split(",")
    )


def _product_payload(product: Product) -> ProductResponse:
    return ProductResponse.model_validate(product)


def create_app(engine: Engine | None = None) -> FastAPI:
    """Create an app, optionally using an injected engine for tests."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        active_engine = engine or create_engine_from_env()
        application.state.session_factory = create_session_factory(active_engine)
        Base.metadata.create_all(active_engine)
        try:
            yield
        finally:
            active_engine.dispose()

    application = FastAPI(title="Web Shop API", lifespan=lifespan)

    @application.get("/products", response_model=list[ProductResponse])
    def list_products(
        response: Response,
        session: Annotated[Session, Depends(get_session)],
        name: Annotated[str | None, Query(min_length=1)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        if_none_match: Annotated[str | None, Header()] = None,
    ) -> list[ProductResponse] | Response:
        statement = (
            select(Product)
            .options(selectinload(Product.detail))
            .order_by(Product.id)
            .limit(limit)
            .offset(offset)
        )
        if name is not None:
            statement = statement.where(Product.name.ilike(f"%{name}%"))
        products = session.scalars(statement).all()
        payload = [_product_payload(product) for product in products]
        etag = _etag_for([item.model_dump(mode="json") for item in payload])
        response.headers["ETag"] = etag
        if _matches_if_none_match(if_none_match, etag):
            return Response(
                status_code=status.HTTP_304_NOT_MODIFIED,
                headers={"ETag": etag},
            )
        return payload

    @application.get("/products/{product_id}", response_model=ProductResponse)
    def get_product(
        product_id: int,
        response: Response,
        session: Annotated[Session, Depends(get_session)],
        if_none_match: Annotated[str | None, Header()] = None,
    ) -> ProductResponse | Response:
        product = session.scalar(
            select(Product)
            .options(selectinload(Product.detail))
            .where(Product.id == product_id)
        )
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        payload = _product_payload(product)
        etag = _etag_for(payload.model_dump(mode="json"))
        response.headers["ETag"] = etag
        if _matches_if_none_match(if_none_match, etag):
            return Response(
                status_code=status.HTTP_304_NOT_MODIFIED,
                headers={"ETag": etag},
            )
        return payload

    @application.post(
        "/products",
        response_model=ProductResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_product(
        product_input: ProductCreate,
        session: Annotated[Session, Depends(get_session)],
    ) -> ProductResponse:
        detail = (
            ProductDetail(**product_input.detail.model_dump())
            if product_input.detail is not None
            else None
        )
        product = Product(
            name=product_input.name,
            description=product_input.description,
            price=product_input.price,
            stock=product_input.stock,
            detail=detail,
        )
        session.add(product)
        session.commit()
        session.refresh(product)
        return _product_payload(product)

    @application.put("/products/{product_id}", response_model=ProductResponse)
    def update_product(
        product_id: int,
        product_input: ProductUpdate,
        session: Annotated[Session, Depends(get_session)],
        if_match: Annotated[str | None, Header()] = None,
    ) -> ProductResponse:
        if if_match is None:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail="If-Match header with the current ETag is required",
            )

        product = session.scalar(
            select(Product)
            .options(selectinload(Product.detail))
            .where(Product.id == product_id)
            .with_for_update()
        )
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        current_etag = _etag_for(_product_payload(product).model_dump(mode="json"))
        if if_match.strip() != current_etag:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail="Product has changed; fetch it again before updating",
            )

        updated_id = session.execute(
            update(Product)
            .where(
                Product.id == product_id,
                Product.name == product.name,
                Product.description == product.description,
                Product.price == product.price,
                Product.stock == product.stock,
            )
            .values(
                name=product_input.name,
                description=product_input.description,
                price=product_input.price,
                stock=product_input.stock,
            )
            .returning(Product.id)
        ).scalar_one_or_none()
        if updated_id is None:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail="Product changed during update; fetch it again before retrying",
            )

        if product_input.detail is None:
            product.detail = None
        elif product.detail is None:
            product.detail = ProductDetail(**product_input.detail.model_dump())
        else:
            product.detail.material = product_input.detail.material
            product.detail.dimensions = product_input.detail.dimensions

        session.commit()
        session.expire(product)
        return _product_payload(product)

    @application.get(
        "/products/{product_id}/reviews",
        response_model=list[ProductReviewResponse],
    )
    def list_reviews(
        product_id: int,
        session: Annotated[Session, Depends(get_session)],
    ) -> list[ProductReviewResponse]:
        if session.get(Product, product_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        reviews = session.scalars(
            select(ProductReview)
            .where(ProductReview.product_id == product_id)
            .order_by(ProductReview.id)
        ).all()
        return [ProductReviewResponse.model_validate(review) for review in reviews]

    @application.post(
        "/products/{product_id}/reviews",
        response_model=ProductReviewResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_review(
        product_id: int,
        review_input: ProductReviewCreate,
        session: Annotated[Session, Depends(get_session)],
    ) -> ProductReviewResponse:
        if session.get(Product, product_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        review = ProductReview(
            product_id=product_id,
            rating=review_input.rating,
            comment=review_input.comment,
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        return ProductReviewResponse.model_validate(review)

    return application


app = create_app()
