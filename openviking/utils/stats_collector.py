# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
"""Statistics collector for monitoring API calls and cache hits."""

from datetime import datetime
from threading import Lock
from typing import Dict, Any, Optional


class StatsCollector:
    """Thread-safe statistics collector."""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize statistics."""
        self._stats: Dict[str, int] = {
            'embedding_total_calls': 0,
            'embedding_api_calls': 0,
            'vlm_api_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'precomputed_vector_used': 0,
            'memory_queries': 0,
            'memories_created': 0,
        }
        self._timestamps: Dict[str, Optional[str]] = {}
        self._timestamps['embedding_api_last_call'] = None
        self._timestamps['cache_last_hit'] = None
        self._timestamps['query_last_time'] = None
        self._data_lock = Lock()
    
    def record_embedding_api_call(self):
        """Record an embedding API call."""
        with self._data_lock:
            self._stats['embedding_api_calls'] += 1
            self._timestamps['embedding_api_last_call'] = datetime.now().isoformat()
    
    def record_embedding_total_call(self):
        """Record total embedding calls (entry point)."""
        with self._data_lock:
            self._stats['embedding_total_calls'] += 1
    
    def record_vlm_api_call(self):
        """Record a VLM API call."""
        with self._data_lock:
            self._stats['vlm_api_calls'] += 1
    
    def record_cache_hit(self):
        """Record a cache hit."""
        with self._data_lock:
            self._stats['cache_hits'] += 1
            self._timestamps['cache_last_hit'] = datetime.now().isoformat()
    
    def record_cache_miss(self):
        """Record a cache miss."""
        with self._data_lock:
            self._stats['cache_misses'] += 1
    
    def record_precomputed_vector_used(self):
        """Record using a precomputed vector."""
        with self._data_lock:
            self._stats['precomputed_vector_used'] += 1
    
    def record_memory_query(self):
        """Record a memory query."""
        with self._data_lock:
            self._stats['memory_queries'] += 1
            self._timestamps['query_last_time'] = datetime.now().isoformat()
    
    def record_memory_created(self):
        """Record a memory creation."""
        with self._data_lock:
            self._stats['memories_created'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        with self._data_lock:
            total_embedding = self._stats['embedding_total_calls']
            
            from openviking.utils.vector_cache import VECTOR_CACHE_MAX_SIZE, get_vector_cache
            
            cache = get_vector_cache()
            cache_stats = cache.get_stats()
            
            return {
                'stats': self._stats.copy(),
                'timestamps': self._timestamps.copy(),
                'total_api_calls': self._stats['embedding_api_calls'] + self._stats['vlm_api_calls'],
                'cache_hit_rate': (
                    self._stats['cache_hits'] / total_embedding * 100
                    if total_embedding > 0 else 0
                ),
                'cache_max_size': VECTOR_CACHE_MAX_SIZE,
                'cache_size': cache_stats.get('size', 0)
            }
    
    def reset(self):
        """Reset all statistics."""
        with self._data_lock:
            self._initialize()


# Global instance
_stats_collector: Optional[StatsCollector] = None


def get_stats_collector() -> StatsCollector:
    """Get global stats collector instance."""
    global _stats_collector
    if _stats_collector is None:
        _stats_collector = StatsCollector()
    return _stats_collector
