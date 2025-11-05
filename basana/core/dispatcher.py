# Basana
#
# Copyright 2022 Gabriel Martin Becedillas Ruiz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict
from typing import cast, Any, Awaitable, Callable, Dict, Generator, List, Optional, Set, Tuple
import abc
import asyncio
import contextlib
import dataclasses
import datetime
import functools
import heapq
import logging
import platform
import signal

from . import dt, errors, event, helpers, logs


# 日志记录器，用于记录事件分发器的运行状态
logger = logging.getLogger(__name__)

# 事件处理器的类型定义：接受事件并返回异步结果的函数
EventHandler = Callable[[event.Event], Awaitable[Any]]

# 空闲处理器的类型定义：不接受参数并返回异步结果的函数
IdleHandler = Callable[[], Awaitable[Any]]

# 调度作业的类型定义：不接受参数并返回异步结果的函数
SchedulerJob = Callable[[], Awaitable[Any]]


@dataclasses.dataclass
class EventDispatch:
    """
    【中文说明】事件分发数据结构
    
    【功能描述】
    封装事件和其对应的处理器的数据结构，用于在事件分发过程中传递信息。
    
    【字段说明】
    - event: event.Event - 要分发的事件实例
    - handlers: List[EventHandler] - 注册的异步事件处理器列表
    
    【使用场景】
    - 在事件分发循环中，将事件和对应的处理器一起传递给任务池
    - 支持批量事件处理和异步执行
    
    【注意事项】
    - 这是一个不可变的数据类，字段在创建后不能修改
    - 用于内部事件分发机制，通常不直接由用户代码使用
    """
    event: event.Event
    handlers: List[EventHandler]


@dataclasses.dataclass(order=True)
class ScheduledJob:
    """
    【中文说明】调度作业数据结构
    
    【功能描述】
    封装调度作业和其执行时间的数据结构，支持按时间排序。
    
    【字段说明】
    - when: datetime.datetime - 作业计划执行的时间点
    - job: SchedulerJob - 要执行的异步作业函数
    
    【排序特性】
    - 根据when字段进行排序，支持最小堆操作
    - job字段不参与比较（因为在Windows上比较函数对象会失败）
    
    【使用场景】
    - 在调度队列中存储和管理定时执行的作业
    - 支持按时间顺序执行调度任务
    
    【注意事项】
    - 时间必须包含时区信息
    - 作业函数应该是异步的，返回Awaitable
    """
    when: datetime.datetime
    job: SchedulerJob = dataclasses.field(compare=False)  # Comparing function objects fails on Win32


class SchedulerQueue:
    """
    【中文说明】调度作业优先级队列
    
    【功能描述】
    基于最小堆实现的调度作业优先级队列，按计划执行时间升序排列。
    提供高效的查看和弹出操作，支持快速获取下一个要执行的作业。
    
    【核心特性】
    - 优先级队列：作业按执行时间排序，最早执行的作业优先级最高
    - 高效操作：push、peek、pop操作的时间复杂度为O(log n)
    - 时间验证：自动检查时间戳是否包含时区信息
    
    【内部实现】
    - 使用heapq模块实现最小堆
    - 通过ScheduledJob数据类封装作业和时间
    
    【使用场景】
    - 事件分发器中管理定时执行的作业
    - 需要按时间顺序执行任务的场景
    
    【注意事项】
    - 所有时间必须包含时区信息
    - 队列为空时peek操作返回None

    A priority queue for scheduler jobs.
    Jobs are stored in ascending order by their scheduled execution time.
    This allows for efficient peek and pop operations of the next scheduled job.
    """

    def __init__(self):
        """
        【中文说明】初始化调度队列
        
        【功能描述】
        创建空的调度队列实例。
        
        【内部实现】
        - 使用列表作为堆的底层存储
        - 通过heapq模块维护最小堆特性
        
        【使用示例】
        >>> scheduler_queue = SchedulerQueue()
        >>> scheduler_queue.push(datetime.now(timezone.utc), my_job)
        """
        # 使用列表作为最小堆的底层存储
        self._queue = []

    def push(self, when: datetime.datetime, job: SchedulerJob):
        """
        【中文说明】将作业添加到调度队列
        
        【功能描述】
        将新的调度作业添加到优先级队列中，按执行时间排序。
        
        【参数说明】
        - when: datetime.datetime - 作业计划执行的时间，必须包含时区信息
        - job: SchedulerJob - 要执行的异步作业函数
        
        【验证检查】
        - 检查时间是否包含时区信息，防止使用朴素时间戳
        
        【操作特性】
        - 时间复杂度：O(log n)，高效的堆插入操作
        - 排序方式：按执行时间升序排列
        
        【异常情况】
        - 如果when参数不包含时区信息，会抛出AssertionError
        
        【使用示例】
        >>> scheduler_queue.push(
        ...     datetime.datetime.now(datetime.timezone.utc),
        ...     async_function
        ... )
        """
        # 验证时间戳必须包含时区信息
        assert not dt.is_naive(when), f"{when} should have timezone information set"
        # 将作业添加到最小堆中，按执行时间排序
        heapq.heappush(self._queue, ScheduledJob(when=when, job=job))

    def peek_next_event_dt(self) -> Optional[datetime.datetime]:
        """
        【中文说明】查看下一个作业的执行时间
        
        【功能描述】
        返回队列中下一个要执行的作业的时间，但不从队列中移除该作业。
        
        【返回值】
        - Optional[datetime.datetime]: 下一个作业的执行时间，如果队列为空则返回None
        
        【操作特性】
        - 时间复杂度：O(1)，高效查看操作
        - 非破坏性：不修改队列状态
        
        【使用场景】
        - 检查是否有即将执行的作业
        - 决定事件分发循环的下一步操作
        
        【注意事项】
        - 如果队列为空，返回None
        - 返回的时间是队列中最早要执行的作业时间
        """
        ret = None
        if self._queue:
            # 获取堆顶元素（最小时间）的执行时间
            ret = self._queue[0].when
        return ret

    def peek_last_event_dt(self) -> Optional[datetime.datetime]:
        """
        【中文说明】查看最后一个作业的执行时间
        
        【功能描述】
        返回队列中最后一个要执行的作业的时间，但不从队列中移除该作业。
        
        【返回值】
        - Optional[datetime.datetime]: 最后一个作业的执行时间，如果队列为空则返回None
        
        【操作特性】
        - 时间复杂度：O(n log n)，需要查找最大元素
        - 非破坏性：不修改队列状态
        
        【使用场景】
        - 回测结束时处理所有待执行的调度作业
        - 了解调度作业的时间范围
        
        【注意事项】
        - 如果队列为空，返回None
        - 性能较低，不适合频繁调用
        """
        ret = None
        if self._queue:
            # 使用heapq.nlargest获取最大的时间
            ret = heapq.nlargest(1, self._queue)[0].when
        return ret

    def pop(self) -> Tuple[datetime.datetime, SchedulerJob]:
        """
        【中文说明】从队列中移除并返回下一个作业
        
        【功能描述】
        从优先级队列中移除并返回执行时间最早的作业。
        
        【返回值】
        - Tuple[datetime.datetime, SchedulerJob]: 包含作业执行时间和作业函数的元组
        
        【操作特性】
        - 时间复杂度：O(log n)，高效的堆弹出操作
        - 破坏性：从队列中移除作业
        
        【验证检查】
        - 确保队列不为空
        
        【异常情况】
        - 如果队列为空，会抛出AssertionError
        
        【使用示例】
        >>> when, job = scheduler_queue.pop()
        >>> await job()
        """
        # 确保队列不为空
        assert self._queue
        # 从最小堆中弹出执行时间最早的作业
        scheduled_job = heapq.heappop(self._queue)
        return scheduled_job.when, scheduled_job.job


class EventMultiplexer:
    """
    【中文说明】事件多路复用器
    
    【功能描述】
    管理多个事件源，按时间顺序检索事件的复用器。
    通过预取机制高效地从多个事件源中获取最早的事件，确保事件按时间顺序处理。
    
    【核心特性】
    - 多路复用：同时管理多个事件源
    - 时间排序：按事件发生时间升序返回事件
    - 预取优化：通过预取事件减少pop操作的延迟
    - 高效查询：支持快速查看下一个事件的时间
    
    【内部机制】
    - 预取缓存：为每个事件源缓存一个预取的事件
    - 时间比较：在多个事件源中选择时间最早的事件
    - 条件过滤：支持按最大时间条件过滤事件
    
    【使用场景】
    - 事件分发器需要从多个源按时间顺序处理事件
    - 需要合并多个事件流并按时间排序
    - 回测和实时交易中的事件调度
    
    【注意事项】
    - 假设事件源提供的事件按时间升序排列
    - 预取机制可能会占用额外内存
    - 适合事件源数量适中的场景

    A multiplexer that manages multiple event sources and provides methods to retrieve events in chronological order.
    """
    def __init__(self) -> None:
        """
        【中文说明】初始化事件多路复用器
        
        【功能描述】
        创建空的事件多路复用器实例。
        
        【内部状态】
        - _prefetched_events: 字典，键为事件源，值为预取的事件（可能为None）
        
        【使用示例】
        >>> event_mux = EventMultiplexer()
        >>> event_mux.add(event_source1)
        >>> event_mux.add(event_source2)
        """
        # 预取事件缓存：事件源 -> 预取的事件（None表示需要重新获取）
        self._prefetched_events: Dict[event.EventSource, Optional[event.Event]] = {}

    def add(self, source: event.EventSource):
        """
        【中文说明】添加事件源到多路复用器
        
        【功能描述】
        将新的事件源添加到多路复用器中，开始从其获取事件。
        
        【参数说明】
        - source: event.EventSource - 要添加的事件源实例
        
        【内部操作】
        - 将事件源添加到预取字典中，初始值为None
        - 后续调用pop或peek方法时会自动预取事件
        
        【使用场景】
        - 在事件分发器中注册新的事件源
        - 动态添加事件源到多路复用器
        
        【注意事项】
        - 同一个事件源不会被重复添加
        - 添加后不会立即预取事件，直到需要时才会预取
        """
        # 将事件源添加到预取字典，初始值为None（表示需要预取）
        self._prefetched_events.setdefault(source)

    def peek_next_event_dt(self) -> Optional[datetime.datetime]:
        """
        【中文说明】查看下一个事件的发生时间
        
        【功能描述】
        返回所有事件源中下一个可用事件的发生时间，但不消费任何事件。
        
        【返回值】
        - Optional[datetime.datetime]: 下一个事件的时间，如果没有事件则返回None
        
        【操作流程】
        1. 预取所有需要预取的事件源
        2. 从所有预取的事件中选择时间最早的事件
        3. 返回该事件的时间
        
        【使用场景】
        - 决定事件分发循环的下一步操作
        - 检查是否有待处理的事件
        - 回测中确定下一个要处理的时间点
        
        【注意事项】
        - 非破坏性操作，不修改内部状态
        - 如果所有事件源都没有事件，返回None
        - 返回的时间是所有事件源中最早的事件时间
        """
        # 预取所有需要预取的事件源
        self._prefetch()

        # 从所有预取的事件中选择时间最早的事件，返回其时间
        return min(
            [evnt.when for evnt in self._prefetched_events.values() if evnt],
            default=None
        )

    def pop(self, max_dt: datetime.datetime) -> Tuple[Optional[event.EventSource], Optional[event.Event]]:
        """
        【中文说明】弹出满足条件的最早事件
        
        【功能描述】
        从所有事件源中弹出时间最早且不超过指定最大时间的事件。
        
        【参数说明】
        - max_dt: datetime.datetime - 事件时间的最大限制，只返回时间<=max_dt的事件
        
        【返回值】
        - Tuple[Optional[event.EventSource], Optional[event.Event]]: 
          包含事件源和事件的元组，如果没有满足条件的事件则返回(None, None)
        
        【算法逻辑】
        1. 遍历所有事件源，预取需要预取的事件
        2. 在所有满足条件（时间<=max_dt）的事件中选择时间最早的事件
        3. 消费该事件，将其从预取缓存中移除
        
        【使用场景】
        - 事件分发循环中按时间顺序获取事件
        - 需要按时间窗口处理事件的场景
        
        【注意事项】
        - 破坏性操作，会消费事件
        - 只返回一个事件，即使有多个事件满足条件
        - 如果没有满足条件的事件，返回(None, None)
        """
        ret_source: Optional[event.EventSource] = None
        ret_event: Optional[event.Event] = None

        # 查找要返回的下一个事件，即时间最早且<=max_dt的事件
        for source, evnt in self._prefetched_events.items():
            # 为排序目的预取事件
            if evnt is None:
                evnt = source.pop()
                self._prefetched_events[source] = evnt
            # 如果事件满足过滤条件，检查是否是下一个要返回的事件
            if evnt and evnt.when <= max_dt and (ret_event is None or evnt.when < ret_event.when):
                ret_source = source
                ret_event = evnt

        # 消费事件：从预取缓存中移除已返回的事件
        if ret_source:
            self._prefetched_events[ret_source] = None

        return (ret_source, ret_event)

    def pop_while(self, max_dt: datetime.datetime) -> Generator[Tuple[event.EventSource, event.Event], None, None]:
        """
        【中文说明】连续弹出满足条件的所有事件
        
        【功能描述】
        生成器方法，连续弹出所有时间不超过指定最大时间的事件。
        
        【参数说明】
        - max_dt: datetime.datetime - 事件时间的最大限制
        
        【返回值】
        - Generator[Tuple[event.EventSource, event.Event], None, None]: 
          生成事件源和事件的元组的生成器
        
        【使用方式】
        - 使用for循环遍历所有满足条件的事件
        - 当没有更多满足条件的事件时自动停止
        
        【使用场景】
        - 批量处理某个时间点之前的所有事件
        - 回测中处理特定时间范围内的所有事件
        - 需要连续处理多个事件的场景
        
        【注意事项】
        - 生成器会持续产生事件直到没有满足条件的事件
        - 每次迭代都会消费一个事件
        - 适合在事件分发循环中使用
        """
        # 持续弹出满足条件的事件，直到返回(None, None)
        while None not in (src_and_event := self.pop(max_dt)):
            # 使用cast确保类型安全，生成事件源和事件的元组
            yield (cast(event.EventSource, src_and_event[0]), cast(event.Event, src_and_event[1]))

    def _prefetch(self):
        """
        【中文说明】预取需要预取的事件
        
        【功能描述】
        内部方法，为所有需要预取的事件源预取下一个事件。
        
        【操作流程】
        1. 找出所有预取缓存为None的事件源（需要预取）
        2. 为每个需要预取的事件源调用pop()方法获取事件
        3. 将获取到的事件更新到预取缓存中
        
        【使用时机】
        - 在peek_next_event_dt()方法中调用，确保所有事件源都有预取的事件
        - 在pop()方法中按需预取单个事件源
        
        【注意事项】
        - 内部方法，通常不直接调用
        - 只预取缓存为None的事件源
        - 如果事件源没有事件，预取缓存保持None
        """
        # 找出所有需要预取的事件源（预取缓存为None的源）
        sources_to_pop = [
            source for source, event in self._prefetched_events.items() if event is None
        ]
        # 为每个需要预取的事件源获取事件
        for source in sources_to_pop:
            if event := source.pop():
                # 将获取到的事件更新到预取缓存中
                self._prefetched_events[source] = event


class EventDispatcher(metaclass=abc.ABCMeta):
    """
    【中文说明】事件分发器抽象基类
    
    【功能描述】
    负责连接事件源和事件处理器，并按正确顺序分发事件的核心组件。
    定义了事件分发器的通用接口和行为，具体实现由子类提供。
    
    【核心职责】
    - 管理事件源和事件处理器的注册关系
    - 按时间顺序调度和执行事件
    - 管理异步任务的生命周期
    - 提供调度作业功能
    
    【架构设计】
    - 抽象基类：定义通用接口，子类实现具体分发逻辑
    - 任务池管理：使用TaskPool管理并发事件处理
    - 生产者模式：支持事件生产者的初始化、运行和清理
    - 多路复用：通过EventMultiplexer管理多个事件源
    
    【子类实现】
    - BacktestingDispatcher: 回测场景的事件分发器
    - RealtimeDispatcher: 实时交易场景的事件分发器
    
    【参数说明】
    - max_concurrent: int - 并发处理事件的最大数量
    
    【注意事项】
    - 一旦开始运行，不能再订阅新的事件源或处理器
    - 调度作业的时间必须包含时区信息
    - 支持信号处理以优雅停止分发循环

    Responsible for connecting event sources to event handlers and dispatching events in the right order.

    :param max_concurrent: The maximum number of events to process concurrently.

    .. note::

        The following helper functions are provided to build event dispatchers suitable for backtesting or for live
        trading:

        * :func:`basana.backtesting_dispatcher`
        * :func:`basana.realtime_dispatcher`
    """

    def __init__(self, max_concurrent: int):
        """
        【中文说明】初始化事件分发器
        
        【功能描述】
        创建事件分发器实例，初始化所有内部状态和组件。
        
        【内部状态说明】
        - _event_handlers: 事件源到处理器列表的映射字典
        - _sniffers_pre: 前置嗅探器列表，在所有处理器之前执行
        - _sniffers_post: 后置嗅探器列表，在所有处理器之后执行  
        - _producers: 事件生产者集合
        - _core_tasks: 核心任务组，管理生产者和分发循环
        - _running: 运行状态标志
        - _stopped: 停止状态标志
        - _scheduler_queue: 调度作业队列
        - _event_mux: 事件多路复用器
        - _handler_tasks: 处理器任务池，管理并发事件处理
        - stop_on_handler_exceptions: 处理器异常时是否停止的标志
        
        【组件关系】
        - 事件源 -> 事件多路复用器 -> 事件分发 -> 处理器任务池
        - 生产者 -> 核心任务组 -> 事件源
        - 调度作业 -> 调度队列 -> 处理器任务池
        
        【参数说明】
        - max_concurrent: int - 并发处理事件的最大数量
        
        【注意事项】
        - 初始化后分发器处于未运行状态
        - 需要调用run()方法启动分发循环
        - 默认情况下处理器异常不会导致分发器停止
        """
        # 事件处理器映射：事件源 -> 事件处理器列表
        self._event_handlers: Dict[event.EventSource, List[EventHandler]] = defaultdict(list)
        # 前置嗅探器：在所有事件处理器之前执行
        self._sniffers_pre: List[EventHandler] = []
        # 后置嗅探器：在所有事件处理器之后执行
        self._sniffers_post: List[EventHandler] = []
        # 事件生产者集合
        self._producers: Set[event.Producer] = set()
        # 核心任务组：管理生产者和分发循环等核心任务
        self._core_tasks: Optional[helpers.TaskGroup] = None
        # 运行状态标志：表示分发器是否正在运行
        self._running = False
        # 停止状态标志：表示分发器是否已请求停止
        self._stopped = False
        # 调度作业队列：管理定时执行的作业
        self._scheduler_queue = SchedulerQueue()
        # 事件多路复用器：管理多个事件源并按时间顺序检索事件
        self._event_mux = EventMultiplexer()
        # 处理器任务池：管理事件和调度处理器的并发执行
        self._handler_tasks = helpers.TaskPool(max_concurrent, max_queue_size=max_concurrent * 10)
        # 处理器异常停止标志：设置为True时，处理器异常会导致分发器停止
        self.stop_on_handler_exceptions = False

    @property
    def current_event_dt(self) -> Optional[datetime.datetime]:
        """
        【中文说明】当前事件时间（已弃用）
        
        【功能描述】
        返回当前正在处理的事件的时间，这是一个已弃用的属性。
        
        【弃用说明】
        - 已弃用：建议使用 now() 方法替代
        - 保留此属性是为了向后兼容
        
        【返回值】
        - Optional[datetime.datetime]: 当前事件的时间，如果没有处理过事件则返回None
        
        【注意事项】
        - 这是一个只读属性
        - 在子类中可能有不同的实现方式
        - 未来版本可能会移除此属性
        """
        helpers.deprecation_warning("Use now() instead")
        return self.now()

    @abc.abstractmethod
    def now(self) -> datetime.datetime:
        """
        【中文说明】获取当前时间（抽象方法）
        
        【功能描述】
        抽象方法，返回分发器当前的时间概念。
        子类必须实现此方法以提供适当的时间语义。
        
        【返回值】
        - datetime.datetime: 当前时间，必须包含时区信息
        
        【子类实现要求】
        - BacktestingDispatcher: 返回最后处理的事件时间
        - RealtimeDispatcher: 返回当前UTC时间
        
        【使用场景】
        - 在事件处理中获取当前时间
        - 调度作业的时间比较
        - 时间相关的业务逻辑
        
        【注意事项】
        - 必须返回包含时区信息的时间
        - 在回测和实时交易中有不同的语义
        """
        raise NotImplementedError()

    @property
    def stopped(self) -> bool:
        """
        【中文说明】停止状态检查
        
        【功能描述】
        检查分发器是否已请求停止。
        
        【返回值】
        - bool: 如果已调用stop()方法则返回True，否则返回False
        
        【使用场景】
        - 在事件处理循环中检查是否应该停止
        - 在处理器中检查分发器状态
        - 优雅停止的逻辑判断
        
        【注意事项】
        - 这是一个只读属性
        - 停止请求是异步的，可能不会立即生效
        - 用于检查是否应该停止处理新事件
        """
        return self._stopped

    def stop(self):
        """
        【中文说明】请求停止事件分发循环
        
        【功能描述】
        请求事件分发器停止事件处理循环。
        这是一个异步请求，分发器会在适当的时候完全停止。
        
        【停止流程】
        1. 设置_stopped标志为True
        2. 取消所有核心任务（如果存在）
        3. 取消所有处理器任务
        
        【内部操作】
        - 设置_stopped标志，阻止新的事件处理
        - 取消核心任务组，停止生产者和分发循环
        - 取消处理器任务池，停止所有待处理的事件
        
        【使用场景】
        - 用户主动停止分发器
        - 信号处理（如Ctrl+C）
        - 错误恢复或系统关闭
        
        【注意事项】
        - 停止请求是异步的，不会立即停止所有操作
        - 已开始处理的事件会继续完成
        - 可以安全地多次调用此方法
        """
        logger.debug("Stop requested")
        # 设置停止标志，阻止新的事件处理
        self._stopped = True
        # 取消核心任务组（生产者和分发循环）
        if self._core_tasks:
            self._core_tasks.cancel()
        # 取消处理器任务池
        self._handler_tasks.cancel()

    def subscribe(self, source: event.EventSource, event_handler: EventHandler):
        """
        【中文说明】订阅事件源
        
        【功能描述】
        注册一个异步可调用对象，当事件源有新事件时将被调用。
        
        【参数说明】
        - source: event.EventSource - 事件源实例
        - event_handler: EventHandler - 接收事件的异步可调用对象
        
        【注册流程】
        1. 将事件源添加到事件多路复用器
        2. 将事件处理器添加到对应事件源的处理器列表
        3. 如果事件源有生产者，将生产者添加到生产者集合
        
        【验证检查】
        - 确保分发器未运行（运行后不能订阅新的事件源）
        
        【异常情况】
        - 如果分发器正在运行，会抛出AssertionError
        
        【使用场景】
        - 为特定事件源注册处理器
        - 建立事件源和处理器之间的映射关系
        - 动态添加事件处理逻辑
        
        【注意事项】
        - 只能在分发器运行前调用
        - 同一个事件源可以注册多个处理器
        - 同一个处理器不会被重复注册到同一个事件源
        """

        assert not self._running, "Subscribing once we're running is not currently supported."

        # 将事件源添加到事件多路复用器，开始接收事件
        self._event_mux.add(source)
        # 获取或创建该事件源的处理器列表
        handlers = self._event_handlers[source]
        # 如果处理器尚未注册，添加到列表中
        if event_handler not in handlers:
            handlers.append(event_handler)
        # 如果事件源有生产者，将生产者添加到生产者集合
        if source.producer:
            self._producers.add(source.producer)

    def subscribe_all(self, event_handler: EventHandler, front_run: bool = False):
        """
        【中文说明】订阅所有事件
        
        【功能描述】
        注册一个异步可调用对象，对所有事件都会被调用。
        可以作为全局事件嗅探器使用。
        
        【参数说明】
        - event_handler: EventHandler - 接收事件的异步可调用对象
        - front_run: bool - 是否在所有其他处理器之前执行
        
        【执行顺序】
        - front_run=True: 在所有特定事件源处理器之前执行（前置嗅探器）
        - front_run=False: 在所有特定事件源处理器之后执行（后置嗅探器）
        
        【验证检查】
        - 确保分发器未运行（运行后不能订阅新的嗅探器）
        
        【使用场景】
        - 全局事件日志记录
        - 事件监控和统计
        - 调试和性能分析
        
        【注意事项】
        - 只能在分发器运行前调用
        - 嗅探器会接收到所有事件，无论来自哪个事件源
        - 前置嗅探器适合预处理，后置嗅探器适合后处理
        """

        assert not self._running, "Subscribing once we're running is not currently supported."

        # 根据front_run参数选择前置或后置嗅探器列表
        sniffers = self._sniffers_pre if front_run else self._sniffers_post
        # 如果嗅探器尚未注册，添加到列表中
        if event_handler not in sniffers:
            sniffers.append(event_handler)

    def schedule(self, when: datetime.datetime, job: SchedulerJob):
        """
        【中文说明】调度定时作业
        
        【功能描述】
        调度一个函数在指定时间执行。
        
        【参数说明】
        - when: datetime.datetime - 函数应该执行的时间
        - job: SchedulerJob - 要执行的异步作业函数
        
        【内部操作】
        - 将作业和时间推送到调度队列
        - 调度队列会按时间排序管理作业
        
        【时间要求】
        - 时间必须包含时区信息
        - 时间应该在未来或当前时间
        
        【使用场景】
        - 定时执行特定任务
        - 延迟执行操作
        - 周期性任务调度
        
        【注意事项】
        - 作业函数应该是异步的
        - 时间必须包含时区信息
        - 可以在分发器运行时调用
        """
        # 将作业推送到调度队列，队列会按时间排序
        self._scheduler_queue.push(when, job)

    async def run(self, stop_signals: List[int] = [signal.SIGINT, signal.SIGTERM]):
        """Executes the event dispatch loop.

        :param stop_signals: The signals that will be handled to request :func:`run()` to :func:`stop()`.

        This method will execute the following steps in order:

        #. Call :meth:`basana.Producer.initialize` on all producers.
        #. Call :meth:`basana.Producer.main` on all producers and execute event dispatch loop until stopped.
        #. Call :meth:`basana.Producer.finalize` on all producers.
        """

        assert not self._running, "Can't run twice."
        assert self._core_tasks is None

        # This block has coverage on all platforms except on Windows.
        if platform.system() != "Windows":  # pragma: no cover
            for stop_signal in stop_signals:
                asyncio.get_event_loop().add_signal_handler(stop_signal, self.stop)

        self._running = True
        try:
            # Initialize producers.
            async with self._core_task_group() as tg:
                for producer in self._producers:
                    tg.create_task(producer.initialize())
            # Run producers and dispatch loop.
            async with self._core_task_group() as tg:
                for producer in self._producers:
                    tg.create_task(producer.main())
                tg.create_task(self._dispatch_loop())
        except asyncio.CancelledError:
            if not self.stopped:
                raise
        finally:
            # Cancel any pending task in the event handlers pool.
            self._handler_tasks.cancel()
            await self._handler_tasks.wait()
            # No more cancelation at this point.
            self._core_tasks = None
            # Finalize producers.
            await gather_no_raise(*[producer.finalize() for producer in self._producers])

    def on_error(self, error: Any):
        logger.error(error)

    @abc.abstractmethod
    async def _dispatch_loop(self):
        raise NotImplementedError()

    @contextlib.asynccontextmanager
    async def _core_task_group(self):
        try:
            async with helpers.TaskGroup() as tg:
                self._core_tasks = tg  # So it can be canceled.
                yield tg
        finally:
            self._core_tasks = None

    async def _dispatch_event(self, event_dispatch: EventDispatch):
        logger.debug(logs.StructuredMessage(
            "Dispatching event", when=event_dispatch.event.when, type=helpers.classpath(event_dispatch.event)
        ))
        if self._sniffers_pre:
            await asyncio.gather(
                *[self._call_event_handler(event_dispatch.event, handler) for handler in self._sniffers_pre]
            )
        if event_dispatch.handlers:
            await asyncio.gather(
                *[self._call_event_handler(event_dispatch.event, handler) for handler in event_dispatch.handlers]
            )
        if self._sniffers_post:
            await asyncio.gather(
                *[self._call_event_handler(event_dispatch.event, handler) for handler in self._sniffers_post]
            )

    async def _call_event_handler(self, event: event.Event, handler: EventHandler):
        try:
            return await handler(event)
        except Exception as e:
            logger.exception(logs.StructuredMessage(
                "Unhandled exception in event handler", error=e, event=dict(type=type(event), when=event.when),
                handler=handler
            ))
            if self.stop_on_handler_exceptions:
                self.stop()

    async def _execute_scheduled(self, dt: datetime.datetime, job: SchedulerJob):
        logger.debug(logs.StructuredMessage("Executing scheduled job", scheduled=dt))

        try:
            await job()
        except Exception as e:
            logger.exception(logs.StructuredMessage(
                "Unhandled exception in handler", error=e, dt=dt, scheduler_job=job
            ))
            if self.stop_on_handler_exceptions:
                self.stop()


class BacktestingDispatcher(EventDispatcher):
    """Event dispatcher for backtesting.

    :param max_concurrent: The maximum number of events to process concurrently.
    """

    def __init__(self, max_concurrent: int):
        super().__init__(max_concurrent=max_concurrent)
        self._last_dt: Optional[datetime.datetime] = None

    async def run(self, stop_signals: List[int] = [signal.SIGINT, signal.SIGTERM]):
        with logs.backtesting_log_mode(self):
            await super().run(stop_signals=stop_signals)

    @property
    def now_available(self) -> bool:
        return self._last_dt is not None

    def now(self) -> datetime.datetime:
        if self._last_dt is None:
            raise errors.Error("Can't calculate current datetime since no events were processed")
        return self._last_dt

    def _set_now(self, now: datetime.datetime):
        # For testing purposes.
        assert self._last_dt is None or now >= self._last_dt
        self._last_dt = now

    async def _dispatch_loop(self):
        while not self.stopped:
            next_dt = self._event_mux.peek_next_event_dt()
            if next_dt:
                # Check that events are processed in ascending order.
                assert self._last_dt is None or next_dt >= self._last_dt, \
                    f"{next_dt} can't be dispatched after {self._last_dt}"

                await self._dispatch_scheduled(next_dt)
                await self._dispatch_events(next_dt)
            else:
                # No more events. Dispatch all pending scheduled jobs before stopping.
                if last_scheduled_dt := self._scheduler_queue.peek_last_event_dt():
                    await self._dispatch_scheduled(last_scheduled_dt)
                self.stop()

    async def _dispatch_scheduled(self, dt: datetime.datetime):
        # Execute jobs that were scheduled to run before dt.
        next_scheduled_dt = self._scheduler_queue.peek_next_event_dt()
        while next_scheduled_dt and next_scheduled_dt <= dt:
            # If self._last_dt is already set in the future, don't move it backwards in time.
            next_scheduled_dt, job = self._scheduler_queue.pop()
            if self._last_dt is None or next_scheduled_dt > self._last_dt:
                self._last_dt = next_scheduled_dt

            await self._handler_tasks.push(functools.partial(self._execute_scheduled, next_scheduled_dt, job))
            # Waiting here and not outside of the loop to prevent executing distant scheduled jobs at the same time.
            await self._handler_tasks.wait()

            next_scheduled_dt = self._scheduler_queue.peek_next_event_dt()

    async def _dispatch_events(self, dt: datetime.datetime):
        # Pop events, push them into the task pool, and wait those to finish executing.
        self._last_dt = dt
        for source, evnt in self._event_mux.pop_while(dt):
            await self._handler_tasks.push(
                functools.partial(
                    self._dispatch_event, EventDispatch(event=evnt, handlers=self._event_handlers[source])
                )
            )
        await self._handler_tasks.wait()


class RealtimeDispatcher(EventDispatcher):
    """Event dispatcher for live trading.

    :param max_concurrent: The maximum number of events to process concurrently.
    """

    def __init__(self, max_concurrent: int):
        super().__init__(max_concurrent=max_concurrent)
        self._prev_event_dt: Dict[event.EventSource, datetime.datetime] = {}
        self.idle_sleep: float = 0.001
        self._wait_all_timeout: float = 0   # TODO: Will be removed in a future version.
        self._idle_handlers: List[IdleHandler] = []

    def now(self) -> datetime.datetime:
        return dt.utc_now()

    def subscribe_idle(self, idle_handler: IdleHandler):
        """Registers an async callable that will be called when there are no events to dispatch.

        :param idle_handler: An async callable that receives no arguments.
        """

        assert not self._running, "Subscribing once we're running is not currently supported."

        if idle_handler not in self._idle_handlers:
            self._idle_handlers.append(idle_handler)

    async def _dispatch_loop(self):
        while not self.stopped:
            now = dt.utc_now()
            # Feed the task pool with scheduled jobs and events that are ready for processing.
            await asyncio.gather(
                self._push_scheduled(now),
                self._push_events(now),
            )
            # Optionally give some time for handlers to execute before pushing new ones.
            # This is disabled by default and it will be deprecated.
            if self._wait_all_timeout:  # pragma: no cover
                await self._handler_tasks.wait(timeout=self._wait_all_timeout)

            if self._handler_tasks.idle:
                await self._on_idle()
            else:
                # Yield to the event loop to allow other tasks to run.
                await asyncio.sleep(0)

    async def _on_idle(self):
        if self._idle_handlers:
            await gather_no_raise(*[
                self._handler_tasks.push(idle_handler) for idle_handler in self._idle_handlers
            ])

        # Avoid trashing the CPU if there's nothing to do.
        await asyncio.sleep(self.idle_sleep)

    async def _push_scheduled(self, dt: datetime.datetime):
        while (next_scheduled_dt := self._scheduler_queue.peek_next_event_dt()) and next_scheduled_dt <= dt:
            next_scheduled_dt, job = self._scheduler_queue.pop()
            # Push scheduled job into the task pool for processing.
            await self._handler_tasks.push(functools.partial(self._execute_scheduled, next_scheduled_dt, job))

    async def _push_events(self, dt: datetime.datetime):
        # Pop events and feed the pool.
        for source, evnt in self._event_mux.pop_while(dt):
            # Check that events from the same source are returned in order.
            prev_event_dt = self._prev_event_dt.get(source)
            if prev_event_dt is not None and evnt.when < prev_event_dt:
                self.on_error(logs.StructuredMessage(
                    "Events returned out of order", source=type(source), previous=prev_event_dt, current=evnt.when
                ))
                # TODO: Not ignoring out-of-order events should be an option.
                continue
            self._prev_event_dt[source] = evnt.when

            # Push event into the task pool for processing.
            await self._handler_tasks.push(
                functools.partial(self._dispatch_event, EventDispatch(
                    event=evnt,
                    handlers=self._event_handlers[source]
                ))
            )


async def gather_no_raise(*awaitables):
    await asyncio.gather(*[await_no_raise(awaitable) for awaitable in awaitables])


async def await_no_raise(coro: Awaitable[Any], message: str = "Unhandled exception"):
    with helpers.no_raise(logger, message):
        await coro


def realtime_dispatcher(max_concurrent: int = 50) -> RealtimeDispatcher:
    """
    Creates an event dispatcher suitable for live trading.

    :param max_concurrent: The maximum number of events to process concurrently.
    """
    return RealtimeDispatcher(max_concurrent=max_concurrent)


def backtesting_dispatcher(max_concurrent: int = 50) -> BacktestingDispatcher:
    """
    Creates an event dispatcher suitable for backtesting.

    :param max_concurrent: The maximum number of events to process concurrently.
    """
    return BacktestingDispatcher(max_concurrent=max_concurrent)
