"""KIS WebSocket 연결 진단 — Railway 아웃바운드 IP + HTTP 핸드셰이크 응답 확인

표준 라이브러리만 사용. railway run으로 실행:
  railway run python3 backend/scripts/diagnose_ws.py
"""

import socket
import time
import urllib.request


HOST = "ops.koreainvestment.com"
TESTS = [
    ("PAPER", 31000, "/"),
    ("LIVE",  21000, "/"),
    ("LIVE+path", 21000, "/tryitout"),
]

WS_UPGRADE = (
    "GET {path} HTTP/1.1\r\n"
    "Host: {host}:{port}\r\n"
    "Upgrade: websocket\r\n"
    "Connection: Upgrade\r\n"
    "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
    "Sec-WebSocket-Version: 13\r\n"
    "\r\n"
)


def get_outbound_ip() -> str:
    try:
        with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=5) as r:
            return r.read().decode().strip()
    except Exception as e:
        return f"확인 실패: {e}"


def tcp_test(host: str, port: int, timeout: float = 5.0) -> tuple[bool, float]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        result = s.connect_ex((host, port))
        elapsed = time.time() - t0
        return result == 0, elapsed
    except OSError as e:
        return False, time.time() - t0
    finally:
        s.close()


def http_handshake_test(host: str, port: int, path: str, timeout: float = 10.0) -> tuple[str, float]:
    """Raw HTTP Upgrade 요청 전송 → 첫 줄(HTTP status line) 읽기."""
    request = WS_UPGRADE.format(host=host, port=port, path=path).encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.connect((host, port))
        s.sendall(request)
        # 첫 응답 읽기 (최대 1024 bytes)
        s.settimeout(5.0)
        response = b""
        try:
            chunk = s.recv(1024)
            response = chunk
        except socket.timeout:
            pass
        elapsed = time.time() - t0
        if not response:
            return f"EOF (0 bytes, {elapsed:.2f}s — 서버가 응답 없이 연결 종료)", elapsed
        first_line = response.split(b"\r\n")[0].decode(errors="replace")
        return f"{first_line} ({len(response)} bytes, {elapsed:.2f}s)", elapsed
    except ConnectionRefusedError:
        return f"ConnectionRefused ({time.time()-t0:.2f}s)", time.time() - t0
    except socket.timeout:
        return f"Timeout ({time.time()-t0:.2f}s)", time.time() - t0
    except OSError as e:
        return f"OSError: {e} ({time.time()-t0:.2f}s)", time.time() - t0
    finally:
        s.close()


def main():
    print("=" * 60)
    print("KIS WebSocket 연결 진단")
    print("=" * 60)

    # 1. Railway 아웃바운드 IP
    ip = get_outbound_ip()
    print(f"\n[1] Railway 아웃바운드 IP: {ip}")
    print("    → 이 IP를 KIS 개발자 포털에 등록했는지 확인하세요.")

    # 2. TCP 연결 테스트
    print(f"\n[2] TCP 연결 테스트 (host={HOST})")
    for label, port, _ in TESTS[:2]:  # PAPER / LIVE 만
        ok, elapsed = tcp_test(HOST, port)
        status = "OPEN ✅" if ok else "CLOSED ❌"
        print(f"    port {port} ({label:8}): {status} ({elapsed:.2f}s)")

    # 3. HTTP 핸드셰이크 테스트 (핵심 판별)
    print(f"\n[3] HTTP WebSocket 핸드셰이크 테스트")
    results = {}
    for label, port, path in TESTS:
        resp, elapsed = http_handshake_test(HOST, port, path)
        print(f"    port {port} {label:12}: {resp}")
        results[label] = resp

    # 4. 진단 결론
    print(f"\n{'=' * 60}")
    print("진단 결론")
    print("=" * 60)

    live_resp = results.get("LIVE", "")
    paper_resp = results.get("PAPER", "")
    live_path_resp = results.get("LIVE+path", "")

    if "101" in paper_resp and ("EOF" in live_resp or "0 bytes" in live_resp):
        print("→ 원인 A: KIS LIVE WS IP 화이트리스트 차단")
        print(f"  Paper(31000): 정상 연결 (101)")
        print(f"  LIVE(21000):  즉시 EOF — Railway IP({ip})가 미등록")
        print()
        print("  조치:")
        print(f"  1. Railway 대시보드 > Settings > Networking > Static Outbound IP 활성화")
        print(f"  2. 할당된 고정 IP를 KIS 개발자 포털 > 실전 API > IP 관리에 등록")

    elif "101" in live_resp:
        print("→ 원인 C 또는 정상: LIVE WS 연결 자체는 성공 (101)")
        print("  websockets 라이브러리 또는 approval_key 문제를 확인하세요.")

    elif "101" in live_path_resp and ("EOF" in live_resp or "0 bytes" in live_resp):
        print("→ 원인 B: LIVE WS URL 경로 필요")
        print(f"  path 없음: EOF, path 있음: 101")
        print("  kis_config.py LIVE ws_url에 경로 추가 필요")

    else:
        print(f"→ 추가 분석 필요")
        print(f"  PAPER: {paper_resp}")
        print(f"  LIVE:  {live_resp}")
        print(f"  LIVE+path: {live_path_resp}")


if __name__ == "__main__":
    main()
