"""LIVE 초기 파라미터 적용 — Phase 7.0 확정 파라미터 #15~#22"""

import os
import psycopg2

# Phase 7.0 LIVE 초기 파라미터 (최리스크 + 김단타 공동 확정)
LIVE_INITIAL_PARAMS = [
    ("max_position_count", "2"),        # Paper: 5 → LIVE 초기: 2
    ("position_size_pct", "5.0"),       # Paper: 10% → LIVE 초기: 5%
    ("daily_max_loss_pct", "-2.0"),     # Paper: -3% → LIVE 초기: -2%
    ("emergency_stop_pct", "-3.0"),     # Paper: -4% → LIVE 초기: -3%
    ("trading_mode", "semi-auto"),      # 확인: semi-auto 유지
]

host = os.environ.get("POSTGRES_HOST", "")
port = os.environ.get("POSTGRES_PORT", "5432")
db   = os.environ.get("POSTGRES_DB", "stockbot")
user = os.environ.get("POSTGRES_USER", "stockbot")
pwd  = os.environ.get("POSTGRES_PASSWORD", "")

if not host or not pwd:
    raise RuntimeError("POSTGRES_HOST / POSTGRES_PASSWORD 환경변수가 없습니다 (railway run으로 실행하세요)")

conn = psycopg2.connect(host=host, port=int(port), dbname=db, user=user, password=pwd)
cur = conn.cursor()

for key, new_value in LIVE_INITIAL_PARAMS:
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    if row:
        old_val = row[0]
        cur.execute("UPDATE settings SET value = %s WHERE key = %s", (new_value, key))
        print(f"[UPDATE] {key}: {old_val} → {new_value}")
    else:
        print(f"[SKIP]   {key}: 키 없음")

conn.commit()
cur.close()
conn.close()
print("LIVE 초기 파라미터 적용 완료")
