"""
Database seed data for initial setup and testing.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models.user import User
from models.branch import Branch
from models.product import Product
from models.inventory import Inventory
from core.database import SessionLocal
import logging

logger = logging.getLogger(__name__)


def seed_database(db: Session = None, force: bool = False):
    """
    Seed database with initial data.

    Args:
        db: Database session (creates new if None)
        force: Force seeding even if data exists
    """
    if db is None:
        db = SessionLocal()

    try:
        # Check if already seeded
        if not force:
            user_count = db.query(User).count()
            if user_count > 0:
                logger.info("Database already seeded, skipping...")
                return

        # Create default admin user
        admin_user = User(
            name="Administrador",
            email="admin@tecnogas.com"
        )
        admin_user.set_password("admin123")
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        logger.info(f"Created admin user: {admin_user.email}")

        # Create sample users
        sample_users = [
            User(name="Juan Perez", email="juan.perez@tecnogas.com"),
            User(name="Maria Garcia", email="maria.garcia@tecnogas.com"),
            User(name="Carlos Lopez", email="carlos.lopez@tecnogas.com"),
        ]
        for user in sample_users:
            user.set_password("password123")
            db.add(user)

        db.commit()
        logger.info(f"Created {len(sample_users)} sample users")

        # Create branches
        branches = [
            Branch(name="Sucursal Central", address="Av. Principal #123, Ciudad"),
            Branch(name="Sucursal Norte", address="Calle Norte #456, Zona Norte"),
            Branch(name="Sucursal Sur", address="Av. Sur #789, Zona Sur"),
            Branch(name="Sucursal Este", address="Blvd. Este #321, Zona Este"),
        ]
        for branch in branches:
            db.add(branch)

        db.commit()
        for branch in branches:
            db.refresh(branch)
        logger.info(f"Created {len(branches)} branches")

        # Create products
        products = [
            Product(sku="GAS-001", name="Gas Natural - Cilindro 25kg", description="Cilindro de gas natural 25kg", unit_of_measure="cilindro", unit_price=350.00),
            Product(sku="GAS-002", name="Gas Natural - Cilindro 45kg", description="Cilindro de gas natural 45kg", unit_of_measure="cilindro", unit_price=580.00),
            Product(sku="GAS-003", name="Gas Natural - Cilindro 90kg", description="Cilindro de gas natural 90kg", unit_of_measure="cilindro", unit_price=920.00),
            Product(sku="GAS-004", name="Gas LP - Tanque 100L", description="Tanque de gas LP 100 litros", unit_of_measure="tanque", unit_price=1250.00),
            Product(sku="GAS-005", name="Gas LP - Tanque 200L", description="Tanque de gas LP 200 litros", unit_of_measure="tanque", unit_price=2100.00),
            Product(sku="REG-001", name="Regulador de Presion Estndar", description="Regulador de presion para uso domstico", unit_of_measure="unidad", unit_price=85.50),
            Product(sku="REG-002", name="Regulador de Presion Industrial", description="Regulador de presion industrial", unit_of_measure="unidad", unit_price=245.00),
            Product(sku="MAN-001", name="Manometro 0-30 PSI", description="Manometro Industrial 0-30 PSI", unit_of_measure="unidad", unit_price=125.00),
            Product(sku="VAL-001", name="Valvula de Seguridad", description="Valvula de seguridad para cilindros", unit_of_measure="unidad", unit_price=95.00),
            Product(sku="MNG-001", name="Manguera Flexible 1m", description="Manguera flexible de 1 metro", unit_of_measure="unidad", unit_price=45.00),
        ]
        for product in products:
            db.add(product)

        db.commit()
        for product in products:
            db.refresh(product)
        logger.info(f"Created {len(products)} products")

        # Create inventory for each product in each branch
        inventory_data = [
            # Central branch
            {"product": 0, "branch": 0, "physical": 150, "digital": 150, "min_stock": 20},
            {"product": 1, "branch": 0, "physical": 100, "digital": 100, "min_stock": 15},
            {"product": 2, "branch": 0, "physical": 80, "digital": 80, "min_stock": 10},
            {"product": 3, "branch": 0, "physical": 40, "digital": 40, "min_stock": 5},
            {"product": 4, "branch": 0, "physical": 25, "digital": 25, "min_stock": 3},
            # Norte branch
            {"product": 0, "branch": 1, "physical": 85, "digital": 90, "min_stock": 20},  # Discrepancy
            {"product": 1, "branch": 1, "physical": 60, "digital": 60, "min_stock": 15},
            {"product": 5, "branch": 1, "physical": 150, "digital": 150, "min_stock": 25},
            {"product": 6, "branch": 1, "physical": 45, "digital": 45, "min_stock": 10},
            # Sur branch
            {"product": 2, "branch": 2, "physical": 50, "digital": 50, "min_stock": 10},
            {"product": 3, "branch": 2, "physical": 20, "digital": 20, "min_stock": 5},
            {"product": 7, "branch": 2, "physical": 30, "digital": 30, "min_stock": 8},
            {"product": 8, "branch": 2, "physical": 60, "digital": 65, "min_stock": 15},  # Discrepancy
            # Este branch
            {"product": 0, "branch": 3, "physical": 100, "digital": 100, "min_stock": 20},
            {"product": 4, "branch": 3, "physical": 15, "digital": 15, "min_stock": 5},  # Low stock
            {"product": 6, "branch": 3, "physical": 30, "digital": 30, "min_stock": 10},
            {"product": 9, "branch": 3, "physical": 200, "digital": 200, "min_stock": 30},
        ]

        for inv_data in inventory_data:
            inventory = Inventory(
                product_id=products[inv_data["product"]].id,
                branch_id=branches[inv_data["branch"]].id,
                physical_stock=inv_data["physical"],
                digital_stock=inv_data["digital"],
                min_stock=inv_data["min_stock"]
            )
            db.add(inventory)

        db.commit()
        logger.info(f"Created {len(inventory_data)} inventory records")

        logger.info("Database seeding completed successfully!")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        if db:
            db.close()


def clear_database(db: Session = None):
    """
    Clear all data from database.

    Warning: This will delete all data!
    """
    if db is None:
        db = SessionLocal()

    try:
        # Delete in reverse order of dependencies
        from models.movement import Movement
        from models.inventory import Inventory
        from modules.alerts.service import Alert
        from modules.history.service import HistoryEntry

        db.query(HistoryEntry).delete()
        db.query(Alert).delete()
        db.query(Movement).delete()
        db.query(Inventory).delete()
        db.query(Product).delete()
        db.query(Branch).delete()
        db.query(User).delete()

        db.commit()
        logger.info("Database cleared successfully")

    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing database: {e}")
        raise
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    # Run seeding directly
    import sys

    print("Seeding database...")
    if "--clear" in sys.argv:
        clear_database()
        print("Database cleared.")
    seed_database(force="--force" in sys.argv)
    print("Seeding complete!")
