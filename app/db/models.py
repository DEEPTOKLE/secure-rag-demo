from sqlalchemy import (
    Column,
    Integer,
    Text,
    DateTime,
    func,
    MetaData,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

metadata = MetaData()
Base = declarative_base(metadata=metadata)


class Chunk(Base):
    """A text chunk (from PDF, OCR, or structured data) stored for retrieval."""

    __tablename__ = "chunks"

    chunk_id = Column(Integer, primary_key=True)
    source_doc_id = Column(Text, nullable=False)
    source_type = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=False)
    exact_locator = Column(JSONB)
    embedding = Column(Vector(384))
    tenant_id = Column(Integer, nullable=False)
    allowed_principals = Column(ARRAY(Text))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmployeeRecord(Base):
    """A structured employee record; also text-indexed via the chunks table."""

    __tablename__ = "employee_records"

    record_id = Column(Integer, primary_key=True)
    source_doc_id = Column(Text, nullable=False)
    source_type = Column(Text, nullable=False, default="db")
    raw_text = Column(Text, nullable=False)
    exact_locator = Column(JSONB)
    tenant_id = Column(Integer, nullable=False)
    allowed_principals = Column(ARRAY(Text))
    employee_name = Column(Text)
    field_name = Column(Text)
    field_value = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
