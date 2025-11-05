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

from typing import List, Optional
import abc
import datetime
from collections import deque

from . import dt


class Producer:
    """
    【中文说明】生产者基类
    
    【功能描述】
    生产者是事件源（EventSource）或其组的主动部分，负责生成和推送事件。
    生产者与事件分发器（EventDispatcher）协同工作，通过initialize、main、finalize三个生命周期方法
    管理事件生成过程。具体使用方式请参考 EventDispatcher.run() 方法。
    
    【生命周期】
    1. initialize(): 初始化阶段，用于建立连接、加载配置等准备工作
    2. main(): 主循环阶段，持续生成和推送事件
    3. finalize(): 清理阶段，用于释放资源、关闭连接等收尾工作
    
    【注意事项】
    - 这是一个抽象基类，不应直接使用，需要子类实现具体逻辑
    - 生产者通常与事件源关联，通过事件源将事件传递给分发器
    - 异步设计，所有方法都是异步的，支持并发执行

    Base class for producers.

    A producer is the active part of an :class:`basana.EventSource` or a group of them.
    Take a look at :meth:`EventDispatcher.run` for details on how producers are used.

    .. note::

        This is a base class and should not be used directly.
    """

    async def initialize(self):
        """
        【中文说明】初始化生产者
        
        【功能描述】
        执行生产者的初始化工作，如建立网络连接、加载配置文件、初始化资源等。
        该方法在生产者开始运行前被事件分发器调用。
        
        【重写说明】
        子类应该重写此方法来实现特定的初始化逻辑。
        
        【注意事项】
        - 异步方法，可以执行异步操作
        - 如果初始化失败，应该抛出异常
        - 在main()方法执行前调用
        
        Override to perform initialization.
        """
        pass

    async def main(self):
        """
        【中文说明】运行生产者的主循环
        
        【功能描述】
        执行生产者的主要工作循环，持续生成事件并推送到关联的事件源。
        该方法通常包含一个无限循环，直到生产者被停止。
        
        【重写说明】
        子类必须重写此方法来实现具体的事件生成逻辑。
        
        【注意事项】
        - 异步方法，通常包含异步等待操作
        - 应该定期检查停止条件，以便优雅退出
        - 可以通过事件源的push()方法推送事件
        
        Override to run the loop that produces events.
        """
        pass

    async def finalize(self):
        """
        【中文说明】清理生产者资源
        
        【功能描述】
        执行生产者的清理工作，如关闭连接、释放资源、保存状态等。
        该方法在生产者停止运行后被事件分发器调用。
        
        【重写说明】
        子类应该重写此方法来实现特定的清理逻辑。
        
        【注意事项】
        - 异步方法，可以执行异步操作
        - 即使初始化或主循环失败，也会被调用
        - 应该确保资源的正确释放
        
        Override to perform cleanup.
        """
        pass


class Event:
    """
    【中文说明】事件基类
    
    【功能描述】
    事件是在特定时间点发生的任何事情，是事件驱动架构的核心数据结构。
    不同类型的事件代表不同的市场活动或系统状态变化，如：
    - 订单簿更新
    - 新交易发生
    - 订单状态变更  
    - 新的K线柱（蜡烛图/OHLC）生成
    - 其他自定义事件
    
    【核心属性】
    - when: 事件发生的时间点，必须包含时区信息
    
    【注意事项】
    - 这是一个抽象基类，不应直接使用，需要子类化实现具体事件类型
    - 所有事件都必须有时间戳，且必须有时区信息
    - 事件应该是不可变的数据结构

    Base class for events.

    An event is something that occurs at a specific point in time. There are many different types of events:

    * An update to an order book.
    * A new trade.
    * An order update.
    * A new bar (candlestick/ohlc).
    * Others

    :param when: The datetime when the event occurred. It must have timezone information set.

    .. note::

        This is a base class and should not be used directly.
    """

    def __init__(self, when: datetime.datetime):
        """
        【中文说明】初始化事件对象
        
        【功能描述】
        创建事件实例，设置事件发生的时间点。
        
        【参数说明】
        - when: datetime.datetime - 事件发生的时间，必须包含时区信息
        
        【验证检查】
        - 检查时间是否包含时区信息，防止使用朴素时间戳
        
        【异常情况】
        - 如果when参数不包含时区信息，会抛出AssertionError
        
        【使用示例】
        >>> event = Event(datetime.datetime.now(datetime.timezone.utc))
        """
        # 验证时间戳必须包含时区信息，防止使用朴素时间戳导致的时区混淆
        assert not dt.is_naive(when), f"{when} should have timezone information set"

        #: The datetime when the event occurred.
        self.when: datetime.datetime = when


class EventSource(metaclass=abc.ABCMeta):
    """
    【中文说明】事件源抽象基类
    
    【功能描述】
    事件源是事件驱动架构中的核心组件，负责提供事件给事件分发器（EventDispatcher）处理。
    它定义了事件源的标准接口，确保不同类型的事件源可以统一被事件分发器使用。
    
    【核心职责】
    - 提供事件获取接口：通过pop()方法返回下一个可用事件
    - 管理事件生产者：可关联一个生产者（Producer）来主动生成事件
    - 支持多种事件源实现：可以是队列、文件、网络流等不同来源
    
    【架构角色】
    - 在事件驱动架构中充当事件提供者
    - 与事件分发器（EventDispatcher）协同工作
    - 支持同步和异步事件源实现
    
    【注意事项】
    - 这是一个抽象基类（ABC），必须被子类化实现具体逻辑
    - pop()方法应该尽快返回，避免阻塞事件分发循环
    - 可以关联生产者来主动生成事件，也可以被动提供事件

    Base class for event sources.

    This class declares the interface that is required by the :class:`basana.EventDispatcher` to gather events for
    processing.

    :param producer: An optional producer associated with this event source.
    """

    def __init__(self, producer: Optional[Producer] = None):
        """
        【中文说明】初始化事件源
        
        【功能描述】
        创建事件源实例，可选择性地关联一个生产者。
        
        【参数说明】
        - producer: Optional[Producer] - 可选的生产者实例，负责主动生成事件
          如果提供，事件分发器会启动该生产者来生成事件
        
        【使用场景】
        - 主动事件源：提供producer参数，生产者主动推送事件
        - 被动事件源：不提供producer参数，事件源被动提供事件（如从队列中读取）
        
        【注意事项】
        - 生产者不是必需的，事件源可以独立工作
        - 如果提供生产者，事件分发器会管理其生命周期
        """
        # 关联的生产者实例，负责主动生成事件
        self.producer = producer

    @abc.abstractmethod
    def pop(self) -> Optional[Event]:
        """
        【中文说明】获取下一个事件
        
        【功能描述】
        从事件源中获取下一个可用的事件。如果没有事件可用，返回None。
        这是事件分发器获取事件的主要接口。
        
        【返回值】
        - Optional[Event]: 下一个事件实例，如果没有事件则返回None
        
        【性能要求】
        - 必须尽快返回，避免阻塞事件分发循环
        - 在无事件时应立即返回None，而不是等待
        
        【实现要求】
        - 抽象方法，子类必须实现此方法
        - 应该遵循先进先出（FIFO）原则，除非有特殊需求
        - 应该处理事件源的内部状态管理
        
        【使用示例】
        >>> event = event_source.pop()
        >>> if event:
        ...     process_event(event)

        Override to return the next event, or None if there are no events available.

        This method is used by the :class:`basana.EventDispatcher` during the event dispatch loop so **it should return
        as soon as possible**.
        """
        raise NotImplementedError()


class FifoQueueEventSource(EventSource):
    """
    【中文说明】先进先出队列事件源
    
    【功能描述】
    基于双端队列（deque）实现的先进先出（FIFO）事件源。
    提供简单的事件队列管理，支持事件的入队（push）和出队（pop）操作。
    
    【核心特性】
    - 线程安全：在单线程环境中安全使用
    - 高性能：基于collections.deque实现，入队出队操作高效
    - 灵活性：支持初始事件列表和动态事件添加
    
    【使用场景】
    - 内存中的事件缓冲队列
    - 事件回放和模拟测试
    - 简单的事件处理管道
    
    【注意事项】
    - 适用于单线程环境，多线程环境需要额外同步
    - 事件存储在内存中，大量事件可能消耗较多内存
    - 队列为空时pop()方法返回None

    A FIFO queue event source.

    :param producer: An optional producer associated with this event source.
    :param events: An optional list of initial events.
    """
    def __init__(self, producer: Optional[Producer] = None, events: List[Event] = []):
        """
        【中文说明】初始化FIFO队列事件源
        
        【功能描述】
        创建FIFO队列事件源实例，可选择性地关联生产者和提供初始事件列表。
        
        【参数说明】
        - producer: Optional[Producer] - 可选的生产者实例
        - events: List[Event] - 可选的初始事件列表，会按顺序添加到队列中
        
        【内部实现】
        - 使用collections.deque作为底层队列存储
        - 支持高效的队首出队和队尾入队操作
        
        【使用示例】
        >>> # 创建空队列事件源
        >>> queue_source = FifoQueueEventSource()
        >>> 
        >>> # 创建带有初始事件的事件源
        >>> initial_events = [Event(datetime1), Event(datetime2)]
        >>> queue_source = FifoQueueEventSource(events=initial_events)
        """
        # 调用父类初始化，设置生产者
        super().__init__(producer)
        # 使用双端队列存储事件，支持高效的入队出队操作
        self._queue = deque(events)

    def push(self, event: Event):
        """
        【中文说明】将事件添加到队列末尾
        
        【功能描述】
        将新事件添加到FIFO队列的末尾，等待后续被pop()方法取出。
        
        【参数说明】
        - event: Event - 要添加到队列的事件实例
        
        【操作特性】
        - 时间复杂度：O(1)，高效操作
        - 队列顺序：事件按照添加顺序排列，先添加的先被处理
        
        【使用场景】
        - 生产者生成事件后推送到队列
        - 从外部源接收事件后缓冲到队列
        - 测试时手动添加模拟事件
        
        【注意事项】
        - 事件会被添加到队列末尾
        - 不限制队列大小，需要注意内存使用
        - 事件应该包含有效的时间戳

        Adds an event to the end of the queue.
        """
        # 将事件添加到队列末尾，保持先进先出顺序
        self._queue.append(event)

    def pop(self) -> Optional[Event]:
        """
        【中文说明】从队列开头移除并返回下一个事件
        
        【功能描述】
        从FIFO队列的开头移除并返回下一个可用事件。
        如果队列为空，返回None。
        
        【返回值】
        - Optional[Event]: 队列中的下一个事件，如果队列为空则返回None
        
        【操作特性】
        - 时间复杂度：O(1)，高效操作
        - 队列行为：严格遵循先进先出原则
        - 空队列处理：队列为空时立即返回None，不阻塞
        
        【内部实现】
        - 使用deque.popleft()方法从队列开头移除元素
        - 检查队列是否为空，避免在空队列上操作
        
        【使用示例】
        >>> while True:
        ...     event = queue_source.pop()
        ...     if event is None:
        ...         break  # 队列为空，退出循环
        ...     process_event(event)

        Removes and returns the next event in the queue.
        """
        # 初始化返回值为None，表示队列可能为空
        ret = None
        # 检查队列是否包含事件
        if self._queue:
            # 从队列开头移除并返回第一个事件
            ret = self._queue.popleft()
        # 返回事件或None（如果队列为空）
        return ret
