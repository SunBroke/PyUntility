import time
import collections
import statistics
import threading
from typing import Dict, List, Optional, Any

class PerfStats:
    """
    通用耗时统计模块
    支持主标签(category)和子标签(tag)关联
    线程安全
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(PerfStats, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._data: Dict[str, Dict[str, List[float]]] = collections.defaultdict(lambda: collections.defaultdict(list))
        self._start_times: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._enabled = True
        self._initialized = True

    @classmethod
    def get_instance(cls):
        return cls()

    def enable(self):
        """开启统计"""
        self._enabled = True

    def disable(self):
        """关闭统计"""
        self._enabled = False

    def init(self):
        """初始化/重置统计数据"""
        with self._lock:
            self._data.clear()
            self._start_times.clear()

    def deinit(self):
        """逆初始化，清理资源"""
        self.init()

    def start_record(self, category: str, tag: str) -> Optional[str]:
        """
        开始记录耗时
        返回唯一key，用于end_record
        """
        if not self._enabled:
            return None
            
        key = f"{category}::{tag}::{threading.get_ident()}::{time.perf_counter()}"
        with self._lock:
            self._start_times[key] = time.perf_counter()
        return key

    def end_record(self, category: str, tag: str, key: str = None):
        """
        结束记录耗时
        如果你在start_record时保存了key，可以传入key以确保线程安全下的精确匹配
        否则默认使用category+tag匹配最近的一个开始时间（注意：仅限单线程模型或能保证调用顺序的场景）
        建议始终配合start_record返回的key使用
        """
        if not self._enabled:
            return

        end_time = time.perf_counter()
        
        with self._lock:
            if key and key in self._start_times:
                start_time = self._start_times.pop(key)
                elapsed = end_time - start_time
                self._data[category][tag].append(elapsed)
            else:
                # 兼容不传key的情况，但不推荐在多线程下这样用
                # 这里为了简单，不做复杂查找，仅作为备用逻辑
                pass

    def record_value(self, category: str, tag: str, elapsed_seconds: float):
        """直接记录一个耗时值"""
        if not self._enabled:
            return
            
        with self._lock:
            self._data[category][tag].append(elapsed_seconds)

    def get_stats(self, category: str = None) -> Dict[str, Any]:
        """
        获取统计结果
        如果指定category，只返回该category下的stats
        否则返回所有
        """
        with self._lock:
            # 深拷贝一份数据用于计算，避免锁太久
            snapshot = {k: {tk: tv[:] for tk, tv in v.items()} for k, v in self._data.items()}

        result = {}
        
        target_categories = [category] if category else snapshot.keys()

        for cat in target_categories:
            if cat not in snapshot:
                continue
            
            cat_result = {}
            for tag, values in snapshot[cat].items():
                if not values:
                    continue
                
                count = len(values)
                min_val = min(values)
                max_val = max(values)
                total = sum(values)
                
                # 计算平均值（去掉最大最小）
                if count > 2:
                    # 去掉一个最大值和一个最小值
                    filtered_sum = total - min_val - max_val
                    avg_val = filtered_sum / (count - 2)
                else:
                    avg_val = total / count

                cat_result[tag] = {
                    "count": count,
                    "min": min_val,
                    "max": max_val,
                    "avg_filtered": avg_val, # 去掉最大最小后的平均
                    "avg_raw": total / count # 原始平均
                }
            result[cat] = cat_result
            
        return result if not category else result.get(category, {})

    def _generate_report(self) -> str:
        """生成格式化的统计报告字符串"""
        stats = self.get_stats()
        lines = []
        lines.append("="*80)
        lines.append(f"{'Category':<15} | {'Tag':<15} | {'Count':<6} | {'Avg(ms)':<8} | {'Min(ms)':<8} | {'Max(ms)':<8}")
        lines.append("-" * 80)
        
        for cat, tags in stats.items():
            for tag, stat in tags.items():
                line = f"{cat:<15} | {tag:<15} | {stat['count']:<6} | {stat['avg_filtered']*1000:<8.3f} | {stat['min']*1000:<8.3f} | {stat['max']*1000:<8.3f}"
                lines.append(line)
        lines.append("="*80)
        return "\n".join(lines)

    def print_stats(self):
        """打印格式化的统计信息"""
        print("\n" + self._generate_report() + "\n")

    def save_stats(self, file_path: str):
        """将统计信息保存到文件"""
        report = self._generate_report()
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report)

# 便捷使用的上下文管理器
class PerfTimer:
    def __init__(self, category: str, tag: str, stats_mgr: PerfStats = None):
        self.category = category
        self.tag = tag
        self.mgr = stats_mgr or PerfStats.get_instance()
        self.key = None

    def __enter__(self):
        self.key = self.mgr.start_record(self.category, self.tag)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mgr.end_record(self.category, self.tag, self.key)
