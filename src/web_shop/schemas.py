"""Pydantic request and response models for the shop API."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductDetailInput(BaseModel):
    """Optional one-to-one product details."""

    model_config = ConfigDict(extra="forbid")

    material: str = Field(min_length=1, max_length=100)
    dimensions: str = Field(min_length=1, max_length=100)


class ProductCreate(BaseModel):
    """Validated product creation payload."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)
    detail: ProductDetailInput | None = None


class ProductUpdate(ProductCreate):
    """Full product replacement payload used by PUT."""


class ProductDetailResponse(BaseModel):
    """Product detail response."""

    model_config = ConfigDict(from_attributes=True)

    material: str
    dimensions: str


class ProductResponse(BaseModel):
    """Product response returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    price: Decimal
    stock: int
    detail: ProductDetailResponse | None


class ProductReviewCreate(BaseModel):
    """Validated product review payload."""

    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=1, max_length=1000)


class ProductReviewResponse(BaseModel):
    """Review response returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    rating: int
    comment: str
