from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime
from database import Base

class User(Base):
    __tablename__ = "tbl_user"

    uid = Column(
        UUID(
            as_uuid = True
        ),
        primary_key = True,
        default     = uuid.uuid4
    )
    device_id = Column(
        String,
        unique   = True,
        index    = True,
        nullable = False
    )
    tier = Column(
        String,
        default = "free"
    )
    expiry_date = Column(
        DateTime(
            timezone = True
        ),
        nullable     = True
    )
    latest_receipt = Column(
        Text,
        nullable = True
    )
    is_banned = Column(
        Boolean,
        default = False
    )
    app_version = Column(
        String(20),
        nullable = True
    )
    created_at = Column(
        DateTime(
            timezone = True
        ),
        default      = datetime.datetime.utcnow
    )