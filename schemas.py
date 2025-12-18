from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

# 로그인 응답용
class UserResponse(BaseModel):
    uid: UUID
    tier: str
    expiry_date: Optional[datetime] = None
    is_banned: bool

    class Config:
        from_attributes = True

# 구매 검증 요청용
class PurchaseRequest(BaseModel):
    device_id: str
    receipt_data: str

class ContactRequest(BaseModel):
    user_id: Optional[str] = "anonymous" # 유저 식별용 (필요시)
    email: str
    content: str                         # 문의 내용
    device_info: str                     # 기기 모델 (예: iPhone 15 Pro)
    os_version: str                      # iOS 버전
    app_version: str                     # 앱 버전