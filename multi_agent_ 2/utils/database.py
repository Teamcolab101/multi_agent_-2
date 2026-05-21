"""
Clean Database layer — SQLite via SQLAlchemy
Single Database Version
"""

import hashlib
import os
import datetime

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Float
)

from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    relationship
)

# ─────────────────────────────
# DATABASE SETUP
# ─────────────────────────────

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_PATH = os.path.join(
    BASE_DIR,
    "hr_chatbot.db"
)

print("DB FILE:", DB_PATH)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={
        "check_same_thread": False
    }
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

# ─────────────────────────────
# MODELS
# ─────────────────────────────

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True
    )

    username = Column(
        String(80),
        unique=True,
        nullable=False
    )

    email = Column(
        String(120),
        unique=True,
        nullable=False
    )

    password_hash = Column(
        String(256),
        nullable=False
    )

    role = Column(
        String(50),
        default="employee"
    )

    is_active = Column(
        Boolean,
        default=True
    )

    sessions = relationship(
        "ConversationSession",
        back_populates="user"
    )

    tickets = relationship(
        "ITTicket",
        back_populates="user"
    )


class ConversationSession(Base):

    __tablename__ = "conversation_sessions"

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    session_id = Column(
        String(100),
        unique=True
    )

    user = relationship(
        "User",
        back_populates="sessions"
    )

    messages = relationship(
        "ConversationMessage",
        back_populates="session"
    )


class ConversationMessage(Base):

    __tablename__ = "conversation_messages"

    id = Column(
        Integer,
        primary_key=True
    )

    session_id = Column(
        Integer,
        ForeignKey("conversation_sessions.id")
    )

    role = Column(String(20))

    content = Column(Text)

    agent_used = Column(String(50))

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )

    session = relationship(
        "ConversationSession",
        back_populates="messages"
    )


class ITTicket(Base):

    __tablename__ = "it_tickets"

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    ticket_id = Column(String(50))

    subject = Column(String(300))

    description = Column(Text)

    category = Column(String(100))

    priority = Column(String(50))

    status = Column(
        String(50),
        default="Pending"
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )

    user = relationship(
        "User",
        back_populates="tickets"
    )


class LeaveRequest(Base):

    __tablename__ = "leave_requests"

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    leave_type = Column(String(50))

    start_date = Column(String(20))

    end_date = Column(String(20))

    days = Column(Float)

    reason = Column(Text)

    status = Column(
        String(30),
        default="Pending"
    )

    applied_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )

# ─────────────────────────────
# INIT DB
# ─────────────────────────────

def init_db():

    Base.metadata.create_all(engine)

# ─────────────────────────────
# PASSWORD HASH
# ─────────────────────────────

def _hash_pw(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()

# ─────────────────────────────
# AUTHENTICATION
# ─────────────────────────────

def authenticate_user(
    username,
    password
):

    db = SessionLocal()

    try:

        return db.query(User).filter(
            User.username == username,
            User.password_hash == _hash_pw(password),
            User.is_active == True
        ).first()

    finally:
        db.close()

# ─────────────────────────────
# DEMO USERS
# ─────────────────────────────

def seed_demo_users():

    db = SessionLocal()

    try:

        existing = db.query(User).first()

        if existing:
            return

        users = [

            User(
                username="admin",
                email="admin@acme.com",
                password_hash=_hash_pw("admin123"),
                role="admin"
            ),

            User(
                username="hrmanager",
                email="hr@acme.com",
                password_hash=_hash_pw("hr1234"),
                role="hr"
            ),

            User(
                username="employee1",
                email="emp1@acme.com",
                password_hash=_hash_pw("emp123"),
                role="employee"
            ),

            User(
                username="manager",
                email="mng@acme.com",
                password_hash=_hash_pw("mng123"),
                role="manager"
            )
        ]

        db.add_all(users)

        db.commit()

        print("Demo users created")

    finally:
        db.close()

# ─────────────────────────────
# SAVE MESSAGE
# ─────────────────────────────

def save_message(
    session_id,
    role,
    content,
    agent_used=""
):

    db = SessionLocal()

    try:

        sess = db.query(
            ConversationSession
        ).filter_by(
            session_id=session_id
        ).first()

        if not sess:
            return

        msg = ConversationMessage(
            session_id=sess.id,
            role=role,
            content=content,
            agent_used=agent_used
        )

        db.add(msg)

        db.commit()

    finally:
        db.close()

# ─────────────────────────────
# GET CHAT HISTORY
# ─────────────────────────────

def get_chat_history(
    session_id,
    limit=20
):

    db = SessionLocal()

    try:

        sess = db.query(
            ConversationSession
        ).filter_by(
            session_id=session_id
        ).first()

        if not sess:
            return []

        msgs = (
            db.query(ConversationMessage)
            .filter_by(session_id=sess.id)
            .order_by(
                ConversationMessage.created_at.asc()
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "role": m.role,
                "content": m.content
            }
            for m in msgs
        ]

    finally:
        db.close()

# ─────────────────────────────
# SAVE TICKET
# ─────────────────────────────

def save_ticket(data):

    db = SessionLocal()

    try:

        ticket = ITTicket(
            user_id=data.get("user_id"),
            ticket_id=data.get("ticket_id"),
            subject=data.get("subject"),
            description=data.get("description"),
            category=data.get("category"),
            priority=data.get("priority"),
            status=data.get("status", "Pending")
        )

        db.add(ticket)

        db.commit()

        db.refresh(ticket)

        return ticket

    finally:
        db.close()

# ─────────────────────────────
# GET LATEST TICKET
# ─────────────────────────────

def get_latest_ticket(user_id):

    db = SessionLocal()

    try:

        return (
            db.query(ITTicket)
            .filter_by(user_id=user_id)
            .order_by(
                ITTicket.created_at.desc()
            )
            .first()
        )

    finally:
        db.close()

# ─────────────────────────────
# APPLY LEAVE
# ─────────────────────────────

def apply_leave(
    employee_name,
    start_date,
    end_date,
    reason
):

    db = SessionLocal()

    try:

        user = db.query(User).filter(
            User.username == employee_name
        ).first()

        if not user:
            print("USER NOT FOUND")
            return None

        leave = LeaveRequest(
            user_id=user.id,
            leave_type="General",
            start_date=start_date,
            end_date=end_date,
            days=1,
            reason=reason,
            status="Pending"
        )

        db.add(leave)

        db.commit()

        db.refresh(leave)

        print("LEAVE STORED SUCCESSFULLY")

        return leave

    finally:
        db.close()

# ─────────────────────────────
# GET PENDING LEAVES
# ─────────────────────────────

def get_pending_leave_requests():

    db = SessionLocal()

    try:

        leaves = (
            db.query(
                LeaveRequest,
                User.username
            )
            .join(
                User,
                LeaveRequest.user_id == User.id
            )
            .filter(
                LeaveRequest.status == "Pending"
            )
            .all()
        )

        result = []

        for leave, username in leaves:

            result.append((
                leave.id,
                username,
                leave.start_date,
                leave.end_date,
                leave.reason,
                leave.status
            ))

        return result

    finally:
        db.close()

# ─────────────────────────────
# APPROVE LEAVE
# ─────────────────────────────

def approve_leave_request(leave_id):

    db = SessionLocal()

    try:

        leave = db.query(
            LeaveRequest
        ).filter_by(
            id=leave_id
        ).first()

        if not leave:
            return False

        leave.status = "Approved"

        db.commit()

        return True

    finally:
        db.close()

# ─────────────────────────────
# INITIALIZE DATABASE
# ─────────────────────────────

init_db()
seed_demo_users()