"""포지션 사이저 — 종목별 투자금·수량 산출."""

from pydantic import BaseModel
from sqlalchemy import select

from core.models.settings import SystemSetting
from core.models.stock import Stock


class PositionSize(BaseModel):
    """포지션 사이징 결과."""

    invest_amount: int
    quantity: int
    is_leverage: bool
    size_pct: float


class PositionSizer:
    """잔고 대비 비율 기반 포지션 사이저.

    Parameters
    ----------
    session_factory : async callable
        ``async with session_factory() as session`` 형태로 DB 세션을 얻는 팩토리.
    """

    # 기본 비율 (settings 테이블에 값이 없을 때 사용)
    DEFAULT_POSITION_SIZE_PCT = 10.0
    DEFAULT_LEVERAGE_POSITION_SIZE_PCT = 5.0

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._position_size_pct: float = self.DEFAULT_POSITION_SIZE_PCT
        self._leverage_position_size_pct: float = self.DEFAULT_LEVERAGE_POSITION_SIZE_PCT

    async def load_settings(self) -> None:
        """settings 테이블에서 position_size_pct, leverage_position_size_pct 로드."""
        async with self._session_factory() as session:
            stmt = select(SystemSetting).where(
                SystemSetting.key.in_(
                    ["position_size_pct", "leverage_position_size_pct"]
                )
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            for row in rows:
                if row.key == "position_size_pct":
                    self._position_size_pct = float(row.value)
                elif row.key == "leverage_position_size_pct":
                    self._leverage_position_size_pct = float(row.value)

    async def calculate(
        self,
        stock_code: str,
        current_price: int,
        balance_amount: int,
        size_ratio: float = 1.0,
    ) -> PositionSize:
        """투자금과 주문 수량을 계산한다.

        Parameters
        ----------
        stock_code : str
            종목코드 (예: ``"005930"``).
        current_price : int
            현재가 (원).
        balance_amount : int
            투자 가능 잔고 (원).
        size_ratio : float
            포지션 비율 (0.0~1.0). 기본값 1.0 (100%).
            적응형/기본 후보 등 안전장치 적용 시 0.5 등으로 설정.

        Returns
        -------
        PositionSize
            투자금, 수량, 레버리지 여부, 적용 비율.
        """
        leverage = await self.is_leverage(stock_code)
        size_pct = (
            self._leverage_position_size_pct if leverage else self._position_size_pct
        )

        invest_amount = int(balance_amount * size_pct / 100)
        quantity = self._compute_quantity(invest_amount, current_price)

        # size_ratio 적용 (후보 플래그로 전달된 비율)
        if size_ratio != 1.0:
            quantity = int(quantity * size_ratio)
            invest_amount = int(invest_amount * size_ratio)

        return PositionSize(
            invest_amount=invest_amount,
            quantity=quantity,
            is_leverage=leverage,
            size_pct=size_pct,
        )

    async def is_leverage(self, stock_code: str) -> bool:
        """stocks 테이블에서 레버리지 종목 여부를 판별한다.

        ``stock_name`` 에 ``"레버리지"`` 또는 ``"2X"`` 가 포함되면 레버리지로 간주한다.
        """
        async with self._session_factory() as session:
            stmt = select(Stock).where(Stock.stock_code == stock_code)
            result = await session.execute(stmt)
            stock = result.scalar_one_or_none()

            if stock is None:
                return False

            name = stock.stock_name or ""
            return "레버리지" in name or "2X" in name

    @staticmethod
    def _compute_quantity(invest_amount: int, price: int) -> int:
        """투자금을 가격으로 나눠 매수 가능 수량을 구한다 (절사).

        ``price`` 가 0 이하이면 ``0`` 을 반환하여 ZeroDivisionError 를 방지한다.
        """
        if price <= 0:
            return 0
        return invest_amount // price
