"""주문 매니저 — 주문 큐 관리 및 체결 폴링."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from core.clients.kis_rest import CancelRequest, KISRestClient, OrderRequest
from core.clients.throttler import TokenBucketThrottler
from core.config import settings
from core.models.trading import Order
from modules.trading.position_sizer import PositionSize
from modules.trading.strategy import TradeSignalData

logger = logging.getLogger(__name__)

# 실전 주문 전략 상수
_LIMIT_ORDER_DIVISION = "05"   # 최우선 지정가
_MARKET_ORDER_DIVISION = "01"  # 시장가
_LIMIT_ORDER_WAIT_SEC = 3.0    # 지정가 체결 대기 시간(초)


class OrderManager:
    """주문 큐 기반 비동기 주문 매니저.

    Parameters
    ----------
    session_factory :
        ``async with session_factory() as session`` 형태의 DB 세션 팩토리.
    rest_client : KISRestClient
        한국투자증권 REST API 클라이언트.
    redis_client :
        redis.asyncio 클라이언트.
    throttler : TokenBucketThrottler
        API Rate Limit 스로틀러.
    """

    def __init__(
        self,
        session_factory,
        rest_client: KISRestClient,
        redis_client,
        throttler: TokenBucketThrottler,
    ):
        self._session_factory = session_factory
        self._rest_client = rest_client
        self._redis = redis_client
        self._throttler = throttler
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # 라이프사이클
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """백그라운드 워커 태스크를 시작한다."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("OrderManager 워커 시작")

    async def stop(self) -> None:
        """백그라운드 워커 태스크를 종료한다."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("OrderManager 워커 종료")

    # ------------------------------------------------------------------
    # 공개 인터페이스
    # ------------------------------------------------------------------

    async def submit_order(
        self, signal: TradeSignalData, position_size: PositionSize
    ) -> Order:
        """주문을 제출한다.

        1. orders 테이블에 status="submitted" 레코드를 생성한다.
        2. 주문 ID를 큐에 enqueue한다.
        3. 생성된 Order 레코드를 반환한다.
        """
        async with self._session_factory() as session:
            order = Order(
                signal_id=None,
                stock_code=signal.stock_code,
                order_type=signal.signal_type,
                quantity=position_size.quantity,
                price=signal.entry_price,
                order_division=_MARKET_ORDER_DIVISION,
                status="submitted",
                submitted_at=datetime.now(tz=timezone.utc),
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            order_id = order.id

        await self._queue.put(order_id)
        logger.info("주문 제출: order_id=%d stock_code=%s", order_id, signal.stock_code)
        return order

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    async def _worker(self) -> None:
        """큐에서 주문 ID를 꺼내 순차적으로 실행한다."""
        logger.info("OrderManager 워커 루프 진입")
        while True:
            try:
                order_id = await self._queue.get()
                try:
                    await self._execute_order(order_id)
                except Exception:
                    logger.exception("주문 실행 중 예외: order_id=%d", order_id)
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                logger.info("OrderManager 워커 취소됨")
                raise

    async def _execute_order(self, order_id: int) -> None:
        """단일 주문을 실행한다.

        - 모의거래(settings.TRADING_ENV=="paper"): 시장가("01")만 사용
        - 실전: 최우선 지정가("05") → 3초 대기 → 미체결 시 취소 → 시장가("01")
        """
        # 주문 레코드 조회
        async with self._session_factory() as session:
            result = await session.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            if order is None:
                logger.error("주문 레코드를 찾을 수 없음: order_id=%d", order_id)
                return

            stock_code = order.stock_code
            order_type = order.order_type
            quantity = order.quantity
            price = order.price

        await self._throttler.acquire()

        is_paper = settings.TRADING_ENV == "paper"

        if is_paper:
            # 모의거래: 시장가 주문
            order_req = OrderRequest(
                stock_code=stock_code,
                order_type=order_type,
                quantity=quantity,
                price=0,
                order_division=_MARKET_ORDER_DIVISION,
            )
            try:
                response = await self._rest_client.place_order(order_req)
            except Exception:
                logger.exception("시장가 주문 실패: order_id=%d", order_id)
                await self._update_order_status(order_id, "failed")
                return

            order_no = response.order_no
            await self._update_order_no(order_id, order_no, _MARKET_ORDER_DIVISION)
            filled = await self._poll_fill_status(order_no)
            if not filled:
                await self._update_order_status(order_id, "timeout")
                await self._reconcile_timeout(order_id)
            else:
                await self._update_order_status(
                    order_id, "filled", filled_at=datetime.now(tz=timezone.utc)
                )
        else:
            # 실전: 최우선 지정가 시도
            limit_req = OrderRequest(
                stock_code=stock_code,
                order_type=order_type,
                quantity=quantity,
                price=int(price),
                order_division=_LIMIT_ORDER_DIVISION,
            )
            try:
                limit_resp = await self._rest_client.place_order(limit_req)
            except Exception:
                logger.exception("지정가 주문 실패: order_id=%d", order_id)
                await self._update_order_status(order_id, "failed")
                return

            limit_order_no = limit_resp.order_no
            await self._update_order_no(order_id, limit_order_no, _LIMIT_ORDER_DIVISION)

            # 3초 대기 후 체결 여부 확인
            await asyncio.sleep(_LIMIT_ORDER_WAIT_SEC)
            await self._throttler.acquire()
            status_data = await self._rest_client.get_order_status(limit_order_no)
            filled = self._is_filled(status_data)

            if filled:
                await self._update_order_status(
                    order_id, "filled", filled_at=datetime.now(tz=timezone.utc)
                )
                return

            # 미체결 → 취소 후 시장가 폴백
            logger.info("지정가 미체결, 취소 후 시장가 주문: order_id=%d", order_id)
            cancel_req = CancelRequest(
                stock_code=stock_code,
                quantity=quantity,
                cancel_type="02",
            )
            try:
                await self._rest_client.cancel_order(limit_order_no, cancel_req)
            except Exception:
                logger.warning("주문 취소 실패 (무시하고 시장가 진행): order_id=%d", order_id)

            await self._throttler.acquire()
            market_req = OrderRequest(
                stock_code=stock_code,
                order_type=order_type,
                quantity=quantity,
                price=0,
                order_division=_MARKET_ORDER_DIVISION,
            )
            try:
                market_resp = await self._rest_client.place_order(market_req)
            except Exception:
                logger.exception("시장가 폴백 주문 실패: order_id=%d", order_id)
                await self._update_order_status(order_id, "failed")
                return

            market_order_no = market_resp.order_no
            await self._update_order_no(order_id, market_order_no, _MARKET_ORDER_DIVISION)
            filled = await self._poll_fill_status(market_order_no)
            if not filled:
                await self._update_order_status(order_id, "timeout")
                await self._reconcile_timeout(order_id)
            else:
                await self._update_order_status(
                    order_id, "filled", filled_at=datetime.now(tz=timezone.utc)
                )

    async def _poll_fill_status(
        self,
        order_no: str,
        max_polls: int = 15,
        interval: float = 2.0,
    ) -> bool:
        """체결 여부를 반복 폴링한다.

        Parameters
        ----------
        order_no : str
            주문 번호.
        max_polls : int
            최대 폴링 횟수 (기본 15회 = 30초).
        interval : float
            폴링 간격 (초, 기본 2.0).

        Returns
        -------
        bool
            체결 시 True, timeout 시 False.
        """
        for poll_no in range(max_polls):
            await asyncio.sleep(interval)
            await self._throttler.acquire()
            try:
                data = await self._rest_client.get_order_status(order_no)
            except Exception:
                logger.warning("체결 상태 조회 실패 (poll %d): order_no=%s", poll_no + 1, order_no)
                continue

            if self._is_filled(data):
                logger.info("체결 확인: order_no=%s (poll %d)", order_no, poll_no + 1)
                return True

        logger.warning("체결 폴링 timeout: order_no=%s", order_no)
        return False

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    @staticmethod
    def _is_filled(status_data: dict) -> bool:
        """체결 응답 데이터에서 체결 여부를 판별한다.

        output1 리스트의 첫 번째 항목의 tot_ccld_qty > 0이면 체결로 간주.
        """
        output1 = status_data.get("output1", [])
        if not output1:
            return False
        first = output1[0] if isinstance(output1, list) else output1
        try:
            return int(first.get("tot_ccld_qty", 0)) > 0
        except (ValueError, TypeError):
            return False

    async def _reconcile_timeout(self, order_id: int) -> None:
        """timeout 주문에 대해 한투 잔고와 positions를 비교하여 불일치 시 경고.

        다음 잔고 조회 시 호출하여 미해결 사항 #2 기본 처리를 수행한다.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            if order is None or order.status != "timeout":
                return

        try:
            positions = await self._rest_client.get_positions()
            for pos in positions:
                if pos.stock_code == order.stock_code and pos.quantity > 0:
                    logger.warning(
                        "timeout 주문 reconciliation: %s — 한투 잔고에 %d주 존재, "
                        "positions 테이블과 동기화 필요",
                        order.stock_code,
                        pos.quantity,
                    )
                    return
            logger.info(
                "timeout 주문 reconciliation: %s — 한투 잔고에 없음, 주문 미체결 확정",
                order.stock_code,
            )
        except Exception:
            logger.exception("reconciliation 실패: order_id=%d", order_id)

    async def _update_order_status(
        self,
        order_id: int,
        status: str,
        filled_at: datetime | None = None,
    ) -> None:
        """orders 테이블의 status 필드를 업데이트한다."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            if order is None:
                return
            order.status = status
            if filled_at is not None:
                order.filled_at = filled_at
            await session.commit()

    async def _update_order_no(
        self,
        order_id: int,
        order_no: str,
        order_division: str,
    ) -> None:
        """orders 테이블의 order_no와 order_division을 업데이트한다."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            if order is None:
                return
            order.order_no = order_no
            order.order_division = order_division
            await session.commit()
