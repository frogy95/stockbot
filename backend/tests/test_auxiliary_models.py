from core.models import Base
from core.models.corp_code import CorpCode
from core.models.financial_data import FinancialData
from core.models.news_sentiment import NewsSentiment


# ── CorpCode ──────────────────────────────────────────────────────────────────

def test_corp_code_tablename():
    assert CorpCode.__tablename__ == "corp_codes"


def test_corp_code_fields():
    cols = {c.name for c in CorpCode.__table__.columns}
    assert {"id", "corp_code", "corp_name", "stock_code", "modify_date", "updated_at"} == cols


def test_corp_code_unique():
    unique_cols = set()
    for c in CorpCode.__table__.constraints:
        if hasattr(c, "columns") and len(c.columns) == 1:
            names = {col.name for col in c.columns}
            if names == {"corp_code"}:
                unique_cols = names
    assert unique_cols == {"corp_code"}


def test_corp_code_stock_code_index():
    index_names = {idx.name for idx in CorpCode.__table__.indexes}
    assert "ix_corp_codes_stock_code" in index_names


def test_corp_code_registered():
    assert "corp_codes" in Base.metadata.tables


# ── FinancialData ─────────────────────────────────────────────────────────────

def test_financial_data_tablename():
    assert FinancialData.__tablename__ == "financial_data"


def test_financial_data_fields():
    cols = {c.name for c in FinancialData.__table__.columns}
    expected = {
        "id", "stock_code", "fiscal_year", "fiscal_quarter",
        "revenue", "operating_profit", "net_income",
        "extra_data", "source", "collected_at",
    }
    assert expected == cols


def test_financial_data_unique_constraint():
    constraint_names = {c.name for c in FinancialData.__table__.constraints if hasattr(c, "name")}
    assert "uq_financial_data_stock_year_quarter" in constraint_names


def test_financial_data_indexes():
    index_names = {idx.name for idx in FinancialData.__table__.indexes}
    assert "ix_financial_data_stock_code" in index_names
    assert "ix_financial_data_year_quarter" in index_names


def test_financial_data_fk():
    fk_targets = {fk.target_fullname for fk in FinancialData.__table__.foreign_keys}
    assert "stocks.stock_code" in fk_targets


def test_financial_data_registered():
    assert "financial_data" in Base.metadata.tables


# ── NewsSentiment ─────────────────────────────────────────────────────────────

def test_news_sentiment_tablename():
    assert NewsSentiment.__tablename__ == "news_sentiments"


def test_news_sentiment_fields():
    cols = {c.name for c in NewsSentiment.__table__.columns}
    expected = {
        "id", "stock_code", "title", "source_url",
        "published_at", "sentiment_score", "keyword", "collected_at",
    }
    assert expected == cols


def test_news_sentiment_indexes():
    index_names = {idx.name for idx in NewsSentiment.__table__.indexes}
    assert "ix_news_sentiments_stock_published" in index_names


def test_news_sentiment_fk():
    fk_targets = {fk.target_fullname for fk in NewsSentiment.__table__.foreign_keys}
    assert "stocks.stock_code" in fk_targets


def test_news_sentiment_registered():
    assert "news_sentiments" in Base.metadata.tables
