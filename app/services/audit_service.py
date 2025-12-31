import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import AuditLog


def log_action(
    session: Session,
    user_id: Optional[int],
    action: str,
    detail: Optional[Dict[str, Any]] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        detail_json=json.dumps(detail or {}, ensure_ascii=False),
        ip=ip,
        user_agent=user_agent,
    )
    session.add(log)
    session.commit()
