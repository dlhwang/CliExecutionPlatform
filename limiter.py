from slowapi import Limiter
from slowapi.util import get_remote_address

# IP 기반의 API 속도 제한을 위한 Limiter 전역 인스턴스 생성
# (main.py와 router 간의 순환 참조를 방지하기 위해 별도 분리)
limiter = Limiter(key_func=get_remote_address)
