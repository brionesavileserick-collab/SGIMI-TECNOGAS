"""
Database bootstrap utilities.

Production installs do not load sample users, branches, products, or inventory.
The application creates the initial user through the first-run dialog in main.py.
"""

import os
import logging
from sqlalchemy.orm import Session
from models.user import User
from models.branch import Branch
from models.product import Product
from models.inventory import Inventory
from core.database import SessionLocal

logger = logging.getLogger(__name__)


def seed_database(db: Session = None, force: bool = False):
    """
    Bootstrap a production database without sample inventory data.

    If SGIMI_INITIAL_USER_EMAIL and SGIMI_INITIAL_USER_PASSWORD are set, this
    creates one initial user. Otherwise no records are inserted.
    """
    owns_session = db is None
    if db is None:
        db = SessionLocal()

    try:
        if db.query(User).count() > 0 and not force:
            logger.info("Database already has users, skipping bootstrap.")
            return

        email = os.getenv("SGIMI_INITIAL_USER_EMAIL")
        password = os.getenv("SGIMI_INITIAL_USER_PASSWORD")
        name = os.getenv("SGIMI_INITIAL_USER_NAME", "Usuario Inicial")

        if not email or not password:
            logger.info("No initial user environment variables provided; bootstrap inserted no data.")
            return

        existing_user = db.query(User).filter(User.email == email.strip().lower()).first()
        if existing_user and not force:
            logger.info("Initial user already exists, skipping bootstrap.")
            return

        user = User(name=name.strip(), email=email.strip().lower())
        user.set_password(password)
        db.add(user)
        db.commit()
        logger.info(f"Created initial user: {user.email}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error bootstrapping database: {e}")
        raise
    finally:
        if owns_session:
            db.close()


def clear_database(db: Session = None):
    """
    Clear all data from database.

    Warning: This will delete all data.
    """
    owns_session = db is None
    if db is None:
        db = SessionLocal()

    try:
        from models.movement import Movement
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
        if owns_session:
            db.close()


if __name__ == "__main__":
    import sys

    if "--clear" in sys.argv:
        clear_database()
        print("Database cleared.")

    seed_database(force="--force" in sys.argv)
    print("Bootstrap complete.")
