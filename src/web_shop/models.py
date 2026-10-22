"""Database models."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Product(Base):
    """A product available in the shop."""

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[ProductDetail | None] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    reviews: Mapped[list[ProductReview]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProductDetail(Base):
    """Optional one-to-one details for a product."""

    __tablename__ = "product_detail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    material: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[str] = mapped_column(String(100), nullable=False)
    product: Mapped[Product] = relationship(back_populates="detail")


class ProductReview(Base):
    """A review belonging to one product; a product can have many reviews."""

    __tablename__ = "product_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    product: Mapped[Product] = relationship(back_populates="reviews")
