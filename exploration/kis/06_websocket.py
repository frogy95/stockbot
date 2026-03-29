"""한투 모의거래 웹소켓 검증 — 실시간 시세 수신, 30분 유지, 재연결.

⚠️  장중(09:00~15:30) 테스트 필수!
장외 시간에는 실시간 데이터가 수신되지 않을 수 있음.

실행: python exploration/kis/06_websocket.py [--duration 1800]
  --duration: 수신 유지 시간(초), 기본 1800(30분)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
import asyncio
import json
import time
from datetime import datetime

import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64

from exploration.common.config import KIS_MOCK_BASE_URL, KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, TEST_STOCKS

# 모의거래 웹소켓 URL
WS_URL = "ws://ops.koreainvestment.com:31000"


def get_approval_key() -> str:
    """웹소켓 접속을 위한 approval_key 발급."""
    import requests
    url = f"{KIS_MOCK_BASE_URL}/oauth2/Approval"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_MOCK_APP_KEY,
        "secretkey": KIS_MOCK_APP_SECRET,
    }
    resp = requests.post(url, json=body)
    data = resp.json()
    key = data.get("approval_key", "")
    if key:
        print(f"[성공] approval_key: {key[:20]}...")
    else:
        print(f"[실패] approval_key 발급 실패: {data}")
    return key


def build_subscribe_msg(approval_key: str, tr_id: str, tr_key: str) -> str:
    """구독 메시지 생성."""
    return json.dumps({
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1",  # 1=등록
            "content-type": "utf-8",
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": tr_key,
            }
        }
    })


def try_decrypt(data: str, iv: str, key: str) -> str:
    """AES-256-CBC 복호화 시도."""
    try:
        cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
        decrypted = unpad(cipher.decrypt(base64.b64decode(data)), AES.block_size)
        return decrypted.decode("utf-8")
    except Exception:
        return data  # 암호화되지 않은 데이터


def parse_realtime_data(raw: str) -> dict:
    """실시간 체결 데이터 파싱 (파이프 구분자)."""
    fields = raw.split("|")
    if len(fields) < 4:
        return {"raw": raw}

    encrypted = fields[0]  # 0: 암호화 여부
    tr_id = fields[1]      # 1: tr_id
    count = fields[2]      # 2: 데이터 건수
    body = fields[3]       # 3: 데이터 본문

    # 본문은 ^로 구분된 필드
    items = body.split("^")
    result = {
        "encrypted": encrypted,
        "tr_id": tr_id,
        "count": count,
    }
    if len(items) >= 4:
        result["stock_code"] = items[0] if len(items) > 0 else "?"
        result["price"] = items[2] if len(items) > 2 else "?"
        result["volume"] = items[12] if len(items) > 12 else "?"
        result["time"] = items[1] if len(items) > 1 else "?"
    return result


async def run_websocket(approval_key: str, duration: int):
    """웹소켓 연결 + 실시간 수신 + 통계."""
    stats = {
        "total_messages": 0,
        "per_stock": {},
        "delays": [],
        "disconnects": 0,
        "start_time": time.time(),
    }

    for info in TEST_STOCKS.values():
        stats["per_stock"][info["code"]] = 0

    print(f"\n{'='*60}")
    print(f"웹소켓 연결 시작 (목표: {duration}초)")
    print(f"구독 종목: {', '.join(f'{v['name']}({v['code']})' for v in TEST_STOCKS.values())}")
    print(f"{'='*60}\n")

    try:
        async with websockets.connect(WS_URL, ping_interval=30) as ws:
            # 3종목 구독
            for info in TEST_STOCKS.values():
                msg = build_subscribe_msg(approval_key, "H0STCNT0", info["code"])
                await ws.send(msg)
                print(f"  구독 요청: {info['name']} ({info['code']})")
                await asyncio.sleep(0.5)

            # 데이터 수신
            last_report = time.time()
            end_time = time.time() + duration

            while time.time() < end_time:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                except asyncio.TimeoutError:
                    print(f"  [{datetime.now().strftime('%H:%M:%S')}] 10초간 데이터 없음")
                    continue

                # JSON 응답 (구독 확인 등)
                if raw.startswith("{"):
                    data = json.loads(raw)
                    print(f"  [서버] {data.get('header', {}).get('tr_id', '?')}: "
                          f"{data.get('body', {}).get('msg1', json.dumps(data.get('body', {}), ensure_ascii=False)[:80])}")
                    continue

                # 실시간 데이터 (파이프 구분)
                parsed = parse_realtime_data(raw)
                stats["total_messages"] += 1
                stock_code = parsed.get("stock_code", "?")
                if stock_code in stats["per_stock"]:
                    stats["per_stock"][stock_code] += 1

                # 지연 측정
                recv_time = datetime.now()
                api_time_str = parsed.get("time", "")
                if len(api_time_str) >= 6:
                    try:
                        h, m, s = int(api_time_str[:2]), int(api_time_str[2:4]), int(api_time_str[4:6])
                        api_time = recv_time.replace(hour=h, minute=m, second=s)
                        delay = (recv_time - api_time).total_seconds()
                        if 0 <= delay < 60:
                            stats["delays"].append(delay)
                    except (ValueError, IndexError):
                        pass

                # 1분마다 보고
                if time.time() - last_report >= 60:
                    elapsed = int(time.time() - stats["start_time"])
                    avg_delay = sum(stats["delays"]) / len(stats["delays"]) if stats["delays"] else 0
                    max_delay = max(stats["delays"]) if stats["delays"] else 0
                    print(f"\n  [{elapsed//60}분] 총 {stats['total_messages']}건 | "
                          f"평균지연: {avg_delay:.3f}s | 최대지연: {max_delay:.3f}s")
                    for code, cnt in stats["per_stock"].items():
                        print(f"    {code}: {cnt}건")
                    last_report = time.time()

    except websockets.exceptions.ConnectionClosed as e:
        stats["disconnects"] += 1
        print(f"\n  [끊김] 연결 종료: {e}")
    except Exception as e:
        print(f"\n  [에러] {type(e).__name__}: {e}")

    # 최종 통계
    elapsed = int(time.time() - stats["start_time"])
    avg_delay = sum(stats["delays"]) / len(stats["delays"]) if stats["delays"] else 0
    max_delay = max(stats["delays"]) if stats["delays"] else 0

    print(f"\n{'='*60}")
    print("웹소켓 테스트 결과")
    print(f"{'='*60}")
    print(f"  연결 시간: {elapsed}초 ({elapsed//60}분 {elapsed%60}초)")
    print(f"  총 수신: {stats['total_messages']}건")
    print(f"  종목별 수신:")
    for code, cnt in stats["per_stock"].items():
        print(f"    {code}: {cnt}건")
    print(f"  평균 지연: {avg_delay:.3f}초")
    print(f"  최대 지연: {max_delay:.3f}초")
    print(f"  끊김 횟수: {stats['disconnects']}")
    print(f"  지연 < 1초: {'예' if max_delay < 1 else '아니오'}")


async def test_reconnect(approval_key: str):
    """끊김 후 재연결 테스트."""
    print(f"\n{'='*60}")
    print("재연결 테스트")
    print(f"{'='*60}")

    # 첫 연결
    try:
        ws = await websockets.connect(WS_URL, ping_interval=30)
        msg = build_subscribe_msg(approval_key, "H0STCNT0", "005930")
        await ws.send(msg)
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        print(f"  1차 연결 성공: {resp[:80]}...")

        # 강제 종료
        await ws.close()
        print("  연결 강제 종료")

        # 재연결
        start = time.time()
        ws2 = await websockets.connect(WS_URL, ping_interval=30)
        reconnect_time = time.time() - start
        print(f"  재연결 소요: {reconnect_time:.3f}초")

        # 재구독
        await ws2.send(msg)
        resp2 = await asyncio.wait_for(ws2.recv(), timeout=5)
        print(f"  재구독 응답: {resp2[:80]}...")
        print("  → 재연결 후 재구독 필요: 예")

        await ws2.close()
    except Exception as e:
        print(f"  [에러] {type(e).__name__}: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=1800, help="수신 유지 시간(초)")
    parser.add_argument("--reconnect-only", action="store_true", help="재연결 테스트만 실행")
    args = parser.parse_args()

    approval_key = get_approval_key()
    if not approval_key:
        sys.exit(1)

    if args.reconnect_only:
        asyncio.run(test_reconnect(approval_key))
    else:
        asyncio.run(run_websocket(approval_key, args.duration))
        asyncio.run(test_reconnect(approval_key))


if __name__ == "__main__":
    main()
