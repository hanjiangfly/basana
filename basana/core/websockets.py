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

from typing import Any, Dict, List, Optional, Set
import abc
import asyncio
import json
import logging
import time

import aiohttp

from . import event, helpers, logs


# 日志记录器，用于记录WebSocket相关的操作和错误
logger = logging.getLogger(__name__)


# Base class for event sources that generate events from websocket messages.
class ChannelEventSource(event.FifoQueueEventSource):
    """
    【中文说明】通道事件源基类
    
    【功能描述】
    从WebSocket消息生成事件的事件源基类。
    继承自FifoQueueEventSource，提供基于通道的事件处理机制。
    
    【架构角色】
    - 将WebSocket消息转换为事件
    - 管理事件队列和分发
    - 支持多通道事件处理
    
    【使用场景】
    - 交易所实时数据订阅
    - 实时交易事件处理
    - 市场数据流处理
    
    【注意事项】
    - 这是一个抽象基类，需要子类实现具体逻辑
    - 需要实现push_from_message方法来处理消息
    """

    def __init__(self, producer: event.Producer):
        """
        【中文说明】初始化通道事件源
        
        【功能描述】
        创建通道事件源实例，关联生产者。
        
        【参数说明】
        - producer: event.Producer - 关联的事件生产者
        
        【内部操作】
        - 调用父类FifoQueueEventSource的初始化方法
        - 设置生产者用于事件生成
        """
        # 调用父类初始化，设置生产者
        super().__init__(producer=producer)

    @abc.abstractmethod
    async def push_from_message(self, message: dict):
        """
        【中文说明】从消息推送事件
        
        【功能描述】
        抽象方法，将WebSocket消息转换为事件并推送到事件队列。
        
        【参数说明】
        - message: dict - WebSocket消息，通常是JSON格式的字典
        
        【实现要求】
        - 子类必须实现此方法
        - 应该解析消息并创建相应的事件
        - 使用push()方法将事件添加到队列
        
        【注意事项】
        - 这是一个异步方法
        - 需要处理消息解析和事件创建
        """
        raise NotImplementedError()


class WebSocketClient(event.Producer, metaclass=abc.ABCMeta):
    """
    【中文说明】WebSocket客户端基类
    
    【功能描述】
    基于通道的WebSocket客户端基类，提供完整的WebSocket连接管理。
    支持连接建立、消息处理、重连机制和通道订阅管理。
    
    【WebSocket协议特性】
    - 全双工通信：客户端和服务器可以同时发送和接收数据
    - 低延迟：相比HTTP轮询，实时性更好
    - 持久连接：建立连接后保持打开状态
    
    【核心功能】
    - 自动重连和退避机制
    - 心跳保活连接
    - 多通道订阅管理
    - 消息处理和事件分发
    
    【参数说明】
    - url: str - WebSocket服务器URL
    - session: Optional[aiohttp.ClientSession] - 可选的HTTP会话
    - config_overrides: dict - 配置覆盖项
    - heartbeat: float - 心跳间隔（秒），默认30秒
    
    【使用场景】
    - 交易所实时数据订阅
    - 实时交易执行
    - 市场行情推送
    - 订单状态更新

    Base class for channel based web socket clients.
    """

    def __init__(
            self, url: str, session: Optional[aiohttp.ClientSession] = None, config_overrides: dict = {},
            heartbeat: float = 30
    ):
        """
        【中文说明】初始化WebSocket客户端
        
        【功能描述】
        创建WebSocket客户端实例，设置连接参数和初始状态。
        
        【参数说明】
        - url: str - WebSocket服务器URL
        - session: Optional[aiohttp.ClientSession] - 可选的HTTP会话，如果为None则自动创建
        - config_overrides: dict - 配置覆盖项，用于自定义连接参数
        - heartbeat: float - 心跳间隔（秒），用于保持连接活跃
        
        【内部状态】
        - _url: WebSocket服务器URL
        - _session: HTTP会话
        - _config_overrides: 配置覆盖项
        - _event_sources: 通道到事件源的映射字典
        - _reconnect_request: 重连请求事件
        - _subscribe_request: 订阅请求事件
        - _pending_subscriptions: 待订阅的通道集合
        - backoff_secs: 重连退避时间（秒）
        - _run_called: 运行状态标志
        - _heartbeat: 心跳间隔
        """
        # 调用父类初始化
        super().__init__()
        # WebSocket服务器URL
        self._url = url
        # HTTP会话
        self._session = session
        # 配置覆盖项
        self._config_overrides = config_overrides
        # 通道到事件源的映射字典
        self._event_sources: Dict[str, ChannelEventSource] = {}
        # 重连请求事件
        self._reconnect_request = asyncio.Event()
        # 订阅请求事件
        self._subscribe_request = asyncio.Event()
        # 待订阅的通道集合
        self._pending_subscriptions: Set[str] = set()
        # 重连退避时间（秒）
        self.backoff_secs = 1
        # 运行状态标志
        self._run_called = False
        # 心跳间隔（秒）
        self._heartbeat = heartbeat

    def set_channel_event_source(self, channel: str, event_source: ChannelEventSource):
        """
        【中文说明】设置通道事件源
        
        【功能描述】
        为指定通道注册事件源，并触发订阅请求。
        
        【参数说明】
        - channel: str - 通道名称
        - event_source: ChannelEventSource - 通道事件源实例
        
        【验证检查】
        - 确保通道尚未注册
        
        【内部操作】
        - 将事件源添加到事件源字典
        - 将通道添加到待订阅集合
        - 设置订阅请求事件
        
        【注意事项】
        - 同一个通道不能重复注册
        - 注册后会立即触发订阅流程
        """
        # 验证通道尚未注册
        assert channel not in self._event_sources, "channel already registered"
        # 注册通道事件源
        self._event_sources[channel] = event_source
        # 添加到待订阅集合
        self._pending_subscriptions.add(channel)
        # 触发订阅请求
        self._subscribe_request.set()

    def get_channel_event_source(self, channel: str) -> Optional[ChannelEventSource]:
        """
        【中文说明】获取通道事件源
        
        【功能描述】
        根据通道名称获取对应的事件源。
        
        【参数说明】
        - channel: str - 通道名称
        
        【返回值】
        - Optional[ChannelEventSource]: 通道事件源，如果不存在则返回None
        """
        return self._event_sources.get(channel)

    def schedule_reconnection(self):
        """
        【中文说明】调度重连
        
        【功能描述】
        请求WebSocket客户端重新建立连接。
        
        【使用场景】
        - 网络连接异常
        - 服务器端关闭连接
        - 手动触发重连
        
        【注意事项】
        - 这是一个异步请求，重连会在适当的时候执行
        - 会触发重连退避机制
        """
        # 设置重连请求事件
        self._reconnect_request.set()

    def schedule_resubscription(self, channels: List[str]):
        """
        【中文说明】调度重新订阅
        
        【功能描述】
        请求重新订阅指定的通道列表。
        
        【参数说明】
        - channels: List[str] - 需要重新订阅的通道列表
        
        【使用场景】
        - 连接恢复后重新订阅通道
        - 动态添加新的订阅通道
        - 订阅配置变更时更新订阅
        """
        # 将通道添加到待订阅集合
        self._pending_subscriptions.update(channels)

    async def on_error(self, error: Any):
        """
        【中文说明】错误处理回调
        
        【功能描述】
        处理WebSocket客户端运行过程中发生的错误。
        
        【参数说明】
        - error: Any - 错误对象，可以是异常或其他错误信息
        
        【使用场景】
        - 连接建立失败
        - 消息处理异常
        - 网络通信错误
        
        【注意事项】
        - 使用结构化日志记录错误信息
        - 不会中断客户端运行
        """
        # 记录错误信息到日志
        logger.error(logs.StructuredMessage("Error", src=self, error=error))

    async def on_unknown_message(self, message: aiohttp.WSMessage):
        """
        【中文说明】未知消息处理回调
        
        【功能描述】
        处理无法识别的WebSocket消息。
        
        【参数说明】
        - message: aiohttp.WSMessage - 未知的WebSocket消息
        
        【使用场景】
        - 服务器发送了未预期的消息类型
        - 消息格式不符合预期
        - 协议版本不兼容
        
        【注意事项】
        - 使用警告级别日志记录
        - 不会中断消息处理循环
        """
        # 记录未知消息警告
        logger.warning(logs.StructuredMessage("Unknown message", src=self, type=message.type, data=message.data))

    async def main(self):
        """
        【中文说明】WebSocket客户端主循环
        
        【功能描述】
        执行WebSocket客户端的主循环，管理连接建立、消息处理和重连机制。
        
        【算法流程】
        1. 检查运行状态，确保只运行一次
        2. 应用重连退避机制
        3. 建立WebSocket连接
        4. 启动消息处理、订阅管理和重连监控任务
        5. 处理连接异常并重试
        
        【重连退避机制】
        - 首次连接失败后等待1秒重试
        - 每次重试失败后增加等待时间
        - 避免频繁重连对服务器造成压力
        
        【注意事项】
        - 这是一个异步无限循环
        - 支持优雅的重连和错误恢复
        - 使用任务组管理并发任务
        """
        # 验证运行状态，确保只运行一次
        assert not self._run_called, "run already called"

        # 设置运行状态标志
        self._run_called = True
        # 上次连接尝试的时间戳
        last_connect_ts = 0
        # 主循环：持续尝试连接和处理消息
        while True:
            # 重连退避机制：如果上次尝试时间太近，等待一段时间
            prev_attemp_age = time.time() - last_connect_ts
            if prev_attemp_age < self.backoff_secs:
                # 等待剩余的重连退避时间
                await asyncio.sleep(self.backoff_secs - prev_attemp_age)

            try:
                # 记录连接调试信息
                logger.debug(logs.StructuredMessage("Connecting websocket", src=self, url=self._url))
                # 更新上次连接尝试时间戳
                last_connect_ts = time.time()
                # 建立WebSocket连接并启动任务组
                async with helpers.use_or_create_session(session=self._session) as session, \
                        session.ws_connect(self._url, heartbeat=self._heartbeat) as ws_cli, \
                        helpers.TaskGroup() as tg:

                    # 清除重连请求标志，因为刚刚重新连接
                    self._reconnect_request.clear()

                    # 将所有已注册的通道添加到待订阅集合
                    self._pending_subscriptions.update(self._event_sources.keys())
                    # 触发订阅请求
                    self._subscribe_request.set()

                    # 启动并发任务
                    # 消息处理循环
                    tg.create_task(self._msg_loop(ws_cli))
                    # 订阅管理循环
                    tg.create_task(self._subscribe_loop(ws_cli))
                    # 重连监控循环
                    tg.create_task(self._reconnect(ws_cli))
            except Exception as e:
                # 处理连接异常
                await self.on_error(e)

    @abc.abstractmethod
    async def subscribe_to_channels(
            self, channels: List[str], ws_cli: aiohttp.ClientWebSocketResponse
    ):
        """
        【中文说明】订阅通道
        
        【功能描述】
        抽象方法，向WebSocket服务器订阅指定的通道列表。
        
        【参数说明】
        - channels: List[str] - 要订阅的通道列表
        - ws_cli: aiohttp.ClientWebSocketResponse - WebSocket客户端连接
        
        【实现要求】
        - 子类必须实现此方法
        - 应该发送订阅消息到WebSocket服务器
        - 处理订阅确认和错误响应
        
        【注意事项】
        - 这是一个异步方法
        - 需要处理特定交易所的订阅协议
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def handle_message(self, message: dict) -> bool:
        """
        【中文说明】处理消息
        
        【功能描述】
        抽象方法，处理从WebSocket服务器接收到的消息。
        
        【参数说明】
        - message: dict - 接收到的消息，通常是JSON格式的字典
        
        【返回值】
        - bool: 如果消息被成功处理返回True，否则返回False
        
        【实现要求】
        - 子类必须实现此方法
        - 应该解析消息并根据类型分发给相应的事件源
        - 返回处理状态以便后续处理
        
        【注意事项】
        - 这是一个异步方法
        - 需要处理不同类型的消息（数据、心跳、错误等）
        """
        raise NotImplementedError()

    async def _msg_loop(self, ws_cli: aiohttp.ClientWebSocketResponse):
        """
        【中文说明】消息处理循环
        
        【功能描述】
        处理WebSocket连接的消息流，持续接收和处理消息。
        
        【参数说明】
        - ws_cli: aiohttp.ClientWebSocketResponse - WebSocket客户端连接
        
        【消息类型处理】
        - TEXT: 文本消息，通常是JSON格式
        - BINARY: 二进制消息
        - PING/PONG: 心跳消息
        - CLOSE: 关闭连接消息
        
        【异常处理】
        - 连接正常关闭（1000或1001状态码）：正常退出
        - 连接异常关闭：抛出ConnectionClosedError异常
        
        【注意事项】
        - 这是一个异步生成器
        - 消息循环退出时会通知其他任务
        """
        # 记录调试信息：开始消息处理循环
        logger.debug(logs.StructuredMessage("Running message loop", src=self))

        # 消息迭代器在连接正常关闭（状态码1000或1001）时正常退出
        # 在其他状态码关闭连接时会抛出ConnectionClosedError异常
        async for message in ws_cli:
            handled = False
            # 处理文本消息（通常是JSON格式）
            if message.type == aiohttp.WSMsgType.TEXT:
                # 解析JSON消息
                json_msg = json.loads(message.data)
                # 调用消息处理方法
                handled = await self.handle_message(json_msg)
            # 如果消息未被处理，记录为未知消息
            if not handled:
                await self.on_unknown_message(message)

        # 如果消息循环结束，通知其他任务以便它们也能结束
        self._subscribe_request.set()
        self._reconnect_request.set()

    async def _reconnect(self, ws_cli: aiohttp.ClientWebSocketResponse):
        """
        【中文说明】重连监控循环
        
        【功能描述】
        监控重连请求，在需要时关闭当前连接以触发重连。
        
        【参数说明】
        - ws_cli: aiohttp.ClientWebSocketResponse - WebSocket客户端连接
        
        【操作流程】
        1. 等待重连请求事件
        2. 清除重连请求标志
        3. 如果连接尚未关闭，关闭连接
        
        【使用场景】
        - 网络连接异常需要重连
        - 服务器端主动断开连接
        - 手动触发重连
        
        【注意事项】
        - 这是一个异步任务
        - 关闭连接会触发主循环的重连机制
        """
        # 等待重连请求或任务取消
        await self._reconnect_request.wait()
        # 清除重连请求标志
        self._reconnect_request.clear()
        # 如果客户端尚未关闭，关闭连接
        if not ws_cli.closed:
            await ws_cli.close()

    async def _subscribe_loop(self, ws_cli: aiohttp.ClientWebSocketResponse):
        """
        【中文说明】订阅管理循环
        
        【功能描述】
        管理通道订阅，处理订阅请求并发送订阅消息。
        
        【参数说明】
        - ws_cli: aiohttp.ClientWebSocketResponse - WebSocket客户端连接
        
        【操作流程】
        1. 等待订阅请求事件
        2. 清除订阅请求标志
        3. 如果连接未关闭且有待订阅通道，发送订阅请求
        
        【使用场景】
        - 初始连接后的首次订阅
        - 动态添加新的通道订阅
        - 重连后的重新订阅
        
        【注意事项】
        - 这是一个异步循环
        - 只在连接活跃时发送订阅请求
        - 批量处理待订阅通道
        """
        # 持续运行直到连接关闭
        while not ws_cli.closed:
            # 等待订阅请求
            await self._subscribe_request.wait()
            # 清除订阅请求标志
            self._subscribe_request.clear()
            # 如果连接未关闭且有待订阅通道，发送订阅请求
            if not ws_cli.closed and self._pending_subscriptions:
                # 获取所有待订阅通道
                channels = list(self._pending_subscriptions)
                # 清空待订阅集合
                self._pending_subscriptions = set()
                # 发送订阅请求
                await self.subscribe_to_channels(channels, ws_cli)
