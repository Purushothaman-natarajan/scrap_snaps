"""Database models and initialization for the research agent."""

import datetime
import logging

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""


class Product(Base):
    """Represents a researched product."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    canonical_name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Source(Base):
    """Represents a web source used for evidence."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, index=True)
    source_type = Column(String)
    reliability_score = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Claim(Base):
    """Represents an extracted specification claim from a source."""

    __tablename__ = "claims"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    source_id = Column(Integer, ForeignKey("sources.id"))
    claim_type = Column(String)
    value = Column(String)
    confidence = Column(Float)
    extracted_at = Column(DateTime, default=datetime.datetime.utcnow)


class Image(Base):
    """Represents a downloaded and classified product image."""

    __tablename__ = "images"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    source_id = Column(Integer, ForeignKey("sources.id"))
    url = Column(String)
    phash = Column(String, index=True)
    view_type = Column(String)
    local_path = Column(String)


class Video(Base):
    """Represents a product video source."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    url = Column(String, unique=True)
    metadata_json = Column(JSON)


def init_db(database_url: str) -> Session:
    """Initialize the database and return a session.

    Creates all tables if they don't exist.
    """
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    logger.info("Database initialized at %s", database_url)
    return session_factory()
