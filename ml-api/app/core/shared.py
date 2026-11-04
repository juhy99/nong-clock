"""저장소 맨 위 shared/ 폴더의 JSON (화면과 같이 쓰는 목록: 품목·도매시장·흙 pH).

- 서버(도커): ml-api 이미지 안 /app/shared/ (Dockerfile 이 저장소 맨 위에서 빌드하며 복사)
- 내 PC: 저장소/shared/
- 다른 곳에 두려면 환경변수 SHARED_DIR
"""

import json
import os
from functools import lru_cache
from pathlib import Path

_HERE = Path(__file__).resolve()
_CANDIDATES = [Path(os.environ["SHARED_DIR"])] if os.environ.get("SHARED_DIR") else []
_CANDIDATES += [_HERE.parents[2] / "shared", _HERE.parents[3] / "shared"]  # /app/shared · 저장소/shared


@lru_cache
def load(name: str) -> dict:
    for d in _CANDIDATES:
        p = d / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"shared/{name} 을 찾을 수 없어요 (찾아본 곳: {', '.join(str(d) for d in _CANDIDATES)})")
