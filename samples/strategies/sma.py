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
简单移动平均策略实现

此策略基于简单移动平均技术指标，通过价格与移动平均线的交叉关系生成交易信号。

策略逻辑：
- 当价格上穿移动平均线时做多
- 当价格下穿移动平均线时做空
- 当价格与移动平均线交叉时平仓

使用场景：
- 趋势跟踪策略
- 市场方向判断
- 技术分析参考
"""

from talipp.indicators import SMA

import basana as bs


class Strategy(bs.TradingSignalSource):
    def __init__(self, dispatcher: bs.EventDispatcher, period: int):
        super().__init__(dispatcher)
        self.sma = SMA(period)
        self._values = (None, None)

    async def on_bar_event(self, bar_event: bs.BarEvent):
        # Feed the technical indicator.
        value = float(bar_event.bar.close)
        self.sma.add(value)

        # Keep a small window of values to check if there is a crossover.
        self._values = (self._values[-1], value)

        # Is the indicator ready ?
        if len(self.sma) < 2 or self.sma[-2] is None:
            return

        # Go short if price crosses below SMA.
        if self._values[-2] >= self.sma[-2] and self._values[-1] < self.sma[-1]:
            self.push(bs.TradingSignal(bar_event.when, bs.Position.SHORT, bar_event.bar.pair))
        # Go long if price crosses above SMA.
        elif self._values[-2] <= self.sma[-2] and self._values[-1] > self.sma[-1]:
            self.push(bs.TradingSignal(bar_event.when, bs.Position.LONG, bar_event.bar.pair))
