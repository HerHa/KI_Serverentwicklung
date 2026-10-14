"""Create the database schema and insert development sample products."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from web_shop.db import create_engine_from_env
from web_shop.models import Base, Product

SAMPLE_PRODUCTS = (
    ("Kaffeetasse", "Keramiktasse, 300 ml", Decimal("8.90"), 25),
    ("Notizbuch", "A5-Notizbuch mit punktierten Seiten", Decimal("5.50"), 40),
    ("Stofftasche", "Wiederverwendbare Baumwolltasche", Decimal("12.00"), 15),
)


def create_schema_and_seed(engine: Engine) -> bool:
    """Create tables and insert sample products if the product table is empty."""
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        has_products = session.scalar(select(Product.id).limit(1)) is not None
        if has_products:
            return False
        session.add_all(
            Product(name=name, description=description, price=price, stock=stock)
            for name, description, price, stock in SAMPLE_PRODUCTS
        )
        session.commit()
    return True


def main() -> None:
    """Initialize the configured database and seed sample products."""
    engine = create_engine_from_env()
    try:
        inserted = create_schema_and_seed(engine)
        if inserted:
            print(f"Database initialized with {len(SAMPLE_PRODUCTS)} sample products.")
        else:
            print("Database already contains products; sample data was not added.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
