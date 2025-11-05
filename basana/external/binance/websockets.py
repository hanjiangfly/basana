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
Binance WebSocket连接模块

此模块提供了Binance WebSocket连接的核心功能，包括：
- WebSocket通道抽象
- WebSocket客户端实现
- 消息处理和订阅管理
- 心跳保持机制

主要类：
- Channel: WebSocket通道抽象基类
- PublicChannel: 公共通道类
- WebSocketClient: WebSocket客户端类
"""

from typing import Dict, List, Optional
from urllib.parse import urljoin
import abc
import asyncio
import datetime
import json
import logging
import time

import aiohttp

from . import client, config
from basana.core import dispatcher, logs, websockets as core_ws
from basana.core.config import get_config_value


logger = logging.getLogger(__name__)


class Channel(metaclass=abc.ABCMeta):
    """WebSocket通道抽象基类
    
    定义WebSocket通道的通用接口。
    """
    
    @property
    @abc.abstractmethod
    def alias(self) -> str:
        """获取通道别名
        
        :return: 通道别名字符串
        """
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def stream(self) -> str:
        """获取流名称
        
        :return: 流名称字符串
        """
        raise NotImplementedError()

    async def resolve_stream_name(self, api_client: client.APIClient):
        """解析流名称
        
        为动态通道提供解析流名称的机会。
        
        :param api_client: API客户端实例
        """
        pass

    def keep_alive_period(self, config_overrides: dict = {}) -> Optional[datetime.timedelta]:
        """获取心跳保持周期
        
        :param config_overrides: 配置覆盖字典
        :return: 心跳间隔时间，如果没有则为None
        """
        return None

    async def keep_alive(self, api_client: client.APIClient):  # pragma: no cover
        """保持连接活跃
        
        发送心跳包以保持WebSocket连接活跃。
        
        :param api_client: API客户端实例
        """
        pass


class PublicChannel(Channel):
    """公共通道类，继承自Channel
    
    表示公共数据流的WebSocket通道。
    """
    
    def __init__(self, name: str):
        """初始化公共通道
        
        :param name: 通道名称
        """
        self._name = name

    @property
    def alias(self) -> str:
        """获取通道别名
        
        :return: 通道别名字符串
        """
        return self._name

    @property
    def stream(self) -> str:
        """获取流名称
        
        :return: 流名称字符串
        """
        return self._name


class WebSocketClient(core_ws.WebSocketClient):
    """Binance WebSocket客户端类，继承自core_ws.WebSocketClient
    
    处理Binance WebSocket连接、订阅和消息处理。
    """
    
    def __init__(
            self, dispatcher: dispatcher.EventDispatcher, api_client: client.APIClient,
            session: Optional[aiohttp.ClientSession] = None, config_overrides: dict = {}
    ):
        """初始化WebSocket客户端
        
        :param dispatcher: 事件分发器
        :param api_client: API客户端
        :param session: aiohttp客户端会话，可选
        :param config_overrides: 配置覆盖字典
        """
        url = urljoin(
            get_config_value(config.DEFAULTS, "api.websockets.base_url", overrides=config_overrides),
            "/stream"
        )
        super().__init__(
            url, session=session, config_overrides=config_overrides,
            heartbeat=get_config_value(config.DEFAULTS, "api.websockets.heartbeat", overrides=config_overrides)
        )
        self._dispatcher = dispatcher
        self._cli = api_client
        self._alias_to_channel: Dict[str, Channel] = {}
        self._stream_to_channel: Dict[str, Channel] = {}
        self._next_keep_alive: Dict[str, datetime.datetime] = {}
        self._next_msg_id = int(time.time() * 1000)

    def set_channel_event_source_ex(self, channel: Channel, event_source: core_ws.ChannelEventSource):
        """设置通道事件源
        
        :param channel: WebSocket通道
        :param event_source: 通道事件源
        :raises AssertionError: 如果通道已经注册
        """
        assert channel.alias not in self._alias_to_channel, "channel already registered"
        super().set_channel_event_source(channel.alias, event_source)
        self._alias_to_channel[channel.alias] = channel

    def get_channel_event_source_ex(self, channel: Channel) -> Optional[core_ws.ChannelEventSource]:
        """获取通道事件源
        
        :param channel: WebSocket通道
        :return: 通道事件源，如果没有则为None
        """
        return super().get_channel_event_source(channel.alias)

    async def subscribe_to_channels(self, channel_aliases: List[str], ws_cli: aiohttp.ClientWebSocketResponse):
        """订阅通道
        
        :param channel_aliases: 通道别名列表
        :param ws_cli: WebSocket客户端响应对象
        """
        logger.debug(logs.StructuredMessage("Subscribing", src=self, channels=channel_aliases))

        # 为动态通道提供解析流名称的机会
        channels: List[Channel] = [self._alias_to_channel[alias] for alias in channel_aliases]
        await asyncio.gather(*[
            channel.resolve_stream_name(self._cli) for channel in channels
        ])
        self._stream_to_channel.update({
            channel.stream: channel for channel in channels
        })

        msg_id = self._get_next_msg_id()
        await ws_cli.send_str(json.dumps({
            "id": msg_id,
            "method": "SUBSCRIBE",
            "params": [channel.stream for channel in channels]
        }))

        # 调度心跳保持
        for channel in channels:
            self._schedule_keep_alive(channel)

    async def handle_message(self, message: dict) -> bool:
        """处理WebSocket消息
        
        :param message: WebSocket消息字典
        :return: 如果消息被处理则为True，否则为False
        """
        coro = None

        # 对我们发送的消息的响应
        if {"result", "id"} <= set(message.keys()):
            coro = self._on_response(message)
        # 与通道关联的消息
        elif stream := message.get("stream"):
            channel = self._stream_to_channel.get(stream)
            assert channel, f"{stream} could not be mapped to a channel instance"
            # 如果监听密钥过期，重新订阅通道
            if message.get("data", {}).get("e") == "listenKeyExpired":
                logger.debug(logs.StructuredMessage(
                    "License key expired. Scheduling re-subscription", alias=channel.alias
                ))
                self.schedule_resubscription([channel.alias])
            # 获取通道别名的事件源
            if event_source := self.get_channel_event_source(channel.alias):
                coro = event_source.push_from_message(message)

        ret = False
        if coro:
            await coro
            ret = True
        return ret

    async def _on_response(self, message: dict):
        """处理响应消息
        
        :param message: 响应消息字典
        """
        if message["result"] is not None:
            await self.on_error(message)

    def _get_next_msg_id(self) -> int:
        """获取下一个消息ID
        
        :return: 消息ID整数
        """
        ret = self._next_msg_id
        self._next_msg_id += 1
        return ret

    def _keep_alive_channel(self, channel: Channel) -> dispatcher.SchedulerJob:
        """创建通道心跳保持任务
        
        :param channel: WebSocket通道
        :return: 调度器任务函数
        """
        async def scheduler_job():
            """调度器任务函数"""
            if self._next_keep_alive[channel.alias] <= self._dispatcher.now():
                logger.debug(logs.StructuredMessage("Channel keep alive", alias=channel.alias))
                try:
                    await channel.keep_alive(self._cli)
                finally:
                    self._schedule_keep_alive(channel)
        return scheduler_job

    def _schedule_keep_alive(self, channel: Channel):
        """调度通道心跳保持
        
        :param channel: WebSocket通道
        """
        period = channel.keep_alive_period(self._config_overrides)
        if period:
            schedule_dt = self._dispatcher.now() + period
            logger.debug(logs.StructuredMessage("Scheduling keep alive", when=schedule_dt, alias=channel.alias))
            self._next_keep_alive[channel.alias] = schedule_dt
            self._dispatcher.schedule(schedule_dt, self._keep_alive_channel(channel))
