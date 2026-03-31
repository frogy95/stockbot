from core.models import Base
from core.models.audit_log import AuditLog


def test_audit_log_fields():
    cols = {c.name for c in AuditLog.__table__.columns}
    assert {
        "id",
        "action",
        "target_key",
        "old_value",
        "new_value",
        "actor",
        "ip_address",
        "created_at",
    }.issubset(cols)


def test_audit_log_tablename():
    assert AuditLog.__tablename__ == "audit_logs"


def test_audit_log_created_at_server_default():
    col = AuditLog.__table__.columns["created_at"]
    assert col.server_default is not None


def test_audit_log_registered_in_base():
    assert "audit_logs" in Base.metadata.tables
