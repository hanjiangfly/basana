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
回测辅助模块

提供回测系统中使用的辅助函数和工具类，包括：
- 订单操作符号计算
- 交易所对象容器管理
"""

from decimal import Decimal
from typing import Dict, Generator, Generic, Iterable, List, Optional, Protocol, TypeVar

from basana.core.enums import OrderOperation


def get_base_sign_for_operation(operation: OrderOperation) -> Decimal:
    """获取订单操作的基础符号。

    :param operation: 订单操作类型。
    :return: 基础符号（买入为1，卖出为-1）。
    """
    if operation == OrderOperation.BUY:
        base_sign = Decimal(1)
    else:
        assert operation == OrderOperation.SELL
        base_sign = Decimal(-1)
    return base_sign


class ExchangeObjectProto(Protocol):
    """交易所对象协议。

    定义交易所对象必须实现的接口。
    """
    @property
    def id(self) -> str:  # pragma: no cover
        """获取对象ID。"""
        ...

    @property
    def is_open(self) -> bool:  # pragma: no cover
        """检查对象是否处于打开状态。"""
        ...


TExchangeObject = TypeVar('TExchangeObject', bound=ExchangeObjectProto)


class ExchangeObjectContainer(Generic[TExchangeObject]):
    """交易所对象容器。

    用于管理交易所对象（如订单、借贷等）的通用容器。

    :param TExchangeObject: 交易所对象类型。
    """
    def __init__(self):
        self._items: Dict[str, TExchangeObject] = {}  # 按ID存储的对象。
        self._open_items: List[TExchangeObject] = []  # 打开状态的对象列表。
        self._reindex_every = 50  # 每处理多少个对象后重新索引。
        self._reindex_counter = 0  # 重新索引计数器。

    def add(self, item: TExchangeObject):
        """添加对象到容器。

        :param item: 要添加的对象。
        """
        assert item.id not in self._items
        self._items[item.id] = item
        if item.is_open:
            self._open_items.append(item)

    def get(self, id: str) -> Optional[TExchangeObject]:
        """根据ID获取对象。

        :param id: 对象ID。
        :return: 对象实例，如果不存在则返回None。
        """
        return self._items.get(id)

    def get_open(self) -> Generator[TExchangeObject, None, None]:
        """获取所有打开状态的对象。

        定期重新索引以提高性能。

        :return: 打开状态对象的生成器。
        """
        self._reindex_counter += 1
        new_open_items: Optional[List[TExchangeObject]] = None
        if self._reindex_counter % self._reindex_every == 0:
            new_open_items = []

        for item in self._open_items:
            if item.is_open:
                yield item
                if new_open_items is not None and item.is_open:
                    new_open_items.append(item)

        if new_open_items is not None:
            self._open_items = new_open_items

    def get_all(self) -> Iterable[TExchangeObject]:
        """获取所有对象。

        :return: 所有对象的可迭代集合。
        """
        return self._items.values()
