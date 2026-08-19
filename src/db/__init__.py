"""Database models and initialization."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Product(Base):
    """A researched product."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    canonical_name = Column(String(500), default="")
    query = Column(String(500), default="")
    confidence = Column(Float, default=0.0)
    status = Column(String(50), default="started")
    row_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sources = relationship("Source", back_populates="product", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="product", cascade="all, delete-orphan")
    images = relationship("Image", back_populates="product", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="product", cascade="all, delete-orphan")


class Source(Base):
    """A web source URL visited during research."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(String(500), default="")
    source_type = Column(String(50), default="web")  # web, image_search, video_search
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="sources")


class Claim(Base):
    """A technical specification claim extracted from a source."""

    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    claim_type = Column(String(200), nullable=False)
    value = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    source_url = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="claims")


class Image(Base):
    """An image collected for a product."""

    __tablename__ = "images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    url = Column(Text, nullable=False)
    local_path = Column(Text, default="")
    view = Column(String(50), default="unknown")
    confidence = Column(Float, default=0.0)
    source = Column(String(50), default="web")  # web, video
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="images")


class Video(Base):
    """A video collected for a product."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(String(500), default="")
    local_path = Column(Text, default="")
    duration = Column(Integer, default=0)
    score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="videos")


def init_db(database_url: str) -> Session:
    """Initialize the database and return a session.

    Creates all tables if they don't exist.
    """
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
