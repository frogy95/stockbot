import core.database as db_module


def pytest_runtest_setup(item):
    """각 테스트 전에 DB 엔진 글로벌 상태를 리셋하여 이벤트 루프 충돌 방지"""
    db_module._engine = None
    db_module._async_session = None
