"""
SQLAlchemy models for autocrawler.

TODO: Define models for:
- CrawlResult: stores crawl output (url, strategy, data, timestamps)
- CrawlJob: scheduled/queued crawl jobs (url, status, scheduled_at)
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class CrawlResult(Base):
    __tablename__ = "crawl_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False, index=True)
    strategy_used = Column(String)
    success = Column(Boolean, default=False)
    data = Column(JSON)
    error = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, running, completed, failed
    scheduled_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    result_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
