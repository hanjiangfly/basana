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
布林带策略实现

此策略基于布林带技术指标，通过价格与布林带上下轨的交叉关系生成交易信号。
布林带由三条线组成：中轨（移动平均线）、上轨（中轨+标准差）、下轨（中轨-标准差）。

策略逻辑：
- 当价格从上方跌破下轨时，做多（认为价格被低估）
- 当价格从下方突破上轨时，做空（认为价格被高估）
- 当价格触及中轨时，平仓（中性持仓）

参考：https://www.investopedia.com/articles/trading/07/bollinger.asp
"""

from talipp.indicators import BB

import basana as bs


class Strategy(bs.TradingSignalSource):
    """
    布林带策略类
    
    基于布林带技术指标生成交易信号，通过价格与布林带上下轨的交叉关系判断市场趋势。
    
    参数：
    - dispatcher: 事件分发器
    - period: 布林带周期（移动平均窗口大小）
    - std_dev: 标准差倍数（决定布林带宽度）
    """
    def __init__(self, dispatcher: bs.EventDispatcher, period: int, std_dev: float):
        super().__init__(dispatcher)
        self.bb = BB(period, std_dev)  # 布林带指标实例
        self._values = (None, None)    # 存储最近两个价格值用于交叉检测

    async def on_bar_event(self, bar_event: bs.BarEvent):
        """
        处理K线事件，更新布林带指标并生成交易信号
        
        参数：
        - bar_event: K线事件，包含价格和时间信息
        """
        # 将当前K线收盘价添加到布林带指标
        value = float(bar_event.bar.close)
        self.bb.add(value)

        # 更新最近两个价格值，用于检测交叉
        self._values = (self._values[-1], value)

        # 检查指标是否已准备好（至少需要2个有效值）
        if len(self.bb) < 2 or self.bb[-2] is None:
            return

        # 做多信号：价格从上方跌破下轨
        if self._values[-2] >= self.bb[-2].lb and self._values[-1] < self.bb[-1].lb:
            self.push(bs.TradingSignal(bar_event.when, bs.Position.LONG, bar_event.bar.pair))
        # 做空信号：价格从下方突破上轨
        elif self._values[-2] <= self.bb[-2].ub and self._values[-1] > self.bb[-1].ub:
            self.push(bs.TradingSignal(bar_event.when, bs.Position.SHORT, bar_event.bar.pair))
        # 平仓信号：价格触及中轨
        elif self._values[-2] < self.bb[-2].cb and self._values[-1] >= self.bb[-1].cb \
                or self._values[-2] > self.bb[-2].cb and self._values[-1] <= self.bb[-1].cb:
            self.push(bs.TradingSignal(bar_event.when, bs.Position.NEUTRAL, bar_event.bar.pair))
