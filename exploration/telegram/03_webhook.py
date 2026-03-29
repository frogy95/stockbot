"""텔레그램 웹훅 수신 테스트.

사전 조건: 별도 터미널에서 ngrok 실행
  ngrok http 5000

실행:
  python exploration/telegram/03_webhook.py --ngrok-url https://xxxx.ngrok-free.app
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from exploration.common.config import TELEGRAM_BOT_TOKEN


class WebhookHandler(BaseHTTPRequestHandler):
    """간단한 웹훅 수신 핸들러."""

    received_count = 0

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body)

        WebhookHandler.received_count += 1
        print(f"\n[웹훅 #{WebhookHandler.received_count}] 수신:")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:500])

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # 기본 로그 비활성화


def set_webhook(ngrok_url: str) -> bool:
    """텔레그램 웹훅 설정."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    webhook_url = f"{ngrok_url}/webhook"
    resp = requests.post(url, json={"url": webhook_url})
    data = resp.json()
    print(f"[setWebhook] {data}")
    return data.get("ok", False)


def delete_webhook() -> bool:
    """텔레그램 웹훅 삭제."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
    resp = requests.post(url)
    data = resp.json()
    print(f"[deleteWebhook] {data}")
    return data.get("ok", False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ngrok-url", required=True, help="ngrok HTTPS URL (예: https://xxxx.ngrok-free.app)")
    parser.add_argument("--port", type=int, default=5000, help="로컬 서버 포트")
    args = parser.parse_args()

    # 웹훅 등록
    if not set_webhook(args.ngrok_url):
        print("[실패] 웹훅 설정 실패")
        sys.exit(1)

    # 로컬 서버 시작
    print(f"\n로컬 서버 시작 (포트 {args.port})...")
    print("텔레그램에서 봇에게 메시지를 보내세요. Ctrl+C로 종료.")
    server = HTTPServer(("0.0.0.0", args.port), WebhookHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n\n수신 건수: {WebhookHandler.received_count}")
    finally:
        # 웹훅 삭제
        delete_webhook()
        server.server_close()


if __name__ == "__main__":
    main()
