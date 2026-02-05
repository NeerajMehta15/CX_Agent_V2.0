import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    phone = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="user", lazy="selectin")
    tickets = relationship("Ticket", back_populates="user", lazy="selectin")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Text, nullable=False, default="pending")  # pending/shipped/delivered/refunded
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(Text, nullable=False)
    description = Column(Text)
    status = Column(Text, nullable=False, default="open")  # open/in_progress/resolved/escalated
    priority = Column(Text, nullable=False, default="medium")  # low/medium/high/critical
    assigned_to = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tickets")


class CannedResponse(Base):
    __tablename__ = "canned_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shortcut = Column(Text, unique=True, nullable=False)  # e.g., "/greet"
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(Text)  # "greeting", "refund", "shipping"
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversationMeta(Base):
    __tablename__ = "conversation_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Text, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sentiment_score = Column(Float)  # -1.0 to 1.0
    sentiment_label = Column(Text)   # negative/neutral/positive
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_session_created", "session_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Text, nullable=False, index=True)
    role = Column(Text, nullable=False)           # user | assistant | tool
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)   # JSON: {tool_name, tool_result, sentiment_at_time}
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def metadata_dict(self) -> dict:
        if self.metadata_json:
            return json.loads(self.metadata_json)
        return {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict):
        self.metadata_json = json.dumps(value) if value else None
