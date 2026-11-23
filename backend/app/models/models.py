"""
SQLAlchemy models — all 12 tables with pgvector, UUID PKs, and business isolation.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float,
    ForeignKey, DateTime, Enum as SAEnum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base
import enum


# ─────────────────────────── Enums ────────────────────────────

class KnowledgeSourceType(str, enum.Enum):
    text = "text"
    pdf = "pdf"
    url = "url"

class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    owner = "owner"

class PendingQuestionSource(str, enum.Enum):
    chat = "chat"
    email = "email"

class PendingQuestionStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"

class EmailAccountStatus(str, enum.Enum):
    connected = "connected"
    disconnected = "disconnected"
    error = "error"

class EmailProcessingMode(str, enum.Enum):
    review = "review"
    auto = "auto"

class EmailMessageDirection(str, enum.Enum):
    incoming = "incoming"
    outgoing = "outgoing"

class EmailMessageStatus(str, enum.Enum):
    pending = "pending"
    draft = "draft"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"

class FeedbackType(str, enum.Enum):
    good = "good"
    bad = "bad"


# ─────────────────────────── Models ────────────────────────────

class Business(Base):
    __tablename__ = "businesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    widget_token = Column(String(64), unique=True, nullable=True, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    users = relationship("User", back_populates="business", cascade="all, delete-orphan")
    knowledge_sources = relationship("KnowledgeSource", back_populates="business", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="business", cascade="all, delete-orphan")
    pending_questions = relationship("PendingQuestion", back_populates="business", cascade="all, delete-orphan")
    email_accounts = relationship("EmailAccount", back_populates="business", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="business", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_owner = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    business = relationship("Business", back_populates="users")


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(SAEnum(KnowledgeSourceType), nullable=False)
    title = Column(String(500), nullable=True)
    original_content = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    file_name = Column(String(255), nullable=True)
    is_processed = Column(Boolean, default=False)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    business = relationship("Business", back_populates="knowledge_sources")
    chunks = relationship("KnowledgeChunk", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_knowledge_sources_business_type", "business_id", "source_type"),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=True)   # text-embedding-004 → 768 dims
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    source = relationship("KnowledgeSource", back_populates="chunks")

    __table_args__ = (
        Index("ix_knowledge_chunks_business", "business_id"),
        Index("ix_knowledge_chunks_source", "source_id"),
        # pgvector HNSW index created via Alembic migration
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    business = relationship("Business", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

    __table_args__ = (
        Index("ix_conversations_business_created", "business_id", "created_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(SAEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    source_chunks = Column(Text, nullable=True)   # JSON: list of chunk IDs used
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


class PendingQuestion(Base):
    __tablename__ = "pending_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(SAEnum(PendingQuestionSource), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    email_message_id = Column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True)
    customer_question = Column(Text, nullable=False)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    status = Column(SAEnum(PendingQuestionStatus), default=PendingQuestionStatus.open)
    owner_answer = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    business = relationship("Business", back_populates="pending_questions")

    __table_args__ = (
        Index("ix_pending_questions_business_status", "business_id", "status"),
    )


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    email_address = Column(String(255), nullable=False)
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    processing_mode = Column(SAEnum(EmailProcessingMode), default=EmailProcessingMode.review)
    status = Column(SAEnum(EmailAccountStatus), default=EmailAccountStatus.connected)
    last_history_id = Column(String(100), nullable=True)   # Gmail history id for polling
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    business = relationship("Business", back_populates="email_accounts")
    email_messages = relationship("EmailMessage", back_populates="email_account", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("business_id", "email_address", name="uq_email_account_business"),
    )


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    email_account_id = Column(UUID(as_uuid=True), ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    gmail_message_id = Column(String(255), unique=True, nullable=False, index=True)   # idempotency
    gmail_thread_id = Column(String(255), nullable=False, index=True)
    direction = Column(SAEnum(EmailMessageDirection), nullable=False)
    subject = Column(Text, nullable=True)
    sender = Column(String(255), nullable=True)
    recipient = Column(String(255), nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    draft_reply = Column(Text, nullable=True)
    status = Column(SAEnum(EmailMessageStatus), default=EmailMessageStatus.pending)
    related_message_id = Column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    pending_question_id = Column(UUID(as_uuid=True), ForeignKey("pending_questions.id", ondelete="SET NULL"), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    email_account = relationship("EmailAccount", back_populates="email_messages")

    __table_args__ = (
        Index("ix_email_messages_business_thread", "business_id", "gmail_thread_id"),
    )


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    original_answer = Column(Text, nullable=True)
    corrected_answer = Column(Text, nullable=False)
    owner_comment = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    embedding = Column(Vector(768), nullable=True)   # embedding of the question
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    business = relationship("Business", back_populates="lessons")
    usages = relationship("LessonUsage", back_populates="lesson", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_lessons_business_active", "business_id", "is_active"),
    )


class AnswerFeedback(Base):
    __tablename__ = "answer_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    feedback_type = Column(SAEnum(FeedbackType), nullable=False)
    question = Column(Text, nullable=True)
    ai_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=True)
    owner_comment = Column(Text, nullable=True)
    lesson_created = Column(Boolean, default=False)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_answer_feedback_business", "business_id"),
        Index("ix_answer_feedback_type_created", "business_id", "feedback_type", "created_at"),
    )


class LessonUsage(Base):
    __tablename__ = "lesson_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    question = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lesson = relationship("Lesson", back_populates="usages")

    __table_args__ = (
        Index("ix_lesson_usage_business_created", "business_id", "created_at"),
    )


class EmailProcessingLog(Base):
    __tablename__ = "email_processing_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    email_account_id = Column(UUID(as_uuid=True), ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    gmail_message_id = Column(String(255), nullable=True, index=True)
    action = Column(String(100), nullable=False)   # e.g., "fetch", "draft_generated", "auto_sent", "moved_to_pending", "error"
    status = Column(String(50), nullable=False)   # e.g., "success", "failed", "skipped"
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_email_processing_logs_business_created", "business_id", "created_at"),
    )
