"""DART corp_code ZIP 다운로드 → XML 파싱 → DB 저장 스크립트.

실행 방법:
    docker compose exec backend python scripts/load_corp_codes.py
"""

import asyncio
import zipfile
import io
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from modules.collector.sources.dart import DartCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        collector = DartCollector(session)

        logger.info("DART corp_code ZIP 다운로드 중...")
        zip_bytes = await collector.fetch_corp_code_zip()

        # ZIP에서 XML 추출
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xml_name = next(
                (name for name in zf.namelist() if name.lower().endswith(".xml")),
                None,
            )
            if xml_name is None:
                logger.error("ZIP 내 XML 파일을 찾을 수 없습니다.")
                return
            xml_bytes = zf.read(xml_name)

        logger.info("XML 파싱 중...")
        records = collector.parse_corp_code_xml(xml_bytes)
        logger.info("파싱된 기업 수: %d", len(records))

        logger.info("DB 저장 중...")
        saved = await collector.save_corp_codes(records)
        print(f"corp_code 저장 완료: {saved}건")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
