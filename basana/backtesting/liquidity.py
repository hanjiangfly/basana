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
回测流动性模块

提供回测系统中的流动性策略，包括：
- 无限流动性策略（无价格影响）
- 成交量份额影响策略

支持模拟订单执行时的流动性限制和价格滑点。
"""

from decimal import Decimal
import abc

from basana.backtesting import errors
from basana.core import bar


class LiquidityStrategy(metaclass=abc.ABCMeta):
    """流动性策略基类。

    流动性策略定义了在处理订单时可以使用多少 :class:`basana.Bar` 的成交量以及价格滑点。

    .. note::

        * 这是一个基类，不应直接使用。
        * 具体策略将由 :class:`basana.backtesting.exchange.Exchange` 为每个交易对创建。
    """

    @abc.abstractmethod
    def on_bar(self, bar: bar.Bar):
        """当新的K线可用时调用。

        :param bar: K线数据。
        """
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def available_liquidity(self) -> Decimal:
        """获取可用流动性。

        :return: 可用流动性数量。
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def take_liquidity(self, amount: Decimal) -> Decimal:
        """获取/消耗可用流动性。

        :param amount: 要获取的流动性数量。必须 <= 可用流动性。
        :return: 价格影响的百分比。
        :raises errors.Error: 如果流动性不足。
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def calculate_price_impact(self, amount: Decimal) -> Decimal:
        """:meth:`take_liquidity` 的只读版本。

        :param amount: 要计算的流动性数量。
        :return: 价格影响的百分比。
        :raises errors.Error: 如果流动性不足。
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def calculate_amount(self, price_impact: Decimal) -> Decimal:
        """计算在指定价格影响下可以获取的流动性数量。

        :param price_impact: 最大价格影响（百分比）。
        :return: 可以获取的流动性数量。
        :raises errors.Error: 如果流动性不足。
        """
        raise NotImplementedError()


class InfiniteLiquidity(LiquidityStrategy):
    """无限流动性策略。

    此类模拟无限流动性且无价格影响。
    """

    def on_bar(self, bar: bar.Bar):
        """处理新的K线数据（无操作）。"""
        pass

    @property
    def available_liquidity(self) -> Decimal:
        """获取可用流动性（无限）。"""
        return Decimal("Infinity")

    def take_liquidity(self, amount: Decimal) -> Decimal:
        """获取流动性（无价格影响）。

        :param amount: 要获取的流动性数量。
        :return: 价格影响（始终为0）。
        """
        assert amount > Decimal(0)
        assert amount <= self.available_liquidity

        return Decimal(0)

    def calculate_price_impact(self, amount: Decimal) -> Decimal:
        """计算价格影响（无价格影响）。

        :param amount: 要计算的流动性数量。
        :return: 价格影响（始终为0）。
        """
        assert amount > Decimal(0)
        assert amount <= self.available_liquidity

        return Decimal(0)

    def calculate_amount(self, price_impact: Decimal) -> Decimal:
        """计算在指定价格影响下可以获取的流动性数量（无限）。

        :param price_impact: 最大价格影响。
        :return: 可以获取的流动性数量（无限）。
        """
        assert price_impact >= Decimal(0), f"无效的价格影响 {price_impact}"

        return Decimal("Infinity")


class VolumeShareImpact(LiquidityStrategy):
    """成交量份额影响策略。

    价格影响通过将价格影响常数乘以已使用成交量与总成交量比率的平方来计算。

    :param volume_limit_pct: 每个K线可以使用的最大成交量百分比。
    :param price_impact: 最大价格影响（百分比）。
    """

    def __init__(self, volume_limit_pct: Decimal = Decimal("25"), price_impact: Decimal = Decimal("10")):
        assert volume_limit_pct >= Decimal(0), f"无效的成交量限制百分比 {volume_limit_pct}"
        assert price_impact >= Decimal(0), f"无效的价格影响 {price_impact}"

        self._volume_limit_pct = volume_limit_pct / Decimal(100)
        self._price_impact_pct = price_impact / Decimal(100)
        self._total_liquidity = Decimal(0)
        self._used_liquidity = Decimal(0)

    def on_bar(self, bar: bar.Bar):
        """处理新的K线数据，重置流动性。

        :param bar: K线数据。
        """
        self._total_liquidity = bar.volume * self._volume_limit_pct
        self._used_liquidity = Decimal(0)

    def _volume_share_impact(self, used_liquidity: Decimal) -> Decimal:
        """计算成交量份额影响。

        :param used_liquidity: 已使用的流动性数量。
        :return: 价格影响百分比。
        """
        # impact = (used_liquidity / (used_liquidity + available_liquidity)) ** 2 * price_impact
        assert used_liquidity >= Decimal(0), f"无效的已使用流动性 {used_liquidity}"
        assert used_liquidity <= self._total_liquidity, f"已使用流动性 {used_liquidity} 过高"

        if used_liquidity == Decimal(0):
            ret = Decimal(0)
        else:
            used_pct = used_liquidity / self._total_liquidity
            ret = used_pct ** Decimal(2) * self._price_impact_pct
        return ret

    @property
    def available_liquidity(self) -> Decimal:
        """获取可用流动性。

        :return: 可用流动性数量。
        """
        return self._total_liquidity - self._used_liquidity

    def take_liquidity(self, amount: Decimal) -> Decimal:
        """获取流动性并计算价格影响。

        :param amount: 要获取的流动性数量。
        :return: 价格影响百分比。
        :raises errors.Error: 如果流动性不足。
        """
        assert amount >= Decimal(0), f"无效的数量 {amount}"
        if amount > self.available_liquidity:
            raise errors.Error("流动性不足")

        impact_pre = self._volume_share_impact(self._used_liquidity)
        self._used_liquidity += amount
        impact_post = self._volume_share_impact(self._used_liquidity)
        diff = impact_post - impact_pre
        assert diff >= Decimal(0)
        return diff

    def calculate_price_impact(self, amount: Decimal) -> Decimal:
        """计算指定数量的价格影响（只读）。

        :param amount: 要计算的流动性数量。
        :return: 价格影响百分比。
        :raises errors.Error: 如果流动性不足。
        """
        assert amount >= Decimal(0), f"无效的数量 {amount}"
        if amount > self.available_liquidity:
            raise errors.Error("流动性不足")

        return self._volume_share_impact(self._used_liquidity + amount)

    def calculate_amount(self, price_impact: Decimal) -> Decimal:
        """计算在指定价格影响下可以获取的流动性数量。

        :param price_impact: 最大价格影响（百分比）。
        :return: 可以获取的流动性数量。
        :raises errors.Error: 如果流动性不足。
        """
        assert price_impact >= Decimal(0), f"无效的价格影响 {price_impact}"

        # price_impact = (used_liquidity / self._total_liquidity) ** 2 * self._price_impact_pct
        # price_impact / self._price_impact_pct = (used_liquidity / self._total_liquidity) ** 2
        # sqrt(price_impact / self._price_impact_pct) = used_liquidity / self._total_liquidity
        # used_liquidity = self._total_liquidity * sqrt(price_impact / self._price_impact_pct)

        if price_impact == Decimal(0):
            ret = Decimal(0)
        elif self.available_liquidity == Decimal(0) or self._price_impact_pct == Decimal(0):
            raise errors.Error("流动性不足")
        else:
            price_impact = min(price_impact, self._price_impact_pct)
            used_liquidity = self._total_liquidity * (price_impact / self._price_impact_pct).sqrt()

            assert used_liquidity <= self._total_liquidity
            ret = max(Decimal(0), used_liquidity - self._used_liquidity)
        return ret
