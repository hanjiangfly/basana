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

"""
【中文说明】辅助工具模块

【功能描述】
提供异步编程、数值计算、HTTP会话管理等通用辅助工具。
包含任务管理、数值处理、上下文管理等实用功能。

【核心组件】
- TaskGroup：异步任务组管理
- TaskPool：异步任务池管理
- 数值处理：Decimal数值的舍入和截断
- 上下文管理器：异常抑制、HTTP会话管理
- 工具函数：弃用警告、类路径获取

【使用场景】
- 异步任务并发管理
- 金融数值精确计算
- HTTP客户端会话管理
- 代码重构和弃用管理

【注意事项】
- 使用Decimal进行精确数值计算
- 异步任务管理需要正确处理异常
- 遵循Python异步编程最佳实践
"""

from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
import asyncio
import contextlib
import decimal
import logging
import uuid
import warnings

import aiohttp

from basana.core import logs


class TaskGroup:
    """
    【中文说明】异步任务组管理器
    
    【功能描述】
    管理一组异步任务的上下文管理器，提供任务创建、等待和取消功能。
    类似于Python 3.11+的asyncio.TaskGroup，但提供更细粒度的控制。
    
    【核心特性】
    - 异步上下文管理器：支持async with语法
    - 任务生命周期管理：自动等待任务完成
    - 异常处理：正确处理任务异常
    - 任务取消：支持手动取消所有任务
    
    【使用场景】
    - 并发执行多个异步任务
    - 需要统一管理任务生命周期的场景
    - 异步资源清理和任务取消
    
    【注意事项】
    - 在退出上下文管理器时会自动等待所有任务完成
    - 支持任务取消和异常处理
    - 遵循异步编程最佳实践
    """

    def __init__(self):
        """
        【中文说明】初始化任务组
        
        【功能描述】
        创建任务组实例，初始化内部状态。
        
        【内部状态】
        - _tasks: List[asyncio.Task] - 任务列表
        - _exiting: bool - 退出状态标志
        """
        # 任务列表
        self._tasks = []
        # 退出状态标志
        self._exiting = False

    async def __aenter__(self) -> "TaskGroup":
        """
        【中文说明】异步上下文管理器入口
        
        【功能描述】
        进入异步上下文管理器，返回任务组实例。
        
        【返回值】
        - TaskGroup: 当前任务组实例
        
        【使用场景】
        - 在async with语句中使用
        - 开始任务组生命周期管理
        """
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """
        【中文说明】异步上下文管理器出口
        
        【功能描述】
        退出异步上下文管理器，等待所有任务完成并处理异常。
        
        【参数说明】
        - exc_type: 异常类型
        - exc_value: 异常值
        - traceback: 异常追踪信息
        
        【操作流程】
        1. 设置退出状态标志
        2. 如果没有异常，等待所有任务完成
        3. 取消所有未完成的任务
        4. 等待被取消的任务完成
        
        【注意事项】
        - 即使有异常也会等待任务完成
        - 取消任务时不会抛出异常
        """
        # 设置退出状态标志
        self._exiting = True

        try:
            # 如果没有异常，等待所有任务完成
            if not exc_type:
                await asyncio.gather(*self._tasks)
        finally:
            # 取消所有未完成的任务
            pending = self._cancel()
            if pending:
                # 等待被取消的任务完成，不抛出异常
                await asyncio.gather(*pending, return_exceptions=True)

    def _cancel(self) -> List[asyncio.Task]:
        """
        【中文说明】取消所有未完成的任务
        
        【功能描述】
        内部方法，取消所有未完成的任务并返回待处理任务列表。
        
        【返回值】
        - List[asyncio.Task]: 被取消的待处理任务列表
        
        【操作流程】
        1. 找出所有未完成的任务
        2. 取消这些任务
        3. 返回被取消的任务列表
        
        【注意事项】
        - 这是一个内部方法
        - 取消任务不会立即停止执行
        """
        # 找出所有未完成的任务
        pending = [task for task in self._tasks if not task.done()]
        # 取消这些任务
        for task in pending:
            if not task.done():
                task.cancel()
        return pending

    def create_task(self, coro) -> asyncio.Task:
        """
        【中文说明】创建新任务
        
        【功能描述】
        在任务组中创建新的异步任务。
        
        【参数说明】
        - coro: 协程对象
        
        【返回值】
        - asyncio.Task: 创建的异步任务
        
        【验证检查】
        - 确保不在退出状态下创建任务
        
        【注意事项】
        - 任务会自动添加到任务组管理
        - 在退出状态下不能创建新任务
        """
        # 验证不在退出状态下
        assert not self._exiting
        # 创建异步任务
        ret = asyncio.create_task(coro)
        # 添加到任务列表
        self._tasks.append(ret)
        return ret

    def cancel(self):
        """
        【中文说明】取消所有任务
        
        【功能描述】
        手动取消任务组中的所有任务。
        
        【使用场景】
        - 需要提前终止所有任务的场景
        - 错误处理时清理任务
        
        【注意事项】
        - 取消后任务不会立即停止
        - 需要等待任务完成清理
        """
        self._cancel()


class TaskPool:
    """
    【中文说明】异步任务池管理器
    
    【功能描述】
    管理异步任务池，控制并发任务数量和队列大小。
    提供任务提交、取消和等待完成等功能，支持动态任务创建。
    
    【核心特性】
    - 并发控制：限制同时运行的任务数量
    - 队列管理：控制待执行任务的队列大小
    - 动态扩展：根据需要创建新的工作线程
    - 优雅关闭：支持任务取消和等待完成
    
    【参数说明】
    - max_tasks: int - 最大并发任务数量
    - max_queue_size: Optional[int] - 最大队列大小，None表示使用max_tasks
    
    【使用场景】
    - 控制异步任务的并发数量
    - 处理大量异步任务的批量执行
    - 资源受限环境下的任务调度
    
    【注意事项】
    - 队列满时会阻塞push操作
    - 支持Python 3.12+的急切任务特性
    - 单个任务失败不会影响其他任务

    A class for managing a pool of asyncio tasks.

    :param size: The maximum number of tasks to be running at the same time.
    :param max_queue_size: The maximum number of coroutine functions to be waiting in the queue for execution.
    """

    def __init__(self, max_tasks: int, max_queue_size: Optional[int] = None):
        """
        【中文说明】初始化任务池
        
        【功能描述】
        创建任务池实例，设置并发限制和队列大小。
        
        【参数说明】
        - max_tasks: int - 最大并发任务数量，必须大于0
        - max_queue_size: Optional[int] - 最大队列大小，None表示使用max_tasks
        
        【验证检查】
        - max_tasks必须大于0
        - max_queue_size必须大于0或为None
        
        【内部状态】
        - _max_tasks: 最大任务数
        - _queue: 任务队列（惰性初始化）
        - _tasks: 任务字典，按名称索引
        - _queue_timeout: 队列获取超时时间
        - _active: 当前活跃任务数
        """
        # 验证最大任务数必须大于0
        assert max_tasks > 0, "Invalid max_tasks"
        # 验证队列大小必须大于0或为None
        assert max_queue_size is None or max_queue_size > 0, "Invalid max_queue_size"

        # 最大并发任务数量
        self._max_tasks = max_tasks
        # 任务队列（惰性初始化）
        self._queue = LazyProxy(
            lambda: asyncio.Queue(maxsize=max_tasks if max_queue_size is None else max_queue_size)
        )
        # 任务字典，按名称索引
        self._tasks: Dict[str, asyncio.Task] = {}
        # 队列获取超时时间（秒）
        self._queue_timeout = 1.0
        # 当前活跃任务数
        self._active = 0

    @property
    def idle(self) -> bool:
        """
        【中文说明】空闲状态检查
        
        【功能描述】
        检查任务池是否处于空闲状态（没有正在执行的任务和等待的任务）。
        
        【返回值】
        - bool: 如果没有任何任务在执行且队列为空，返回True；否则返回False
        
        【使用场景】
        - 检查任务池是否完成所有工作
        - 决定是否可以安全关闭任务池
        - 监控任务池状态
        
        【注意事项】
        - 空闲状态表示可以安全关闭任务池
        - 活跃任务数为0且队列为空时才返回True

        True if there are no coroutines being executed and there are no coroutines waiting in the queue,
        False otherwise.
        """
        return self._active == 0 and self._queue.empty()

    async def push(self, coroutine_func: Callable[[], Awaitable[Any]]):
        """
        【中文说明】提交任务到任务池
        
        【功能描述】
        将协程函数提交到任务池队列，如果队列满则阻塞等待。
        根据需要动态创建工作线程。
        
        【参数说明】
        - coroutine_func: Callable[[], Awaitable[Any]] - 协程函数，不接受参数
        
        【操作流程】
        1. 将协程函数放入队列
        2. 如果没有空闲任务且未达到最大任务数，创建新任务
        3. 使用UUID作为任务名称确保唯一性
        
        【使用场景】
        - 批量提交异步任务
        - 控制任务并发执行
        - 动态扩展工作线程
        
        【注意事项】
        - 队列满时会阻塞
        - 支持Python 3.12+的急切任务特性
        - 任务函数不应接受参数

        Adds a coroutine function to the queue. It may block if the queue is full.

        :param coroutine_func: The coroutine function to be added to the task pool.
        """

        # 将协程函数放入队列
        await self._queue.put(coroutine_func)

        # 根据需要创建新任务
        # 计算空闲任务数
        idle_tasks = len(self._tasks) - self._active
        # 如果没有空闲任务且未达到最大任务数，创建新任务
        if idle_tasks == 0 and len(self._tasks) < self._max_tasks:
            # 生成唯一任务名称
            task_name = uuid.uuid4().hex
            # 创建任务主循环
            task = asyncio.create_task(self._task_main(task_name))
            # 检查任务是否已完成（Python >= 3.12的急切任务特性）
            # 在注册任务前检查，因为如果启用了急切任务，任务可能已经运行完成
            if not task.done() and task_name not in self._tasks:
                # 注册任务到任务字典
                self._tasks[task_name] = task

    def cancel(self):
        """
        【中文说明】取消所有任务
        
        【功能描述】
        请求取消任务池中的所有任务并清空队列。
        
        【操作流程】
        1. 取消所有运行中的任务
        2. 清空任务队列
        3. 标记所有队列任务为完成
        
        【使用场景】
        - 紧急停止所有任务
        - 资源清理和关闭
        - 错误处理时的任务清理
        
        【注意事项】
        - 取消后任务不会立即停止
        - 需要调用wait()等待任务完成清理

        Requests all tasks in the pool to be canceled and clears the queue.
        """
        # 取消所有运行中的任务
        for task in self._tasks.values():
            task.cancel()

        # 清空任务队列
        while self._queue.qsize():
            self._queue.get_nowait()
            self._queue.task_done()

    async def wait(self, timeout: Optional[Union[int, float]] = None) -> bool:
        """
        【中文说明】等待所有任务完成
        
        【功能描述】
        等待任务池中的所有任务完成，支持超时设置。
        
        【参数说明】
        - timeout: Optional[Union[int, float]] - 超时时间（秒），None表示无限等待
        
        【返回值】
        - bool: 如果所有任务在超时前完成返回True，否则返回False
        
        【使用场景】
        - 等待批量任务完成
        - 优雅关闭任务池
        - 超时控制的任务执行
        
        【注意事项】
        - 超时后返回False，但任务仍在运行
        - 需要结合cancel()使用来完全停止任务

        Waits for all tasks in the pool to complete.

        :param timeout: The maximum number of seconds to wait for tasks to complete. If None, wait indefinitely.
        :returns: Returns True if all the coroutines in the queue have been processed, False otherwise.
        """

        ret = False
        try:
            # 等待队列中的所有任务完成
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
            ret = True
        except asyncio.TimeoutError:
            # 超时后返回False
            pass
        return ret

    async def _task_main(self, task_name: str):
        """
        【中文说明】任务主循环
        
        【功能描述】
        工作线程的主循环，从队列获取任务并执行。
        支持Python 3.12+的急切任务特性。
        
        【参数说明】
        - task_name: str - 任务名称，用于任务注册
        
        【操作流程】
        1. 注册当前任务（处理急切任务情况）
        2. 循环从队列获取任务
        3. 执行任务并处理异常
        4. 更新活跃任务计数
        5. 标记任务完成
        
        【异常处理】
        - 单个任务失败不会影响工作线程
        - 使用pass忽略任务异常
        
        【注意事项】
        - 这是一个内部方法
        - 处理竞态条件和队列超时
        - 支持优雅退出
        """
        # 获取当前任务
        current_task = asyncio.current_task()
        # 如果当前任务尚未注册，进行注册（处理Python >= 3.12的急切任务特性）
        if current_task not in self._tasks:
            assert current_task is not None
            self._tasks[task_name] = current_task

        try:
            eof = False
            while not eof:

                try:
                    # 从队列获取任务，支持超时
                    coro_func = await asyncio.wait_for(self._queue.get(), timeout=self._queue_timeout)
                except asyncio.TimeoutError:
                    # 处理队列超时情况
                    # 这个双重检查是为了解决竞态条件问题：
                    # 即使队列中有项目，上面的pop操作也可能超时
                    # 2025-10-16 15:08:30 - DEBUG - basana.core.helpers - Task pop timed out {"total_tasks": 1, "active_tasks": 0, "queue_size": 2}
                    # 2025-10-16 15:08:30 - DEBUG - basana.core.helpers - Task is about to exit {"total_tasks": 0, "active_tasks": 0, "queue_size": 2}
                    # 检查队列是否真正为空
                    eof = self._queue.empty()
                    continue

                try:
                    # 增加活跃任务计数
                    self._active += 1
                    # 执行协程函数
                    await coro_func()
                except Exception:
                    # 单个协程失败不应导致工作线程崩溃
                    pass
                finally:
                    # 减少活跃任务计数
                    self._active -= 1
                    # 标记任务完成
                    self._queue.task_done()
        finally:
            # 完成后从任务注册表中移除自己
            self._tasks.pop(task_name)


@contextlib.contextmanager
def no_raise(logger: logging.Logger, msg: str, **kwargs):
    """
    【中文说明】异常抑制上下文管理器
    
    【功能描述】
    抑制代码块中的所有异常，记录错误日志但不抛出异常。
    用于处理非关键性操作，避免异常中断主流程。
    
    【参数说明】
    - logger: logging.Logger - 日志记录器
    - msg: str - 日志消息
    - **kwargs: 额外的日志参数
    
    【使用场景】
    - 非关键性操作的错误处理
    - 避免异常中断主流程
    - 记录错误信息但不中断执行
    
    【注意事项】
    - 使用异常级别记录错误
    - 不会中断程序执行
    - 适用于可恢复的错误情况
    """
    try:
        yield
    except Exception as e:
        # 构建日志参数
        log_args = {"exception": e}
        log_args.update(kwargs)
        # 记录异常日志
        logger.exception(logs.StructuredMessage(msg, **log_args))


@contextlib.asynccontextmanager
async def use_or_create_session(session: Optional[aiohttp.ClientSession] = None, proxy: Optional[str] = None):
    """
    【中文说明】HTTP会话管理上下文管理器
    
    【功能描述】
    管理aiohttp.ClientSession的异步上下文管理器。
    如果提供了会话则使用现有会话，否则创建新会话。
    支持代理配置，包括SOCKS5代理。
    
    【参数说明】
    - session: Optional[aiohttp.ClientSession] - 可选的现有会话
    - proxy: Optional[str] - 代理URL，支持HTTP/HTTPS/SOCKS5代理
    
    【使用场景】
    - HTTP客户端会话管理
    - 会话复用和资源管理
    - 避免会话泄漏
    - 通过代理访问网络资源
    
    【注意事项】
    - 如果创建新会话，会自动管理其生命周期
    - 使用现有会话时不会自动关闭
    - 遵循异步上下文管理器协议
    - 支持SOCKS5代理需要安装aiohttp_socks库
    """
    if session:
        # 使用现有会话
        yield session
    else:
        # 创建新会话并管理其生命周期
        if proxy:
            # 支持代理配置
            if proxy.startswith('socks5://'):
                # 使用SOCKS5代理
                from aiohttp_socks import ProxyConnector
                connector = ProxyConnector.from_url(proxy)
            else:
                # 使用HTTP/HTTPS代理
                connector = aiohttp.TCPConnector()
            async with aiohttp.ClientSession(connector=connector) as new_session:
                yield new_session
        else:
            # 无代理，使用默认连接器
            async with aiohttp.ClientSession() as new_session:
                yield new_session


def round_decimal(value: Decimal, precision: int, rounding=None) -> Decimal:
    """
    【中文说明】Decimal数值舍入
    
    【功能描述】
    对Decimal数值进行舍入操作，支持自定义舍入模式。
    使用decimal模块的quantize方法进行精确舍入。
    
    【参数说明】
    - value: Decimal - 要舍入的数值
    - precision: int - 精度（小数点后的位数）
    - rounding: 可选舍入模式，来自decimal模块
    
    【返回值】
    - Decimal: 舍入后的数值
    
    【使用场景】
    - 金融数值精确计算
    - 价格和数量的格式化
    - 数值精度控制
    
    【注意事项】
    - 使用Decimal进行精确计算
    - 支持各种舍入模式（四舍五入、向上舍入等）

    Rounds a decimal value.

    :param value: The value to round.
    :param precision: The number of digits after the decimal point.
    :param rounding: An optional rounding option from the :mod:`decimal` module.
    :returns: The rounded value.
    """
    return value.quantize(Decimal(f"1e-{precision}"), rounding=rounding)


def truncate_decimal(value: Decimal, precision: int) -> Decimal:
    """
    【中文说明】Decimal数值截断
    
    【功能描述】
    对Decimal数值进行截断操作，直接丢弃多余的小数位。
    使用ROUND_DOWN模式实现截断效果。
    
    【参数说明】
    - value: Decimal - 要截断的数值
    - precision: int - 精度（小数点后的位数）
    
    【返回值】
    - Decimal: 截断后的数值
    
    【使用场景】
    - 金融计算中的数值截断
    - 避免舍入误差的累积
    - 符合特定交易规则的计算
    
    【注意事项】
    - 直接丢弃多余小数位，不进行舍入
    - 使用ROUND_DOWN舍入模式

    Truncates a decimal value.

    :param value: The value to truncate.
    :param precision: The number of digits after the decimal point.
    :returns: The truncated value.
    """
    return round_decimal(value, precision, rounding=decimal.ROUND_DOWN)


def deprecation_warning(message: str):
    """
    【中文说明】弃用警告
    
    【功能描述】
    发出弃用警告，提醒用户某个功能即将被移除或替换。
    使用DeprecationWarning类别和适当的堆栈级别。
    
    【参数说明】
    - message: str - 警告消息
    
    【使用场景】
    - 标记即将废弃的API
    - 提醒用户迁移到新版本
    - 代码重构和版本升级
    
    【注意事项】
    - 使用DeprecationWarning类别
    - 设置stacklevel=2以指向调用者
    - 遵循Python弃用警告最佳实践
    """
    warnings.warn(message, DeprecationWarning, stacklevel=2)


def classpath(obj: object):
    """
    【中文说明】获取对象的类路径
    
    【功能描述】
    获取对象的完整类路径，包括模块名和类名。
    用于日志记录、序列化和调试。
    
    【参数说明】
    - obj: object - 任意Python对象
    
    【返回值】
    - str: 对象的完整类路径（格式：module.ClassName）
    
    【使用场景】
    - 日志记录中的对象标识
    - 序列化和反序列化
    - 调试和错误追踪
    
    【注意事项】
    - 对于内置类型可能返回不完整的路径
    - 支持嵌套类和模块路径
    """
    cls = obj.__class__
    module = cls.__module__
    # 构建类路径部分
    parts = [str(module), cls.__qualname__] if module else [cls.__qualname__]
    # 使用点号连接
    return ".".join(parts)


class LazyProxy:
    """
    【中文说明】惰性代理类
    
    【功能描述】
    实现惰性初始化的代理模式，延迟对象的创建直到第一次访问。
    提供透明的属性访问，就像直接访问目标对象一样。
    
    【核心特性】
    - 惰性初始化：对象在第一次访问时创建
    - 透明代理：支持所有属性访问操作
    - 状态跟踪：可以检查初始化状态
    
    【使用场景】
    - 昂贵的资源初始化
    - 循环依赖解决
    - 配置驱动的对象创建
    
    【注意事项】
    - 工厂函数在第一次属性访问时调用
    - 支持所有Python魔术方法
    - 线程安全性需要额外处理
    """

    def __init__(self, factory):
        """
        【中文说明】初始化惰性代理
        
        【功能描述】
        创建惰性代理实例，设置工厂函数。
        
        【参数说明】
        - factory: 工厂函数，用于创建目标对象
        
        【内部状态】
        - _factory: 工厂函数
        - _obj: 目标对象（初始为None）
        """
        # 工厂函数
        self._factory = factory
        # 目标对象（惰性初始化）
        self._obj = None

    @property
    def initialized(self):
        """
        【中文说明】初始化状态检查
        
        【功能描述】
        检查目标对象是否已经初始化。
        
        【返回值】
        - bool: 如果目标对象已初始化返回True，否则返回False
        
        【使用场景】
        - 检查对象是否已创建
        - 避免重复初始化
        - 调试和状态监控
        """
        return self._obj is not None

    @property
    def obj(self):
        """
        【中文说明】获取目标对象
        
        【功能描述】
        获取目标对象，如果未初始化则调用工厂函数创建。
        
        【返回值】
        - Any: 目标对象
        
        【操作流程】
        1. 检查对象是否已初始化
        2. 如果未初始化，调用工厂函数创建对象
        3. 返回目标对象
        
        【注意事项】
        - 工厂函数只在第一次访问时调用
        - 后续访问直接返回已创建的对象
        """
        if self._obj is None:
            # 调用工厂函数创建对象
            self._obj = self._factory()
        return self._obj

    def __getattr__(self, name):
        """
        【中文说明】属性访问代理
        
        【功能描述】
        将属性访问代理到目标对象。
        支持所有属性访问操作（方法调用、属性读取等）。
        
        【参数说明】
        - name: str - 属性名称
        
        【返回值】
        - Any: 目标对象的属性值
        
        【使用场景】
        - 透明的对象访问
        - 方法调用代理
        - 属性读取代理
        
        【注意事项】
        - 所有属性访问都会触发对象初始化（如果未初始化）
        - 支持Python的所有属性访问操作
        """
        return getattr(self.obj, name)
