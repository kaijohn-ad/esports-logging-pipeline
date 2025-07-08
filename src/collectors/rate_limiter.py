"""
レート制限管理モジュール

API呼び出しのレート制限を管理する
"""

import asyncio
import time
from collections import deque


class RateLimiter:
    """API レート制限管理クラス"""
    
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """レート制限チェック、必要に応じて待機"""
        async with self._lock:
            now = time.time()
            
            # time_window を過ぎたリクエストを削除
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()
            
            # 制限に達している場合は待機
            if len(self.requests) >= self.max_requests:
                wait_time = self.requests[0] + self.time_window - now + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    return await self.acquire()  # 再帰的に再チェック
            
            # リクエスト時刻を記録
            self.requests.append(now)