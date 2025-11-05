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
回测图表模块

提供用于回测结果可视化的图表工具，包括：
- 交易对价格图表
- 账户余额图表
- 投资组合价值图表
- 自定义指标图表

使用Plotly库生成交互式图表，支持显示和保存功能。
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
import abc
import collections
import logging

from basana.backtesting import errors
from basana.backtesting.exchange import Exchange
from basana.core import bar, event, helpers
from basana.core.enums import OrderOperation
from basana.core.pair import Pair

import plotly.graph_objects as go  # type: ignore
import plotly.subplots  # type: ignore


# 图表数据点函数类型：接收时间戳，返回可选的小数值
ChartDataPointFn = Callable[[datetime], Optional[Decimal]]
logger = logging.getLogger(__name__)


class DataPointFromSequence:
    """从序列中获取数据点的可调用对象。

    如果序列不为空，则返回序列的最后一个值。

    :param seq: 用于获取值的序列。
    """
    def __init__(self, seq: Sequence[Any]):
        self._seq = seq

    def __call__(self, dt: datetime) -> Optional[Decimal]:
        """获取指定时间点的数据点值。

        :param dt: 时间戳
        :return: 序列的最后一个值，如果序列为空则返回None
        """
        ret = None
        if self._seq:
            ret = self._seq[-1]
        return Decimal(ret) if ret is not None else ret


class TimeSeries:
    """时间序列数据存储类。

    用于存储时间戳和对应值的数据对，支持按时间排序。
    """
    def __init__(self):
        self._values = {}

    def add_value(self, dt: datetime, value: Decimal):
        """添加时间戳和对应的值。

        :param dt: 时间戳
        :param value: 对应的数值
        """
        self._values[dt] = value

    def get_x_y(self):
        """获取排序后的时间序列数据。

        :return: 包含时间戳列表和值列表的元组
        """
        return zip(*sorted(self._values.items())) if self._values else ([], [])


class LineChart(metaclass=abc.ABCMeta):
    """折线图抽象基类。

    定义所有折线图类型必须实现的接口。
    """
    @abc.abstractmethod
    def get_title(self) -> str:
        """获取图表标题。

        :return: 图表标题字符串
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def add_traces(self, figure: go.Figure, row: int):
        """向图表添加轨迹。

        :param figure: Plotly图表对象
        :param row: 子图的行号
        """
        raise NotImplementedError()


class PairLineChart(LineChart):
    """交易对价格折线图。

    显示交易对价格走势，可选显示买入和卖出标记，支持技术指标叠加。
    """
    def __init__(self, pair: Pair, include_buys: bool, include_sells: bool, exchange: Exchange):
        """
        :param pair: 交易对
        :param include_buys: 是否包含买入标记
        :param include_sells: 是否包含卖出标记
        :param exchange: 回测交易所实例
        """
        self._pair = pair
        self._include_buys = include_buys
        self._include_sells = include_sells
        self._exchange = exchange
        self._ts = TimeSeries()
        self._indicators: Dict[str, Tuple[ChartDataPointFn, TimeSeries]] = {}

        # 订阅K线事件以更新价格数据
        exchange.subscribe_to_bar_events(pair, self._on_bar_event)

    def get_title(self) -> str:
        """获取图表标题（交易对名称）。"""
        return str(self._pair)

    def add_traces(self, figure: go.Figure, row: int):
        """向图表添加轨迹：价格线、买入卖出标记、技术指标。

        :param figure: Plotly图表对象
        :param row: 子图的行号
        """
        # 添加交易对价格轨迹
        x, y = self._ts.get_x_y()
        figure.add_trace(go.Scatter(x=x, y=y, name=str(self._pair)), row=row, col=1)

        # 添加买入价格标记
        if self._include_buys:
            x, y = self._get_order_fills(OrderOperation.BUY).get_x_y()
            figure.add_trace(
                go.Scatter(x=x, y=y, name="买入", mode="markers", marker=dict(symbol="arrow-up", color="green")),
                row=row, col=1
            )

        # 添加卖出价格标记
        if self._include_sells:
            x, y = self._get_order_fills(OrderOperation.SELL).get_x_y()
            figure.add_trace(
                go.Scatter(x=x, y=y, name="卖出", mode="markers", marker=dict(symbol="arrow-down", color="red")),
                row=row, col=1
            )

        # 为每个技术指标添加轨迹
        for name, (_, ts) in self._indicators.items():
            x, y = ts.get_x_y()
            figure.add_trace(go.Scatter(x=x, y=y, name=name), row=row, col=1)

    def add_indicator(self, name: str, get_data_point: ChartDataPointFn):
        """添加技术指标。

        :param name: 指标名称
        :param get_data_point: 获取数据点的函数
        """
        assert name not in self._indicators
        self._indicators[name] = (get_data_point, TimeSeries())

    def _get_order_fills(self, op: OrderOperation) -> TimeSeries:
        """获取指定操作类型的订单成交价格时间序列。

        :param op: 订单操作类型（买入或卖出）
        :return: 成交价格时间序列
        """
        ret = TimeSeries()
        orders = filter(
            lambda order: order.pair == self._pair and order.operation == op,
            self._exchange._get_all_orders()
        )
        pair_info = self._exchange._get_pair_info(self._pair)
        for order in orders:
            for fill in order.fills:
                base_amount = fill.balance_updates[order.pair.base_symbol]
                quote_amount = fill.balance_updates[order.pair.quote_symbol]
                price = -helpers.truncate_decimal(quote_amount / base_amount, pair_info.quote_precision)
                ret.add_value(fill.when, price)
        return ret

    async def _on_bar_event(self, bar_event: bar.BarEvent):
        """处理K线事件，更新价格和技术指标数据。

        :param bar_event: K线事件
        """
        dt = bar_event.when
        value = bar_event.bar.close
        # 将值添加到主时间序列
        self._ts.add_value(dt, value)
        # 添加自定义指标值
        for get_data_point, ts in self._indicators.values():
            indicator_value = get_data_point(dt)
            if indicator_value is not None:
                ts.add_value(dt, indicator_value)


class AccountBalanceLineChart(LineChart):
    """账户余额折线图。

    显示指定货币符号的账户余额变化。
    """
    def __init__(self, symbol: str, exchange: Exchange):
        """
        :param symbol: 货币符号
        :param exchange: 回测交易所实例
        """
        self._symbol = symbol
        self._exchange = exchange
        self._ts = TimeSeries()

        # 最初考虑让交易所在余额更新时发出事件，但后来意识到如果图表未被使用，这会带来过多开销。
        exchange._get_dispatcher().subscribe_all(self._on_any_event)

    def get_title(self) -> str:
        """获取图表标题（货币余额）。"""
        return f"{self._symbol} 余额"

    def add_traces(self, figure: go.Figure, row: int):
        """向图表添加余额轨迹。

        :param figure: Plotly图表对象
        :param row: 子图的行号
        """
        # 添加余额轨迹
        x, y = self._ts.get_x_y()
        figure.add_trace(go.Scatter(x=x, y=y, name=self._symbol), row=row, col=1)

    async def _on_any_event(self, event: event.Event):
        """处理任何事件，更新余额数据。

        :param event: 事件对象
        """
        balance = await self._exchange.get_balance(self._symbol)
        # 计算净余额（总余额减去借入余额）
        self._ts.add_value(event.when, balance.total - balance.borrowed)


class PortfolioValueLineChart(LineChart):
    """投资组合价值折线图。

    显示以指定货币计价的投资组合总价值变化。
    """
    def __init__(self, quote_symbol: str, exchange: Exchange, precision: int = 2):
        """
        :param quote_symbol: 计价货币符号
        :param exchange: 回测交易所实例
        :param precision: 小数精度
        """
        self._quote_symbol = quote_symbol
        self._exchange = exchange
        self._ts = TimeSeries()
        self._precision = precision

        # 最初考虑让交易所在余额更新时发出事件，但后来意识到如果图表未被使用，这会带来过多开销。
        exchange._get_dispatcher().subscribe_all(self._on_any_event)

    def get_title(self) -> str:
        """获取图表标题（投资组合价值）。"""
        return f"投资组合价值 ({self._quote_symbol})"

    def add_traces(self, figure: go.Figure, row: int):
        """向图表添加投资组合价值轨迹。

        :param figure: Plotly图表对象
        :param row: 子图的行号
        """
        # 添加投资组合价值轨迹
        x, y = self._ts.get_x_y()
        figure.add_trace(go.Scatter(x=x, y=y, name=f"投资组合 ({self._quote_symbol})"), row=row, col=1)

    async def _on_any_event(self, event: event.Event):
        """处理任何事件，更新投资组合价值数据。

        :param event: 事件对象
        """
        portfolio_value = Decimal(0)
        balances = await self._exchange.get_balances()
        for symbol, balance in balances.items():
            if balance.total == 0:
                continue

            try:
                price = Decimal(1)
                if symbol != self._quote_symbol:
                    # 获取买卖价格，根据余额正负选择合适的价格
                    bid, ask = await self._exchange.get_bid_ask(Pair(symbol, self._quote_symbol))
                    price = bid if balance.total > 0 else ask
                portfolio_value += balance.total * price
            except errors.Error as e:
                logger.debug(str(e))

        # 四舍五入到指定精度并添加到时间序列
        self._ts.add_value(event.when, helpers.round_decimal(portfolio_value, self._precision))


class CustomLineChart(LineChart):
    """自定义折线图。

    允许用户自定义数据点和线条的图表。
    """
    def __init__(self, name: str, exchange: Exchange):
        """
        :param name: 图表名称
        :param exchange: 回测交易所实例
        """
        self._name = name
        self._exchange = exchange
        self._data_point_fns: Dict[str, Tuple[ChartDataPointFn, TimeSeries]] = {}

        exchange._get_dispatcher().subscribe_all(self._on_any_event)

    def get_title(self) -> str:
        """获取图表标题。"""
        return self._name

    def add_traces(self, figure: go.Figure, row: int):
        """向图表添加所有自定义线条轨迹。

        :param figure: Plotly图表对象
        :param row: 子图的行号
        """
        for name, (_, ts) in self._data_point_fns.items():
            x, y = ts.get_x_y()
            figure.add_trace(go.Scatter(x=x, y=y, name=name), row=row, col=1)

    def add_data_point_fn(self, name: str, get_data_point: ChartDataPointFn):
        """添加数据点函数。

        :param name: 线条名称
        :param get_data_point: 获取数据点的函数
        """
        assert name not in self._data_point_fns
        self._data_point_fns[name] = (get_data_point, TimeSeries())

    async def _on_any_event(self, event: event.Event):
        """处理任何事件，更新所有自定义数据点。

        :param event: 事件对象
        """
        dt = event.when
        for get_data_point, ts in self._data_point_fns.values():
            value = get_data_point(dt)
            if value is not None:
                ts.add_value(dt, value)


class LineCharts:
    """折线图集合。

    显示交易对价格和账户余额随时间变化的折线图集合。

    :param exchange: 回测交易所实例。
    """
    def __init__(self, exchange: Exchange):
        self._exchange = exchange
        self._balance_charts: Dict[str, AccountBalanceLineChart] = collections.OrderedDict()
        self._pair_charts: Dict[Pair, PairLineChart] = collections.OrderedDict()
        self._portfolio_charts: Dict[str, PortfolioValueLineChart] = collections.OrderedDict()
        self._custom_charts: Dict[str, CustomLineChart] = collections.OrderedDict()

    def add_balance(self, symbol: str):
        """添加账户余额图表。

        :param symbol: 货币符号。
        """
        self._balance_charts[symbol] = AccountBalanceLineChart(symbol, self._exchange)

    def add_portfolio_value(self, symbol: str, precision: int = 2):
        """添加以指定货币计价的投资组合价值图表。

        :param symbol: 货币符号。
        :param precision: 小数点后的位数。

        .. note::

            * 如果在任何时间点无法计算投资组合价值（例如，某个工具没有价格），将记录错误日志。
        """
        self._portfolio_charts[symbol] = PortfolioValueLineChart(symbol, self._exchange, precision=precision)

    def add_pair(self, pair: Pair, include_buys: bool = True, include_sells: bool = True):
        """添加交易对价格图表。

        :param pair: 交易对。
        :param include_buys: 是否包含买入价格标记。
        :param include_sells: 是否包含卖出价格标记。
        """
        self._pair_charts[pair] = PairLineChart(pair, include_buys, include_sells, self._exchange)

    def add_pair_indicator(self, name: str, pair: Pair, get_data_point: ChartDataPointFn):
        """向交易对图表添加技术指标。

        :param name: 指标名称。
        :param pair: 要添加指标的交易对图表。
        :param get_data_point: 用于在每个K线上获取数据点的可调用对象。
        """
        assert pair in self._pair_charts, f"{pair} 未添加"
        self._pair_charts[pair].add_indicator(name, get_data_point)

    def add_custom(self, name: str, line: str, get_data_point: ChartDataPointFn):
        """添加自定义图表。

        :param name: 图表名称。
        :param line: 线条名称。
        :param get_data_point: 用于获取线条数据点的可调用对象。
        """
        if (chart := self._custom_charts.get(name)) is None:
            chart = CustomLineChart(name, self._exchange)
            self._custom_charts[name] = chart
        chart.add_data_point_fn(line, get_data_point)

    def show(self, show_legend: bool = True):  # pragma: no cover
        """使用默认渲染器显示图表。

        查看 https://plotly.com/python-api-reference/generated/plotly.graph_objects.Figure.html#plotly.graph_objects.Figure.show
        获取更多信息。

        :param show_legend: 如果图例应该可见则为True，否则为False。
        """  # noqa: E501

        if fig := self._build_figure(show_legend=show_legend):
            fig.show()

    def save(
            self, path: str, width: Optional[int] = None, height: Optional[int] = None,
            scale: Optional[Union[int, float]] = None, show_legend: bool = True
    ):
        """将图表保存到文件。

        :param path: 保存图像的文件路径。
        :param width: 导出图像的宽度（布局像素）。
        :param height: 导出图像的高度（布局像素）。
        :param scale: 导出图表时使用的缩放因子。
        :param show_legend: 如果图例应该可见则为True，否则为False。

        .. note::

            * 支持的文件格式包括 png、jpg/jpeg、webp、svg 和 pdf。
        """

        if fig := self._build_figure(show_legend=show_legend):
            fig.write_image(path, width=width, height=height, scale=scale)

    def _build_figure(self, show_legend: bool = True) -> Optional[go.Figure]:
        """构建包含所有图表的Plotly图表对象。

        :param show_legend: 是否显示图例。
        :return: Plotly图表对象，如果没有图表则返回None。
        """
        charts: List[LineChart] = []
        charts.extend(self._pair_charts.values())
        charts.extend(self._balance_charts.values())
        charts.extend(self._portfolio_charts.values())
        charts.extend(self._custom_charts.values())

        figure = None
        if charts:
            subplot_titles = [chart.get_title() for chart in charts]
            figure = plotly.subplots.make_subplots(
                rows=len(charts), cols=1, shared_xaxes=True, subplot_titles=subplot_titles
            )

            row = 1
            for chart in charts:
                chart.add_traces(figure, row)
                row += 1

            figure.layout.update(showlegend=show_legend)

        return figure
