"""수집 스케줄러 — APScheduler 기반 장전/장중/장후 데이터 수집 오케스트레이션."""

import asyncio
import html
import json
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import settings
from core.models.screening_result import ScreeningResult
from core.models.stock import Stock

from core.clients.kis_rest import KISRestClient
from core.redis import RedisClient
from core.trading_calendar import is_trading_day
from modules.collector.models import CollectionResult, ValidationResult
from modules.collector.validator import CollectionValidator
from modules.collector.sources.data_go_kr import DataGoKrCollector
from modules.collector.sources.kis_collector import KISCollector
from modules.collector.sources.kis_daily_collector import KISDailyCollector
from modules.collector.sources.kis_master import KISMasterCollector
from modules.collector.sources.kis_realtime import (
    parse_raw_message,
    parse_execution,
    parse_orderbook,
)
from modules.collector.ws_manager import WSSubscriptionManager
from modules.collector.trade_strength import TradeStrengthCalculator
from core.clients.kis_ws import KISWebSocketClient

logger = logging.getLogger(__name__)

MISFIRE_GRACE_TIME = 300  # 초 (5분 — Railway 재시작/스케줄러 지연 대응)
REALTIME_CACHE_TTL = 10  # 초
STATE_TTL = 86400  # 초 (Redis 상태 TTL — 24시간)
ALERT_MAX_LEN = 200  # 알림 메시지 에러 문자열 최대 길이
RECOVERY_INSTRUCTION = "POST /api/v1/collector/trigger/premarket-pipeline"
REDIS_STATE_KEY_PREFIX = "scheduler:last_"
PIPELINE_STATUS_KEY = "scheduler:pipeline_status"
PIPELINE_HEALTHY_KEY = "scheduler:pipeline_healthy"
ALL_PIPELINE_STEPS = ["premarket", "etf_master", "primary_screen", "etf", "dart", "sentiment"]
PIPELINE_RUNNING_KEY = "scheduler:pipeline_running"

# 의존성 맵: 각 단계의 선행 단계 목록
DEPENDENCY_MAP: dict[str, list[str]] = {
    "primary_screen": ["premarket"],
    "etf": ["etf_master"],
    "dart": ["primary_screen"],
    "sentiment": ["primary_screen"],
}
# pipeline_healthy = "true" 조건: 두 단계 모두 success
CORE_STEPS = ["premarket", "primary_screen"]


class CollectorScheduler:
    """수집 스케줄러.

    장전(08:00) 공공데이터포털 일괄 수집, 장중(09:00~15:30) 한투 WS 실시간 수신을 관리한다.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        rest_client: KISRestClient,
        ws_manager: WSSubscriptionManager,
        trade_strength: TradeStrengthCalculator,
        ws_client: KISWebSocketClient,
        redis: RedisClient,
        primary_screener=None,
        realtime_screener=None,
        inquiry_client: KISRestClient | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._rest_client = rest_client
        self._inquiry_client = inquiry_client
        self._ws_manager = ws_manager
        self._trade_strength = trade_strength
        self._ws_client = ws_client
        self._redis = redis
        self._primary_screener = primary_screener
        self._realtime_screener = realtime_screener
        self._validator = CollectionValidator()
        self._scheduler = AsyncIOScheduler()
        self._running = False
        self._last_premarket: datetime | None = None
        self._last_etf: datetime | None = None
        self._last_primary_screen: datetime | None = None
        self._last_secondary_screen: datetime | None = None
        self._last_dart: datetime | None = None
        self._last_sentiment: datetime | None = None
        self._last_etf_master: datetime | None = None
        self._telegram_bot = None  # 텔레그램 봇 (main.py에서 후속 주입)
        self._notifier_manager = None  # 알림 매니저 (main.py에서 후속 주입)
        self._trading_engine = None  # 매매 엔진 (main.py에서 후속 주입)
        self._pipeline_status: dict = {}  # get_status API 계약 유지 — Redis 연동은 의존성 체인 구현 시 추가
        self._secondary_skip_count: int = 0
        self._secondary_no_data_count: int = 0  # WS 연결 상태인데 실시간 데이터 없는 연속 횟수

    @property
    def is_running(self) -> bool:
        """스케줄러 실행 여부."""
        return self._running

    def set_telegram_bot(self, bot) -> None:
        """텔레그램 봇 참조 설정 (main.py에서 후속 주입)."""
        self._telegram_bot = bot

    def set_notifier_manager(self, manager) -> None:
        """알림 매니저 참조 설정 (main.py에서 후속 주입)."""
        self._notifier_manager = manager

    def set_trading_engine(self, engine) -> None:
        """매매 엔진 참조 설정 (main.py에서 후속 주입)."""
        self._trading_engine = engine

    @staticmethod
    def _are_core_steps_healthy(pipeline_status: dict) -> bool:
        """CORE_STEPS가 모두 'success'이고 validation(있으면) passed인지 확인한다."""
        for s in CORE_STEPS:
            step_data = pipeline_status.get(s, {})
            if step_data.get("status") != "success":
                return False
            v = step_data.get("validation")
            if v is not None and not v.get("passed", True):
                return False
        return True

    async def _get_pipeline_status(self) -> dict:
        """Redis에서 pipeline_status JSON을 읽어 dict로 반환. 없으면 빈 dict."""
        raw = await self._redis.get(PIPELINE_STATUS_KEY)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    async def _update_step_status(
        self,
        step: str,
        status: str,
        error: str | None = None,
        collected_count: int | None = None,
        validation: ValidationResult | None = None,
    ) -> None:
        """pipeline_status의 해당 step을 업데이트하고 Redis에 저장한다.

        status가 'success'이고 모든 CORE_STEPS가 'success'이면 pipeline_healthy를 'true'로 설정.
        """
        pipeline_status = await self._get_pipeline_status()
        entry: dict = {"status": status, "timestamp": datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).isoformat()}
        if error is not None:
            entry["error"] = error
        if collected_count is not None:
            entry["collected_count"] = collected_count
        if validation is not None:
            entry["validation"] = {
                "passed": validation.passed,
                "failure_type": validation.failure_type,
                "failure_reason": validation.failure_reason,
                "details": validation.details,
                "severity": validation.severity,
            }
        pipeline_status[step] = entry
        await self._redis.set(PIPELINE_STATUS_KEY, json.dumps(pipeline_status), ttl=STATE_TTL)
        self._pipeline_status = pipeline_status

        if status == "success" and self._are_core_steps_healthy(pipeline_status):
            await self._redis.set(PIPELINE_HEALTHY_KEY, "true", ttl=STATE_TTL)

    async def _run_db_validation(self, step: str, validator_method: str) -> None:
        """DB 후검증 실행 → 결과를 pipeline_status에 기록."""
        try:
            async with self._session_factory() as db_session:
                db_validation = await getattr(self._validator, validator_method)(db_session)
            if not db_validation.passed:
                logger.warning("DB 후검증 실패: %s", db_validation.failure_reason)
            step_data = self._pipeline_status.get(step, {})
            step_data["db_validation"] = {
                "passed": db_validation.passed,
                "failure_reason": db_validation.failure_reason,
                "details": db_validation.details,
            }
            self._pipeline_status[step] = step_data
            await self._redis.set(PIPELINE_STATUS_KEY, json.dumps(self._pipeline_status), ttl=STATE_TTL)
        except Exception:
            logger.debug("%s DB 후검증 실행 실패", step, exc_info=True)

    async def _check_dependency(self, step: str, pipeline_status: dict | None = None) -> bool:
        """DEPENDENCY_MAP에서 선행 단계를 확인, 모든 선행이 'success'이면 True.

        pipeline_status를 외부에서 전달하면 추가 Redis 조회를 생략한다.
        """
        deps = DEPENDENCY_MAP.get(step, [])
        if not deps:
            return True
        if pipeline_status is None:
            pipeline_status = await self._get_pipeline_status()
        return all(
            pipeline_status.get(dep, {}).get("status") == "success"
            for dep in deps
        )

    async def get_pipeline_status(self) -> dict:
        """파이프라인 상태 조회 (API 노출용)."""
        return await self._get_pipeline_status()

    async def _send_failure_alert(self, step: str, error: str) -> None:
        """파이프라인 단계 실패 시 텔레그램 알림 발송."""
        if self._telegram_bot is None:
            return
        msg = (
            f"<b>[장애]</b> {step} 실패\n"
            f"에러: {html.escape(error[:ALERT_MAX_LEN])}\n"
            f"수동 복구: {RECOVERY_INSTRUCTION}"
        )
        await self._telegram_bot.send_notification(msg)

    async def _send_fallback_info_alert(self, step: str, portal_reason: str, kis_collected: int) -> None:
        """포털 실패 → KIS 폴백 성공 시 [정보] 알림 발송."""
        if self._telegram_bot is None:
            return
        msg = (
            f"<b>[정보]</b> {step} 포털 수집 실패, KIS 보조 수집 전환\n"
            f"포털 실패 사유: {html.escape(portal_reason[:ALERT_MAX_LEN])}\n"
            f"KIS 보조 수집: {kis_collected}건"
        )
        await self._telegram_bot.send_notification(msg)

    async def _send_double_failure_alert(self, step: str, portal_reason: str, kis_reason: str) -> None:
        """포털 + KIS 이중 실패 시 [긴급] 알림 발송."""
        if self._telegram_bot is None:
            return
        msg = (
            f"<b>[긴급]</b> {step} 이중 실패 — 수동 복구 필요\n"
            f"포털 실패: {html.escape(portal_reason[:ALERT_MAX_LEN])}\n"
            f"KIS 실패: {html.escape(kis_reason[:ALERT_MAX_LEN])}\n"
            f"수동 복구: {RECOVERY_INSTRUCTION}"
        )
        await self._telegram_bot.send_notification(msg)

    async def _send_stale_data_alert(self, details: dict) -> None:
        """DB 폴백 스크리닝 — T-2 데이터 사용 시 [경고] 알림 발송."""
        if self._telegram_bot is None:
            return
        msg = (
            f"<b>[경고]</b> DB 폴백 스크리닝 -- T-2 데이터 사용\n"
            f"최신 데이터: {details.get('latest_date')}\n"
            f"건수: {details.get('total_count')}건\n"
            f"소스: {details.get('source_counts')}"
        )
        await self._telegram_bot.send_notification(msg)

    async def _send_recovery_alert(self, success: bool) -> None:
        """수동 복구 결과 알림 발송."""
        if self._telegram_bot is None:
            return
        if success:
            msg = "<b>[복구 완료]</b> 장전 파이프라인 정상 복구"
        else:
            msg = "<b>[복구 실패]</b> 장전 파이프라인 일부 실패 — 수동 확인 필요"
        await self._telegram_bot.send_notification(msg)

    async def _run_scheduled_pipeline(self) -> None:
        """08:00 CronTrigger용 장전 파이프라인. 락 선점 후 체인 실행."""
        today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
        if not is_trading_day(today):
            logger.info("비거래일 스킵: step=premarket_pipeline date=%s", today)
            return
        existing = await self._redis.get(PIPELINE_RUNNING_KEY)
        if existing:
            logger.warning("파이프라인 이미 실행 중 -- 자동 스케줄 스킵")
            return
        await self._redis.set(PIPELINE_RUNNING_KEY, "auto", ttl=STATE_TTL)
        t0 = time.monotonic()
        logger.info("장전 파이프라인 시작 (자동 스케줄)")
        try:
            await self.run_premarket_pipeline()
        finally:
            logger.info("장전 파이프라인 종료 (자동 스케줄, 소요: %.1f초)", time.monotonic() - t0)

    async def run_premarket_pipeline(self) -> dict:
        """장전 파이프라인 오케스트레이터.

        락 선점은 호출자(API 핸들러 또는 _run_scheduled_pipeline)가 담당한다.
        이 메서드는 단계를 순차 실행하고 finally에서 락을 해제한다.
        실패한 단계의 의존 단계는 스킵되지만 독립 단계는 계속 실행한다.
        """
        try:
            await self._premarket_collect()
            await self._etf_master_collect()
            await self._primary_screen()
            await self._etf_collect()
            await self._dart_collect()
            await self._sentiment_collect()
        finally:
            await self._redis.delete(PIPELINE_RUNNING_KEY)

        await self._send_recovery_alert(success=self._are_core_steps_healthy(self._pipeline_status))
        return {"completed": True, "pipeline_status": self._pipeline_status}

    async def _load_state_from_redis(self) -> None:
        """Redis에서 _last_* 타임스탬프를 복원한다."""
        key_field_map = {
            f"{REDIS_STATE_KEY_PREFIX}premarket": "_last_premarket",
            f"{REDIS_STATE_KEY_PREFIX}etf": "_last_etf",
            f"{REDIS_STATE_KEY_PREFIX}primary_screen": "_last_primary_screen",
            f"{REDIS_STATE_KEY_PREFIX}etf_master": "_last_etf_master",
            f"{REDIS_STATE_KEY_PREFIX}dart": "_last_dart",
            f"{REDIS_STATE_KEY_PREFIX}sentiment": "_last_sentiment",
        }
        for key, field in key_field_map.items():
            try:
                value = await self._redis.get(key)
                if value:
                    setattr(self, field, datetime.fromisoformat(value))
            except Exception:
                logger.debug("Redis 상태 로드 실패 (key=%s)", key)

    async def _save_last_timestamp(self, job_name: str, dt: datetime) -> None:
        """Redis에 scheduler:last_{job_name} 키로 타임스탬프를 저장한다 (TTL STATE_TTL)."""
        try:
            await self._redis.set(f"{REDIS_STATE_KEY_PREFIX}{job_name}", dt.isoformat(), ttl=STATE_TTL)
        except Exception:
            logger.debug("Redis 타임스탬프 저장 실패 (job=%s)", job_name)

    async def start(self) -> None:
        """스케줄러 시작 + job 등록."""
        await self._load_state_from_redis()
        tz = ZoneInfo(settings.MARKET_TIMEZONE)
        # 장전 파이프라인: 08:00 단일 체인 (개별 CronTrigger 대신 래퍼로 순차 실행)
        self._scheduler.add_job(
            self._run_scheduled_pipeline,
            CronTrigger(hour=8, minute=0, timezone=tz),
            id="premarket_pipeline",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._market_open,
            CronTrigger(hour=9, minute=0, timezone=tz),
            id="market_open",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._market_close,
            CronTrigger(hour=15, minute=30, timezone=tz),
            id="market_close",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._market_open_recovery,
            CronTrigger(hour=9, minute=5, timezone=tz),
            id="market_open_recovery",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        # 08:30 포털 재시도: 포털 수집이 실패했을 때 재시도 (체인 외 독립 실행)
        self._scheduler.add_job(
            self._premarket_retry,
            CronTrigger(hour=8, minute=30, timezone=tz),
            id="premarket_retry",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        # 2차 스크리닝: 09:30~15:30 30초 주기
        if self._realtime_screener:
            self._scheduler.add_job(
                self._secondary_screen,
                IntervalTrigger(seconds=30),
                id="secondary_screen",
                misfire_grace_time=MISFIRE_GRACE_TIME,
            )
            # 시작 시에는 일시 정지, _market_open에서 resume
            self._scheduler.get_job("secondary_screen").pause()
        self._scheduler.start()
        self._running = True
        logger.info("수집 스케줄러 시작")

    async def stop(self) -> None:
        """스케줄러 종료."""
        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("수집 스케줄러 종료")

    def get_status(self) -> dict:
        """스케줄러 상태 조회."""
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "next_run": next_run.isoformat() if next_run else None,
            })

        return {
            "running": self._running,
            "job_count": len(jobs),
            "next_jobs": jobs,
            "ws_subscriptions": self._ws_manager.count,
            "last_premarket": self._last_premarket.isoformat() if self._last_premarket else None,
            "last_etf": self._last_etf.isoformat() if self._last_etf else None,
            "last_etf_master": self._last_etf_master.isoformat() if self._last_etf_master else None,
            "last_dart": self._last_dart.isoformat() if self._last_dart else None,
            "last_sentiment": self._last_sentiment.isoformat() if self._last_sentiment else None,
            "pipeline_status": self._pipeline_status,
        }

    def get_auxiliary_status(self) -> dict:
        """보조 데이터 수집 상태 조회."""
        return {
            "last_dart": self._last_dart.isoformat() if self._last_dart else None,
            "last_sentiment": self._last_sentiment.isoformat() if self._last_sentiment else None,
        }

    def get_screening_status(self) -> dict:
        """스크리닝 상태 조회."""
        return {
            "primary_last_run": (
                self._last_primary_screen.isoformat() if self._last_primary_screen else None
            ),
            "secondary_last_run": (
                self._last_secondary_screen.isoformat() if self._last_secondary_screen else None
            ),
            "secondary_interval": 30,
            "primary_screener_ready": self._primary_screener is not None,
            "realtime_screener_ready": self._realtime_screener is not None,
        }

    async def trigger_primary_screening(self) -> dict:
        """수동 1차 스크리닝 트리거."""
        if self._primary_screener is None:
            return {"candidates": 0, "passed": 0}
        return await self._primary_screen()

    async def trigger_secondary_screening(self) -> dict:
        """수동 2차 스크리닝 트리거."""
        if self._realtime_screener is None:
            return {"candidates": 0, "passed": 0}
        return await self._secondary_screen()

    async def trigger_etf_master(self) -> dict:
        """수동 ETF 마스터 갱신 트리거."""
        return await self._etf_master_collect()

    async def trigger_dart(self) -> dict:
        """수동 DART 재무 수집 트리거."""
        collected = await self._dart_collect()
        return {"financials_collected": collected}

    async def trigger_sentiment(self) -> dict:
        """수동 네이버 센티멘트 수집 트리거."""
        collected = await self._sentiment_collect()
        return {"sentiments_collected": collected}

    async def trigger_market_open(self) -> dict:
        """수동 market_open 트리거 (WS 연결 + 2차 스크리닝 활성화)."""
        await self._market_open()
        return {
            "ws_connected": self._ws_client.connected,
            "ws_subscriptions": self._ws_manager.count,
        }

    async def check_and_recover_market_open(self) -> bool:
        """서버 시작 시 장중 여부를 확인하고, 장중이면 _market_open을 자동 호출한다.

        Railway 재시작이 09:00~15:30 사이에 발생하면 market_open 스케줄 job이
        이미 지나쳐 WS 연결이 누락될 수 있다. lifespan에서 이 메서드를 호출하여 복구한다.
        """
        from datetime import time as dtime

        tz = ZoneInfo(settings.MARKET_TIMEZONE)
        now = datetime.now(tz)
        now_time = now.time()
        if dtime(9, 0) <= now_time < dtime(15, 30):
            logger.warning(
                "장중 재시작 감지 (%s) — market_open 자동 호출",
                now.strftime("%H:%M:%S"),
            )
            await self._market_open()
            return True
        return False

    async def trigger_market_open_recovery(self) -> dict:
        """수동 market_open_recovery 트리거."""
        await self._market_open_recovery()
        return {
            "ws_connected": self._ws_client.connected,
            "ws_subscriptions": self._ws_manager.count,
        }

    async def trigger_premarket(self) -> dict:
        """수동 장전 수집 트리거."""
        count = await self._premarket_collect()
        return {"stocks_collected": count}

    async def trigger_premarket_date(self, target_date: str) -> dict:
        """수동 장전 수집 트리거 (특정 날짜 지정, 공공데이터포털 사용).

        Args:
            target_date: YYYYMMDD 형식의 수집 대상 날짜
        """
        logger.info("수동 장전 수집 시작: target_date=%s", target_date)
        try:
            async with self._session_factory() as db_session:
                collector = DataGoKrCollector(db_session)
                result = await collector.collect_all(target_date=target_date)
            logger.info(
                "수동 장전 수집 완료: target_date=%s collected=%d",
                target_date, result.collected,
            )
            return {
                "target_date": target_date,
                "collected": result.collected,
                "data_date": result.data_date,
            }
        except Exception as e:
            logger.exception("수동 장전 수집 실패: target_date=%s reason=%s", target_date, e)
            return {"target_date": target_date, "error": str(e)}

    async def trigger_kis_daily(self, target_date: str) -> dict:
        """수동 KIS 일봉 수집 트리거 (특정 날짜 지정).

        Args:
            target_date: YYYYMMDD 형식의 수집 대상 날짜
        """
        logger.info("수동 KIS 일봉 수집 시작: target_date=%s", target_date)
        try:
            client = self._inquiry_client or self._rest_client
            async with self._session_factory() as db_session:
                from modules.collector.sources.kis_daily_collector import KISDailyCollector
                collector = KISDailyCollector(client, db_session)
                result = await collector.collect_all(target_date=target_date)
            logger.info(
                "수동 KIS 일봉 수집 완료: target_date=%s collected=%d failed=%d",
                target_date, result.collected, result.failed,
            )
            return {
                "target_date": target_date,
                "collected": result.collected,
                "failed": result.failed,
                "total_target": result.total_target,
            }
        except Exception as e:
            logger.exception("수동 KIS 일봉 수집 실패: target_date=%s reason=%s", target_date, e)
            return {"target_date": target_date, "error": str(e)}

    async def trigger_etf(self) -> dict:
        """수동 ETF 수집 트리거."""
        count = await self._etf_collect()
        return {"etfs_collected": count}

    # ── 스케줄 job ──────────────────────────────────────

    async def _premarket_collect(self) -> int:
        """08:00 공공데이터포털 전 종목 수집. 매 실행마다 독립 DB 세션 사용."""
        logger.info("수집 시작: step=premarket")
        # 매일 08:00 시작 시 파이프라인 상태 전체 초기화
        await asyncio.gather(
            self._redis.set(PIPELINE_HEALTHY_KEY, "false", ttl=STATE_TTL),
            self._redis.set(
                PIPELINE_STATUS_KEY,
                json.dumps({s: {"status": "pending"} for s in ALL_PIPELINE_STEPS}),
                ttl=STATE_TTL,
            ),
        )
        self._pipeline_status = {}
        try:
            async with self._session_factory() as db_session:
                collector = DataGoKrCollector(db_session)
                result = await collector.collect_all()
            validation = self._validator.validate_premarket(result)
            self._last_premarket = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            await self._save_last_timestamp("premarket", self._last_premarket)
            if validation.passed:
                await self._update_step_status("premarket", "success", collected_count=result.collected, validation=validation)
                # cross-check: 포털 수집 성공 시 KIS 종가와 괴리 검증 (비중단)
                if result.data_date:
                    try:
                        async with self._session_factory() as db_session:
                            await self._validator.cross_check_prices(db_session, result.data_date)
                    except Exception as e:
                        logger.warning("cross-check 오류 (비중단): %s", e)
            else:
                logger.warning("포털 수집 실패, KIS 보조 수집 전환: reason=%s", validation.failure_reason)
                kis_result = await self._run_kis_daily_fallback()
                kis_validation = self._validator.validate_kis_daily(kis_result)
                if kis_validation.passed:
                    await asyncio.gather(
                        self._update_step_status("premarket", "success", collected_count=kis_result.collected, validation=kis_validation),
                        self._send_fallback_info_alert("premarket", validation.failure_reason or "", kis_result.collected),
                    )
                    logger.info("KIS 보조 수집 성공: collected=%d", kis_result.collected)
                    logger.info(
                        "수집 완료: step=premarket collected=%d failed=%d total=%d validation=%s",
                        kis_result.collected, kis_result.failed, kis_result.total_target,
                        "PASS",
                    )
                    await self._run_db_validation("premarket", "validate_premarket_db")
                    return kis_result.collected
                else:
                    error_msg = f"이중 실패 — 포털: {validation.failure_reason}, KIS: {kis_validation.failure_reason}"
                    await asyncio.gather(
                        self._update_step_status("premarket", "failed", error=error_msg, collected_count=kis_result.collected, validation=kis_validation),
                        self._send_double_failure_alert("premarket", validation.failure_reason or "", kis_validation.failure_reason or ""),
                    )
                    logger.error("이중 실패: step=premarket %s", error_msg)
            logger.info(
                "수집 완료: step=premarket collected=%d failed=%d total=%d validation=%s",
                result.collected, result.failed, result.total_target,
                "PASS" if validation.passed else "FAIL",
            )
            await self._run_db_validation("premarket", "validate_premarket_db")
            return result.collected
        except Exception as e:
            logger.exception("수집 실패: step=premarket reason=%s", e)
            # 예외 경로에서도 KIS 폴백 시도
            try:
                logger.info("예외 경로 KIS 폴백 시도: step=premarket")
                kis_result = await self._run_kis_daily_fallback()
                kis_validation = self._validator.validate_kis_daily(kis_result)
                if kis_validation.passed:
                    await asyncio.gather(
                        self._update_step_status("premarket", "success", collected_count=kis_result.collected, validation=kis_validation),
                        self._send_fallback_info_alert("premarket", str(e), kis_result.collected),
                    )
                    logger.info("예외 경로 KIS 폴백 성공: collected=%d", kis_result.collected)
                    await self._run_db_validation("premarket", "validate_premarket_db")
                    return kis_result.collected
                else:
                    await self._update_step_status("premarket", "failed", error=str(e))
                    await self._send_double_failure_alert("premarket", str(e), kis_validation.failure_reason or "")
            except Exception as fallback_err:
                logger.exception("예외 경로 KIS 폴백도 실패: %s", fallback_err)
                await self._update_step_status("premarket", "failed", error=str(e))
                await self._send_failure_alert("premarket", str(e))
            return 0

    async def _run_kis_daily_fallback(self) -> CollectionResult:
        """포털 수집 실패 시 KIS 일봉 보조 수집 실행."""
        try:
            client = self._inquiry_client or self._rest_client
            async with self._session_factory() as db_session:
                daily_collector = KISDailyCollector(client, db_session)
                return await daily_collector.collect_all()
        except Exception as e:
            logger.exception("KIS 보조 수집 실패: %s", e)
            return CollectionResult(collected=0, failed=0, total_target=0)

    async def _send_recovery_info_alert(self, collected: int) -> None:
        """08:30 포털 재시도 성공 시 [복구] 알림 발송."""
        if self._telegram_bot is None:
            return
        msg = (
            f"<b>[복구]</b> 08:30 포털 재시도 성공\n"
            f"수집 건수: {collected}건"
        )
        await self._telegram_bot.send_notification(msg)

    async def _premarket_retry(self) -> None:
        """08:30 포털 재시도 — premarket이 실패 상태일 때만 포털 재수집을 시도한다.

        성공 시 pipeline_status를 포털 데이터 기준으로 success로 업데이트하고
        [복구] 태그 알림을 발송한다. 실패 시에는 KIS 보조 데이터가 이미 있으므로 경고 로그만 기록.
        """
        today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
        if not is_trading_day(today):
            logger.info("비거래일 스킵: step=premarket_retry date=%s", today)
            return
        pipeline_status = await self._get_pipeline_status()
        premarket_status = pipeline_status.get("premarket", {}).get("status")
        if premarket_status == "success":
            logger.info("포털 재시도 스킵: premarket 이미 성공 상태")
            return

        logger.info("포털 재시도 시작: step=premarket_retry (premarket.status=%s)", premarket_status)
        try:
            async with self._session_factory() as db_session:
                collector = DataGoKrCollector(db_session)
                result = await collector.collect_all()
            validation = self._validator.validate_premarket(result)
            if validation.passed:
                await asyncio.gather(
                    self._update_step_status("premarket", "success", collected_count=result.collected, validation=validation),
                    self._send_recovery_info_alert(result.collected),
                )
                logger.info("포털 재시도 성공: collected=%d", result.collected)
                await self._run_db_validation("premarket", "validate_premarket_db")
                # cross-check: 재시도 성공 시에도 KIS 종가와 괴리 검증 (비중단)
                if result.data_date:
                    try:
                        async with self._session_factory() as db_session:
                            await self._validator.cross_check_prices(db_session, result.data_date)
                    except Exception as e:
                        logger.warning("cross-check 오류 (비중단): %s", e)
                pipeline_status, existing_lock = await asyncio.gather(
                    self._get_pipeline_status(),
                    self._redis.get(PIPELINE_RUNNING_KEY),
                )
                screen_status = pipeline_status.get("primary_screen", {}).get("status")
                if screen_status in ("skipped", "failed"):
                    if existing_lock:
                        logger.warning("파이프라인 실행 중 -- 재시도 후 재실행 스킵")
                    else:
                        logger.info("포털 재시도 성공 -> 스크리닝 + 후속 단계 재실행")
                        try:
                            await self._primary_screen()
                            await self._dart_collect()
                            await self._sentiment_collect()
                        except Exception as e:
                            logger.exception("재시도 후 재실행 실패: %s", e)
            else:
                logger.warning(
                    "포털 재시도 실패 (KIS 보조 데이터 유지): reason=%s",
                    validation.failure_reason,
                )
        except Exception as e:
            logger.warning("포털 재시도 예외 발생 (KIS 보조 데이터 유지): %s", e)

    async def _etf_collect(self) -> int:
        """08:15 ETF 시세 수집. 매 실행마다 독립 DB 세션 사용."""
        if not await self._check_dependency("etf"):
            logger.warning("ETF 수집 스킵: etf_master 선행 실패")
            await self._update_step_status("etf", "skipped")
            return 0
        logger.info("수집 시작: step=etf")
        try:
            client = self._inquiry_client or self._rest_client
            async with self._session_factory() as db_session:
                collector = KISCollector(client, db_session)
                result = await collector.collect_etf_prices()
            logger.info("ETF 수집 대상: KODEX %d종목 (전체 ETF 대비)", result.total_target)
            validation = self._validator.validate_etf_collect(result)
            self._last_etf = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            await self._save_last_timestamp("etf", self._last_etf)
            if validation.passed:
                await self._update_step_status("etf", "success", collected_count=result.collected, validation=validation)
            else:
                await self._update_step_status("etf", "failed", error=validation.failure_reason, collected_count=result.collected, validation=validation)
                await self._send_failure_alert("etf", validation.failure_reason or "ETF 유효성 검증 실패")
                logger.error("수집 실패: step=etf reason=%s", validation.failure_reason)
            logger.info(
                "수집 완료: step=etf collected=%d failed=%d total=%d validation=%s",
                result.collected, result.failed, result.total_target,
                "PASS" if validation.passed else "FAIL",
            )
            await self._run_db_validation("etf", "validate_etf_db")
            return result.collected
        except Exception as e:
            logger.exception("수집 실패: step=etf reason=%s", e)
            await self._update_step_status("etf", "failed", error=str(e))
            return 0

    async def _etf_master_collect(self) -> dict:
        """08:10 KIS 마스터파일에서 ETF/ETN 종목 적재. 실패 시 기존 DB 유지."""
        logger.info("ETF 마스터 수집 시작")
        try:
            async with self._session_factory() as db_session:
                collector = KISMasterCollector(db_session)
                result = await collector.collect()

            if result["source"] == "seed":
                pass  # seed 폴백은 _etf_master_collect 내부가 아닌 최초 설치 스크립트에서 처리

            collection_result = CollectionResult(collected=result["etf_count"] + result["etn_count"])
            validation = self._validator.validate_etf_master(collection_result, sanity_passed=result.get("sanity_passed", False))
            self._last_etf_master = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            await self._save_last_timestamp("etf_master", self._last_etf_master)
            if validation.passed:
                await self._update_step_status("etf_master", "success", collected_count=collection_result.collected, validation=validation)
            else:
                await self._update_step_status("etf_master", "failed", error=validation.failure_reason, collected_count=collection_result.collected, validation=validation)
                await self._send_failure_alert("etf_master", validation.failure_reason or "ETF 마스터 유효성 검증 실패")
            logger.info(
                "ETF 마스터 수집 완료: ETF=%d, ETN=%d, source=%s",
                result["etf_count"], result["etn_count"], result["source"],
            )
            return result
        except Exception as e:
            logger.exception("ETF 마스터 수집 실패")
            await self._update_step_status("etf_master", "failed", error=str(e))
            await self._send_failure_alert("etf_master", str(e))
            return {"etf_count": 0, "etn_count": 0, "source": "error", "sanity_passed": False}

    async def _on_ws_reconnect_failure(self) -> None:
        """WS 재연결 7회 실패 시 긴급 알림."""
        logger.error("WS 재연결 최대 실패 -- 장중 실시간 파이프라인 중단")
        await self._send_failure_alert("ws_reconnect", "WebSocket 재연결 7회 실패. 장중 2차 스크리닝 중단 상태.")

    async def _on_ws_reconnect_success(self) -> None:
        """WS 재연결 성공 시 체결강도 웜업 설정."""
        self._trade_strength.set_warmup_all(5.0)
        logger.info("WS 재연결 성공: 체결강도 5초 웜업 설정")

    async def _reconnect_ws(self) -> None:
        """WS 연결 끊고 재연결 + 구독 복원. 구독 실패(ALREADY IN USE 등) 자동 복구용."""
        logger.warning("WS 재연결 시작 (구독 데이터 부재 감지)")
        try:
            self._ws_manager._subscriptions.clear()
            await self._ws_client.disconnect()
            # KIS가 이전 세션을 정리할 시간 부여
            await asyncio.sleep(3)
            self._ws_client.set_on_data(self._on_realtime_data)
            self._ws_client.set_on_ws_failure(self._on_ws_reconnect_failure)
            self._ws_client.set_on_reconnect_success(self._on_ws_reconnect_success)
            await self._ws_client.connect()
            async with self._session_factory() as db_session:
                codes = await self._get_latest_primary_codes(db_session)
            if codes:
                for code in codes:
                    await self._ws_manager.subscribe(code)
                logger.info("WS 재구독 완료: %d종목", len(codes))
            if self._telegram_bot:
                await self._telegram_bot.send_notification(
                    "<b>[자동 복구]</b> WS 재연결 + 재구독 완료 (%d종목)" % (len(codes) if codes else 0)
                )
        except Exception:
            logger.exception("WS 재연결 실패")
            await self._send_failure_alert("ws_reconnect_auto", "WS 자동 재연결 실패")

    async def _market_open(self) -> None:
        """09:00 WS 연결 + 구독 시작 + 2차 스크리닝 활성화."""
        today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
        if not is_trading_day(today):
            logger.info("비거래일 스킵: step=market_open date=%s", today)
            return
        logger.info("장중 시작: WS 연결")
        try:
            self._ws_client.set_on_data(self._on_realtime_data)
            self._ws_client.set_on_ws_failure(self._on_ws_reconnect_failure)
            self._ws_client.set_on_reconnect_success(self._on_ws_reconnect_success)
            # 기존 ws_manager 구독 목록 초기화 (재연결 시 중복 방지)
            self._ws_manager._subscriptions.clear()
            await self._ws_client.connect()
            # DB에서 최신 1차 스크리닝 결과 읽어 WS 구독
            async with self._session_factory() as db_session:
                codes = await self._get_latest_primary_codes(db_session)
            if codes:
                for code in codes:
                    await self._ws_manager.subscribe(code)
                logger.info("WS 구독: %d종목", len(codes))
            # 2차 스크리닝 30초 주기 활성화
            job = self._scheduler.get_job("secondary_screen")
            if job:
                job.resume()
                logger.info("2차 스크리닝 30초 주기 활성화")
            logger.info("WS 연결 완료, 구독 %d개", self._ws_manager.count)
        except Exception as e:
            logger.exception("WS 연결 실패")
            await self._send_failure_alert("market_open", str(e))

    async def _market_open_recovery(self) -> None:
        """09:05/09:10/09:15 WS 연결 상태 확인 — 미연결 시 단계적 재시도 (최대 3회, 5분 간격)."""
        today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
        if not is_trading_day(today):
            logger.info("비거래일 스킵: step=market_open_recovery date=%s", today)
            return
        if self._ws_client.connected:
            logger.info("market_open 복구 불필요: ws_connected=True, subscriptions=%d", self._ws_manager.count)
            return

        max_attempts = 3
        retry_interval = 300  # 5분
        for attempt in range(1, max_attempts + 1):
            logger.warning("market_open 복구 시도 %d/%d: ws_connected=False (subscriptions=%d)", attempt, max_attempts, self._ws_manager.count)
            if self._telegram_bot:
                await self._telegram_bot.send_notification(
                    f"<b>[장애 복구]</b> market_open 미실행 감지 ({attempt}/{max_attempts})\n"
                    "ws_connected=False → 자동 재시도 중..."
                )
            await self._market_open()

            if self._ws_client.connected:
                subs = self._ws_manager.count
                if self._telegram_bot:
                    await self._telegram_bot.send_notification(
                        f"<b>[장애 복구]</b> 복구 성공 ({attempt}/{max_attempts})\nws_connected=True, subscriptions={subs}"
                    )
                return

            if attempt < max_attempts:
                logger.info("market_open 복구 대기: %d초 후 재시도", retry_interval)
                await asyncio.sleep(retry_interval)

        # 3회 모두 실패
        logger.error("market_open 복구 최종 실패: %d회 시도 모두 실패", max_attempts)
        if self._telegram_bot:
            await self._telegram_bot.send_notification(
                f"<b>[긴급]</b> market_open 복구 최종 실패\n"
                f"{max_attempts}회 시도 모두 실패 — 장중 실시간 파이프라인 마비 상태\n"
                "수동 확인 필요"
            )

    async def _market_close(self) -> None:
        """15:30 WS 구독 해제 + 연결 종료 + 2차 스크리닝 중지."""
        today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
        if not is_trading_day(today):
            logger.info("비거래일 스킵: step=market_close date=%s", today)
            return
        logger.info("장후 시작: WS 종료")
        try:
            # 2차 스크리닝 일시 정지
            job = self._scheduler.get_job("secondary_screen")
            if job:
                job.pause()
                logger.info("2차 스크리닝 중지")
            await self._ws_manager.unsubscribe_all()
            await self._ws_client.disconnect()
            logger.info("WS 종료 완료")
        except Exception:
            logger.exception("WS 종료 실패")

        # 일일 마감 리포트 발송
        if self._notifier_manager is not None:
            try:
                await self._notifier_manager.send_daily_report(self._session_factory)
                logger.info("일일 마감 리포트 발송 완료")
            except Exception:
                logger.exception("일일 마감 리포트 발송 실패")

    # ── 스크리닝 job ─────────────────────────────────────

    async def _primary_screen(self) -> dict:
        """08:10 1차 스크리닝: DB 정적 필터 + 팩터 스코어링."""
        if not await self._check_dependency("primary_screen"):
            # pipeline_status 실패 시 DB 데이터 충분성 폴백 체크
            try:
                async with self._session_factory() as db_session:
                    readiness = await self._validator.validate_screening_readiness(db_session)
                if readiness.passed:
                    logger.warning(
                        "premarket 실패지만 DB 데이터 충분 -- 스크리닝 진행 (DB 폴백): %s",
                        readiness.details,
                    )
                    if readiness.severity == "warning":
                        await self._send_stale_data_alert(readiness.details)
                else:
                    logger.warning(
                        "1차 스크리닝 스킵: premarket 실패 + DB 데이터 부족 (%s)",
                        readiness.failure_reason,
                    )
                    await self._update_step_status(
                        "primary_screen", "skipped", error=readiness.failure_reason
                    )
                    return {"skipped": True, "candidates": 0, "passed": 0}
            except Exception as e:
                logger.warning("DB 충분성 검증 실패 -- 스크리닝 스킵: %s", e)
                await self._update_step_status("primary_screen", "skipped")
                return {"skipped": True, "candidates": 0, "passed": 0}
        logger.info("1차 스크리닝 시작")
        try:
            async with self._session_factory() as db_session:
                results = await self._primary_screener.screen(db_session)
                saved = await self._primary_screener.save_results(db_session, results)
                await db_session.commit()

            # 1차 결과로 WS 구독 목록 업데이트
            for item in results:
                await self._ws_manager.subscribe(
                    item["stock_code"],
                    priority=float(item.get("score", 0)),
                )

            passed = [r for r in results if r.get("is_passed")]
            collection_result = CollectionResult(collected=len(passed))
            validation = self._validator.validate_primary_screen(collection_result)
            self._last_primary_screen = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            await self._save_last_timestamp("primary_screen", self._last_primary_screen)
            await self._update_step_status("primary_screen", "success", collected_count=len(passed), validation=validation)
            logger.info("1차 스크리닝 완료: %d후보, %d통과", len(results), len(passed))
            return {"candidates": len(results), "passed": len(passed)}
        except Exception as e:
            logger.exception("1차 스크리닝 실패")
            await self._update_step_status("primary_screen", "failed", error=str(e))
            await self._send_failure_alert("primary_screen", str(e))
            return {"candidates": 0, "passed": 0, "error": str(e)}

    async def _secondary_screen(self) -> dict:
        """장중 30초 주기 2차 스크리닝: 실시간 필터 + 팩터 스코어링."""
        if not self._ws_client.connected:
            self._secondary_skip_count += 1
            logger.warning("2차 스크리닝 스킵: WS 미연결 (연속 %d회)", self._secondary_skip_count)
            # 3회 첫 경고, 이후 10회마다 재발송 (30초 주기 기준 스팸 방지)
            n = self._secondary_skip_count
            if (n == 3 or n % 10 == 0) and self._telegram_bot:
                await self._telegram_bot.send_notification(
                    "<b>[경고]</b> 2차 스크리닝 연속 %d회 스킵\nWS 미연결 상태 지속" % n
                )
            return {"candidates": 0, "passed": 0, "skipped": True, "reason": "ws_disconnected"}

        logger.info("2차 스크리닝 시작")
        try:
            async with self._session_factory() as db_session:
                candidate_codes = await self._get_latest_primary_codes(db_session)

                if not candidate_codes:
                    return {"candidates": 0, "passed": 0}

                results = await self._realtime_screener.screen(candidate_codes, db_session)

            passed = [r for r in results if r.get("is_passed")]
            self._last_secondary_screen = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            self._secondary_skip_count = 0

            # 구독된 종목 중 실제로 Redis에 데이터가 있는지 직접 확인 (필터 탈락과 구분)
            subscribed_codes = self._ws_manager.get_subscribed_stocks()
            data_count = 0
            sample_codes = subscribed_codes[:10]  # 상위 10개만 샘플링
            for code in sample_codes:
                exec_raw = await self._redis.get(f"realtime:{code}:execution")
                ob_raw = await self._redis.get(f"realtime:{code}:orderbook")
                if exec_raw is not None and ob_raw is not None:
                    data_count += 1

            # 구독 종목이 있는데 샘플 10개 중 데이터가 0건이면 구독 실패 의심
            if len(subscribed_codes) > 0 and data_count == 0:
                self._secondary_no_data_count += 1
                logger.warning(
                    "실시간 데이터 부재: 구독 %d종목 샘플 %d개 중 데이터 0건 (연속 %d회)",
                    len(subscribed_codes), len(sample_codes), self._secondary_no_data_count,
                )
                if self._secondary_no_data_count >= 5:
                    logger.error("실시간 데이터 5회 연속 부재 — WS 재연결 시도")
                    self._secondary_no_data_count = 0
                    await self._reconnect_ws()
            else:
                self._secondary_no_data_count = 0

            logger.info(
                "2차 스크리닝 완료: %d후보, 구독 %d종목(데이터 %d/%d), %d통과",
                len(candidate_codes), len(subscribed_codes), data_count, len(sample_codes), len(passed),
            )

            # 통과 종목을 매매 엔진에 전달
            if passed and self._trading_engine:
                await self._trading_engine.process_screening_results(passed)

            return {"candidates": len(candidate_codes), "passed": len(passed)}
        except Exception:
            logger.exception("2차 스크리닝 실패")
            return {"candidates": 0, "passed": 0}

    async def _dart_collect(self) -> int:
        """08:15 DART 재무 데이터 수집 — 1차 스크리닝 통과 종목 대상."""
        if not await self._check_dependency("dart"):
            logger.warning("DART 수집 스킵: primary_screen 선행 실패")
            await self._update_step_status("dart", "skipped")
            return 0
        logger.info("수집 시작: step=dart")
        try:
            from modules.collector.sources.dart import DartCollector

            async with self._session_factory() as db_session:
                stock_codes = await self._get_latest_primary_codes(db_session)

                if not stock_codes:
                    logger.info("DART 재무 수집 대상 없음")
                    result = CollectionResult(collected=0, total_target=0)
                    validation = self._validator.validate_dart(result)
                    await self._update_step_status("dart", "success", collected_count=0, validation=validation)
                    return 0

                collector = DartCollector(db_session)
                result = await collector.collect_financials(stock_codes)

            validation = self._validator.validate_dart(result)
            self._last_dart = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            await self._save_last_timestamp("dart", self._last_dart)
            status = "success" if validation.passed else "failed"
            await self._update_step_status("dart", status, collected_count=result.collected, validation=validation, error=validation.failure_reason if not validation.passed else None)
            if not validation.passed:
                logger.error("수집 실패: step=dart reason=%s", validation.failure_reason)
            logger.info(
                "수집 완료: step=dart collected=%d failed=%d total=%d validation=%s",
                result.collected, result.failed, result.total_target,
                "PASS" if validation.passed else "FAIL",
            )
            return result.collected
        except Exception as e:
            logger.exception("수집 실패: step=dart reason=%s", e)
            await self._update_step_status("dart", "failed", error=str(e))
            return 0

    async def _sentiment_collect(self) -> int:
        """08:20 네이버 뉴스 센티멘트 수집 — 1차 스크리닝 통과 종목 대상."""
        if not await self._check_dependency("sentiment"):
            logger.warning("센티멘트 수집 스킵: primary_screen 선행 실패")
            await self._update_step_status("sentiment", "skipped")
            return 0
        logger.info("수집 시작: step=sentiment")
        try:
            from modules.collector.sources.naver import NaverCollector

            async with self._session_factory() as db_session:
                stock_info = await self._get_latest_primary_stock_info(db_session)

                if not stock_info:
                    logger.info("네이버 센티멘트 수집 대상 없음")
                    result = CollectionResult(collected=0, total_target=0)
                    validation = self._validator.validate_sentiment(result)
                    await self._update_step_status("sentiment", "success", collected_count=0, validation=validation)
                    return 0

                collector = NaverCollector(db_session)
                result = await collector.collect_sentiments(stock_info)

            validation = self._validator.validate_sentiment(result)
            self._last_sentiment = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            await self._save_last_timestamp("sentiment", self._last_sentiment)
            status = "success" if validation.passed else "failed"
            await self._update_step_status("sentiment", status, collected_count=result.collected, validation=validation, error=validation.failure_reason if not validation.passed else None)
            if not validation.passed:
                logger.error("수집 실패: step=sentiment reason=%s", validation.failure_reason)
            logger.info(
                "수집 완료: step=sentiment collected=%d failed=%d total=%d validation=%s",
                result.collected, result.failed, result.total_target,
                "PASS" if validation.passed else "FAIL",
            )
            return result.collected
        except Exception as e:
            logger.exception("수집 실패: step=sentiment reason=%s", e)
            await self._update_step_status("sentiment", "failed", error=str(e))
            return 0

    # ── 내부 헬퍼 ────────────────────────────────────────

    async def _get_latest_primary_codes(self, db_session: AsyncSession) -> list[str]:
        """최신 1차 스크리닝 통과 종목 코드 목록을 rank 오름차순으로 반환한다 (단일 쿼리)."""
        latest_subq = (
            select(func.max(ScreeningResult.screened_at))
            .where(ScreeningResult.screening_type == "primary")
            .scalar_subquery()
        )
        stmt = (
            select(ScreeningResult.stock_code)
            .where(
                ScreeningResult.screening_type == "primary",
                ScreeningResult.screened_at == latest_subq,
            )
            .order_by(ScreeningResult.rank.asc().nulls_last())
        )
        result = await db_session.execute(stmt)
        return [row[0] for row in result.all()]

    async def _get_latest_primary_stock_info(self, db_session: AsyncSession) -> list[dict]:
        """최신 1차 스크리닝 통과 종목의 코드+종목명을 반환한다 (단일 쿼리)."""
        latest_subq = (
            select(func.max(ScreeningResult.screened_at))
            .where(ScreeningResult.screening_type == "primary")
            .scalar_subquery()
        )
        stmt = (
            select(ScreeningResult.stock_code, Stock.stock_name)
            .join(Stock, Stock.stock_code == ScreeningResult.stock_code)
            .where(
                ScreeningResult.screening_type == "primary",
                ScreeningResult.screened_at == latest_subq,
            )
        )
        result = await db_session.execute(stmt)
        return [{"stock_code": row[0], "stock_name": row[1]} for row in result.all()]

    # ── WS 수신 콜백 ───────────────────────────────────

    def _on_realtime_data(self, tr_id: str, raw_data: str) -> None:
        """WS 수신 콜백 — 파서 -> Redis 캐싱 -> 체결강도."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._process_realtime_data(tr_id, raw_data))
        except RuntimeError:
            pass

    async def _process_realtime_data(self, tr_id: str, raw_data: str) -> None:
        """실시간 데이터 처리."""
        parsed = parse_raw_message(raw_data)
        if parsed is None:
            return

        msg_tr_id, _encrypted, body = parsed

        if msg_tr_id == "H0STCNT0":
            execution = parse_execution(body)
            if execution:
                # Redis 캐싱
                await self._redis.set(
                    f"realtime:{execution.stock_code}:execution",
                    json.dumps({
                        "stock_code": execution.stock_code,
                        "time": execution.time,
                        "price": execution.price,
                        "volume": execution.volume,
                        "acml_volume": execution.acml_volume,
                        "change_rate": execution.change_rate,
                        "sell_or_buy": execution.sell_or_buy,
                    }),
                    ttl=REALTIME_CACHE_TTL,
                )
                # 체결강도 업데이트
                import time
                self._trade_strength.add_execution(
                    execution.stock_code,
                    time.time(),
                    execution.volume,
                    execution.sell_or_buy,
                )

        elif msg_tr_id == "H0STASP0":
            orderbook = parse_orderbook(body)
            if orderbook:
                await self._redis.set(
                    f"realtime:{orderbook.stock_code}:orderbook",
                    json.dumps({
                        "stock_code": orderbook.stock_code,
                        "time": orderbook.time,
                        "total_ask_volume": orderbook.total_ask_volume,
                        "total_bid_volume": orderbook.total_bid_volume,
                        "ask_count": len(orderbook.asks),
                        "bid_count": len(orderbook.bids),
                    }),
                    ttl=REALTIME_CACHE_TTL,
                )
