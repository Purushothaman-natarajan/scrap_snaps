from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import datetime

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    canonical_name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Source(Base):
    __tablename__ = 'sources'
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, index=True)
    source_type = Column(String)  # manufacturer, retailer, forum, etc.
    reliability_score = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Claim(Base):
    __tablename__ = 'claims'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    source_id = Column(Integer, ForeignKey('sources.id'))
    claim_type = Column(String) # e.g., 'weight', 'battery_life'
    value = Column(String)
    confidence = Column(Float)
    extracted_at = Column(DateTime, default=datetime.datetime.utcnow)

class Image(Base):
    __tablename__ = 'images'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    source_id = Column(Integer, ForeignKey('sources.id'))
    url = Column(String)
    phash = Column(String, index=True)
    view_type = Column(String) # front, back, side, etc.
    local_path = Column(String)

class Video(Base):
    __tablename__ = 'videos'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    url = Column(String, unique=True)
    metadata_json = Column(JSON)

# DB initialization placeholder
def init_db(database_url: str):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
