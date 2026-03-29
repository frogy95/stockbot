from core.models import Base
from core.models.screening_result import ScreeningResult


def test_screening_result_tablename():
    assert ScreeningResult.__tablename__ == "screening_results"


def test_screening_result_fields():
    cols = {c.name for c in ScreeningResult.__table__.columns}
    expected = {
        "id", "stock_code", "screening_type", "score", "rank",
        "factors", "is_hot", "status", "screened_at", "expires_at",
    }
    assert expected.issubset(cols)


def test_screening_result_unique_constraint():
    constraints = ScreeningResult.__table__.constraints
    unique_cols = None
    for c in constraints:
        if hasattr(c, "columns") and len(c.columns) == 3:
            unique_cols = {col.name for col in c.columns}
    assert unique_cols == {"stock_code", "screening_type", "screened_at"}


def test_screening_result_indexes():
    index_names = {idx.name for idx in ScreeningResult.__table__.indexes}
    assert "ix_screening_results_type_date" in index_names
    assert "ix_screening_results_score" in index_names


def test_screening_result_registered():
    assert "screening_results" in Base.metadata.tables


def test_screening_result_fk():
    fks = ScreeningResult.__table__.foreign_keys
    fk_targets = {fk.target_fullname for fk in fks}
    assert "stocks.stock_code" in fk_targets
