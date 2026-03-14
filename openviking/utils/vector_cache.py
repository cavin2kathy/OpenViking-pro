# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
"""Vector cache with persistence support."""

import asyncio
import json
import time
import hashlib
import aiofiles
import glob
import re
from datetime import datetime
from typing import Optional, Dict, Tuple, List, Any
from openviking_cli.utils import get_logger

logger = get_logger(__name__)

# Metadata cleanup regex patterns
CONVERSATION_METADATA_RE = re.compile(
    r'(?:^|\n)\s*(?:Conversation info|Conversation metadata|会话信息|对话信息)\s*(?:\([^)]*\))?\s*:\s*```[\s\S]*?```',
    re.IGNORECASE
)
SENDER_METADATA_RE = re.compile(
    r'(?:^|\n)\s*Sender\s*(\([^)]*\))?\s*:\s*```[\s\S]*?```',
    re.IGNORECASE
)
JSON_BLOCK_RE = re.compile(r'```json\s*\n?[\s\S]*?```')
MESSAGE_ID_RE = re.compile(r'\s*\[[^\]\n]{1,120}\]\s*')


def sanitize_message_content(content: str) -> str:
    """Remove metadata from message content."""
    content = CONVERSATION_METADATA_RE.sub('', content)
    content = SENDER_METADATA_RE.sub('', content)
    content = JSON_BLOCK_RE.sub('', content)
    content = MESSAGE_ID_RE.sub(' ', content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


# Maximum concurrent API calls
MAX_CONCURRENT_EMBEDDING = 10

# Vector cache max size
VECTOR_CACHE_MAX_SIZE = 10000

# Cache persistence directory
CACHE_DIR = "/root/.openviking/cache"
VECTORS_DIR = f"{CACHE_DIR}/vectors"
CONTENT_DIR = f"{CACHE_DIR}/content"

# MD 文件保留天数
MD_FILE_RETENTION_DAYS = 7

# 每次淘汰的数量
EVICTION_BATCH_SIZE = 100

_embedding_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _embedding_semaphore
    if _embedding_semaphore is None:
        _embedding_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EMBEDDING)
    return _embedding_semaphore


class VectorCache:
    """
    LRU cache for embedding vectors with persistence.
    
    Features:
    - Content-based key (MD5 hash)
    - Permanent cache (no TTL expiration)
    - LRU eviction policy based on access time
    - Async persistence to MD files (only on API calls)
    - Load from MD files on startup (cache warmup)
    """
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Tuple[List[float], Dict[str, float], float]] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()
        self._pending: Dict[str, asyncio.Event] = {}
        self._persist_queue: asyncio.Queue = asyncio.Queue()
        self._persist_task: Optional[asyncio.Task] = None
        self._initialized = False
        self._persisted_keys: set = set()  # 已持久化的 key，避免重复写入
    
    def _ensure_persist_task(self):
        """Ensure persist task is started (lazy initialization)"""
        if self._initialized:
            return
        
        async def persist_worker():
            while True:
                try:
                    item = await self._persist_queue.get()
                    content_hash, content, vector, sparse_vector, timestamp = item
                    await self._persist_to_md(content_hash, content, vector, timestamp)
                    self._persist_queue.task_done()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Persist error: {e}")
        
        self._persist_task = asyncio.create_task(persist_worker())
        self._initialized = True
    
    async def _persist_to_md(self, content_hash: str, content: str, vector: List[float], timestamp: float):
        """Persist vector to MD file, content to separate file for human viewing"""
        try:
            date = datetime.now().strftime('%Y-%m-%d')
            
            # 创建目录
            import os
            os.makedirs(VECTORS_DIR, exist_ok=True)
            os.makedirs(CONTENT_DIR, exist_ok=True)
            
            vector_path = f"{VECTORS_DIR}/{date}.md"
            content_path = f"{CONTENT_DIR}/{date}.md"
            
            vector_json = json.dumps(vector)
            ts_str = datetime.fromtimestamp(timestamp).isoformat()
            
            # 写入向量文件: content_hash|vector_json|timestamp (系统用)
            async with aiofiles.open(vector_path, 'a') as f:
                await f.write(f"{content_hash}|{vector_json}|{ts_str}\n")
            
            # 写入内容文件: 时间戳|content (人看)
            async with aiofiles.open(content_path, 'a') as f:
                await f.write(f"{ts_str}|{content}\n")
            
            logger.debug(f"Persisted {content_hash[:8]} to cache")
        except Exception as e:
            logger.error(f"Failed to persist: {e}")
    
    def _compute_key(self, content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()
    
    def get_by_key(self, key: str) -> Optional[Dict]:
        if key in self._cache:
            vector, sparse_vector, timestamp = self._cache[key]
            # 缓存命中时更新访问时间（保护热点数据不被淘汰）
            self._cache[key] = (vector, sparse_vector, time.time())
            self._hits += 1
            return {"vector": vector, "sparse_vector": sparse_vector, "cached": True}
        
        self._misses += 1
        return None

    def get(self, content: str) -> Optional[Dict]:
        key = self._compute_key(content)
        return self.get_by_key(key)
    
    async def set_by_key(
        self, key: str, content: str, vector: List[float], sparse_vector: Optional[Dict] = None
    ):
        timestamp = time.time()
        
        async with self._lock:
            # 如果 key 已存在，只更新时间戳
            if key in self._cache:
                self._cache[key] = (vector, sparse_vector or {}, timestamp)
                return
            
            # LRU 淘汰：缓存满时一次性淘汰 1/5
            if len(self._cache) >= self._max_size:
                batch_size = max(1, self._max_size // 5)
                # 按访问时间排序，淘汰最老的 batch_size 个
                sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][2])
                for oldest_key in sorted_keys[:batch_size]:
                    del self._cache[oldest_key]
                    self._persisted_keys.discard(oldest_key)
            
            self._cache[key] = (vector, sparse_vector or {}, timestamp)
        
        # 只有未持久化过的 key 才写入 MD 文件
        if key not in self._persisted_keys:
            self._ensure_persist_task()
            await self._persist_queue.put((key, content, vector, sparse_vector, timestamp))
            self._persisted_keys.add(key)
        
        logger.debug(f"Cached vector for content hash {key[:8]}")

    async def set(
        self,
        content: str,
        vector: List[float],
        sparse_vector: Optional[Dict] = None,
    ):
        key = self._compute_key(content)
        await self.set_by_key(key, content, vector, sparse_vector)
    
    def load_from_md(self, limit: Optional[int] = None):
        """Load vectors from MD files on startup (up to limit)"""
        if limit is None:
            limit = self._max_size
        
        import os
        os.makedirs(VECTORS_DIR, exist_ok=True)
        os.makedirs(CONTENT_DIR, exist_ok=True)
        
        # 加载向量文件: content_hash|vector_json|timestamp (系统用)
        vector_files = sorted(glob.glob(f"{VECTORS_DIR}/*.md"), reverse=True)
        count = 0
        
        for vector_path in vector_files:
            if count >= limit:
                break
            
            try:
                with open(vector_path, 'r') as f:
                    for line in f:
                        if count >= limit:
                            break
                        
                        parts = line.strip().split('|', 2)
                        if len(parts) == 3:
                            content_hash, vector_json, ts_str = parts
                            
                            # 跳过已加载的 key
                            if content_hash in self._cache:
                                continue
                            
                            self._cache[content_hash] = (
                                json.loads(vector_json),
                                {},
                                datetime.fromisoformat(ts_str).timestamp()
                            )
                            self._persisted_keys.add(content_hash)
                            count += 1
            except Exception as e:
                logger.error(f"Failed to load {vector_path}: {e}")
        
        logger.info(f"Loaded {count} vectors from cache files (limit: {limit})")
        
        # 清理过期的 MD 文件
        self._cleanup_old_md_files()
    
    def _cleanup_old_md_files(self):
        """清理过期的 MD 文件，只保留最近 N 天的"""
        import os
        if not os.path.exists(CONTENT_DIR):
            return
        
        cutoff_time = time.time() - (MD_FILE_RETENTION_DAYS * 24 * 3600)
        cutoff_date = datetime.fromtimestamp(cutoff_time).strftime('%Y-%m-%d')
        
        for cache_dir in [CONTENT_DIR, VECTORS_DIR]:
            try:
                for filename in os.listdir(cache_dir):
                    if not filename.endswith('.md'):
                        continue
                    date_str = filename[:-3]
                    if date_str < cutoff_date:
                        file_path = os.path.join(cache_dir, filename)
                        os.remove(file_path)
                        logger.info(f"Cleaned up old cache file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup {cache_dir}: {e}")
    
    def clear(self):
        self._cache.clear()
        self._persisted_keys.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%"
        }
    
    async def shutdown(self):
        """Shutdown persistence task"""
        if self._persist_task:
            await self._persist_queue.join()
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass


_vector_cache: Optional[VectorCache] = None


def get_vector_cache() -> VectorCache:
    global _vector_cache
    if _vector_cache is None:
        _vector_cache = VectorCache(max_size=VECTOR_CACHE_MAX_SIZE)
    return _vector_cache


def clear_vector_cache():
    global _vector_cache
    if _vector_cache:
        _vector_cache.clear()


async def get_embedding(text: str, embedder) -> Any:
    """
    Unified interface for getting embedding vectors.
    """
    from openviking.utils.stats_collector import get_stats_collector
    from openviking.models.embedder.base import EmbedResult
    
    text = sanitize_message_content(text)
    
    # 校验文本长度（在sanitize之后检查，因为sanitize会清理文本）
    MAX_TEXT_LENGTH = 8192
    if len(text) > MAX_TEXT_LENGTH:
        logger.warning(f"Text too long ({len(text)} chars), truncating to {MAX_TEXT_LENGTH} chars. Text: {text[-200:]}...")
        text = text[-MAX_TEXT_LENGTH:]  # 截取后8192字符，保留最新内容
    
    stats = get_stats_collector()
    stats.record_embedding_total_call()
    
    cache = get_vector_cache()
    key = cache._compute_key(text)
    
    # ========== 第1次缓存检查 ==========
    cached = cache.get_by_key(key)
    if cached:
        stats.record_cache_hit()
        return EmbedResult(
            dense_vector=cached["vector"],
            sparse_vector=cached.get("sparse_vector", {})
        )
    
    event: asyncio.Event
    owns_execution = False
    while True:
        cached = cache.get_by_key(key)
        if cached:
            stats.record_cache_hit()
            return EmbedResult(
                dense_vector=cached["vector"],
                sparse_vector=cached.get("sparse_vector", {})
            )

        async with cache._lock:
            event = cache._pending.get(key)
            if event is None:
                event = asyncio.Event()
                cache._pending[key] = event
                owns_execution = True
                break

        await event.wait()
    
    # ========== 调用API ==========
    semaphore = _get_semaphore()
    try:
        async with semaphore:
            # API调用之前记录（确保失败也被统计）
            stats.record_embedding_api_call()
            
            result = await asyncio.to_thread(embedder.embed, text)
            await cache.set_by_key(key, text, result.dense_vector, result.sparse_vector)
            return result
    finally:
        if owns_execution:
            event.set()
            async with cache._lock:
                cache._pending.pop(key, None)
