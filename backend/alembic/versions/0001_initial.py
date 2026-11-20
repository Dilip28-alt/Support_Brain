"""Initial migration — create all tables with pgvector indexes.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # businesses
    op.create_table(
        "businesses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_businesses_slug", "businesses", ["slug"], unique=True)

    # users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("is_owner", sa.Boolean, default=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_business_id", "users", ["business_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # knowledge_sources
    op.create_table(
        "knowledge_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.Enum("text", "pdf", "url", name="knowledgesourcetype"), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("original_content", sa.Text),
        sa.Column("source_url", sa.Text),
        sa.Column("file_name", sa.String(255)),
        sa.Column("is_processed", sa.Boolean, default=False),
        sa.Column("chunk_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_sources_business_id", "knowledge_sources", ["business_id"])

    # knowledge_chunks
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text),  # stored as vector, cast in queries
        sa.Column("token_count", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_chunks_business_id", "knowledge_chunks", ["business_id"])
    op.create_index("ix_knowledge_chunks_source_id", "knowledge_chunks", ["source_id"])
    # Alter column type to vector(768) for pgvector
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768);")
    # Create HNSW index for fast approximate nearest neighbor search
    op.execute("CREATE INDEX ix_knowledge_chunks_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);")

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("customer_email", sa.String(255)),
        sa.Column("is_resolved", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_business_id", "conversations", ["business_id"])

    # lessons (before messages so messages can FK to it)
    op.create_table(
        "lessons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("original_answer", sa.Text),
        sa.Column("corrected_answer", sa.Text, nullable=False),
        sa.Column("owner_comment", sa.Text),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("embedding", sa.Text),
        sa.Column("usage_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lessons_business_id", "lessons", ["business_id"])
    op.execute("ALTER TABLE lessons ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768);")
    op.execute("CREATE INDEX ix_lessons_embedding ON lessons USING hnsw (embedding vector_cosine_ops);")

    # messages
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", "system", name="messagerole"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_chunks", sa.Text),
        sa.Column("lesson_id", UUID(as_uuid=True), sa.ForeignKey("lessons.id", ondelete="SET NULL")),
        sa.Column("confidence_score", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_business_id", "messages", ["business_id"])

    # email_accounts
    op.create_table(
        "email_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_address", sa.String(255), nullable=False),
        sa.Column("encrypted_access_token", sa.Text),
        sa.Column("encrypted_refresh_token", sa.Text),
        sa.Column("token_expiry", sa.DateTime(timezone=True)),
        sa.Column("processing_mode", sa.Enum("review", "auto", name="emailprocessingmode"), default="review"),
        sa.Column("status", sa.Enum("connected", "disconnected", "error", name="emailaccountstatus"), default="connected"),
        sa.Column("last_history_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("business_id", "email_address", name="uq_email_account_business"),
    )
    op.create_index("ix_email_accounts_business_id", "email_accounts", ["business_id"])

    # pending_questions
    op.create_table(
        "pending_questions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.Enum("chat", "email", name="pendingquestionsource"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("email_message_id", UUID(as_uuid=True)),   # FK added after email_messages
        sa.Column("customer_question", sa.Text, nullable=False),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("customer_email", sa.String(255)),
        sa.Column("status", sa.Enum("open", "resolved", name="pendingquestionstatus"), default="open"),
        sa.Column("owner_answer", sa.Text),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pending_questions_business_id", "pending_questions", ["business_id"])

    # email_messages
    op.create_table(
        "email_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_account_id", UUID(as_uuid=True), sa.ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gmail_message_id", sa.String(255), unique=True, nullable=False),
        sa.Column("gmail_thread_id", sa.String(255), nullable=False),
        sa.Column("direction", sa.Enum("incoming", "outgoing", name="emailmessagedirection"), nullable=False),
        sa.Column("subject", sa.Text),
        sa.Column("sender", sa.String(255)),
        sa.Column("recipient", sa.String(255)),
        sa.Column("body_text", sa.Text),
        sa.Column("body_html", sa.Text),
        sa.Column("draft_reply", sa.Text),
        sa.Column("status", sa.Enum("pending", "draft", "sent", "failed", "skipped", name="emailmessagestatus"), default="pending"),
        sa.Column("pending_question_id", UUID(as_uuid=True), sa.ForeignKey("pending_questions.id", ondelete="SET NULL")),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_email_messages_business_id", "email_messages", ["business_id"])
    op.create_index("ix_email_messages_gmail_id", "email_messages", ["gmail_message_id"], unique=True)
    op.create_index("ix_email_messages_thread_id", "email_messages", ["gmail_thread_id"])

    # answer_feedback
    op.create_table(
        "answer_feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("feedback_type", sa.Enum("good", "bad", name="feedbacktype"), nullable=False),
        sa.Column("question", sa.Text),
        sa.Column("ai_answer", sa.Text),
        sa.Column("correct_answer", sa.Text),
        sa.Column("owner_comment", sa.Text),
        sa.Column("lesson_created", sa.Boolean, default=False),
        sa.Column("lesson_id", UUID(as_uuid=True), sa.ForeignKey("lessons.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_answer_feedback_business_id", "answer_feedback", ["business_id"])

    # lesson_usage
    op.create_table(
        "lesson_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", UUID(as_uuid=True), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("question", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lesson_usage_business_id", "lesson_usage", ["business_id"])


def downgrade() -> None:
    op.drop_table("lesson_usage")
    op.drop_table("answer_feedback")
    op.drop_table("email_messages")
    op.drop_table("pending_questions")
    op.drop_table("email_accounts")
    op.drop_table("messages")
    op.drop_table("lessons")
    op.drop_table("conversations")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_sources")
    op.drop_table("users")
    op.drop_table("businesses")
    op.execute("DROP TYPE IF EXISTS knowledgesourcetype;")
    op.execute("DROP TYPE IF EXISTS messagerole;")
    op.execute("DROP TYPE IF EXISTS pendingquestionsource;")
    op.execute("DROP TYPE IF EXISTS pendingquestionstatus;")
    op.execute("DROP TYPE IF EXISTS emailprocessingmode;")
    op.execute("DROP TYPE IF EXISTS emailaccountstatus;")
    op.execute("DROP TYPE IF EXISTS emailmessagedirection;")
    op.execute("DROP TYPE IF EXISTS emailmessagestatus;")
    op.execute("DROP TYPE IF EXISTS feedbacktype;")
