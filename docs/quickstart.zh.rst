快速入门
==========

准备好开始了吗？本页提供了如何开始使用 Basana 框架的良好介绍。

.. _quickstart_installation:

安装
------------

Basana 需要 Python 3.9 或更高版本，您可以使用以下命令安装该包：

.. code-block:: console

   $ pip install basana[charts]

`GitHub 上的示例 <https://github.com/gbeced/basana/tree/master/samples>`_ 利用了 TALIpp、Pandas 和 statsmodels。
可以使用以下命令安装这些依赖：

.. code-block:: console

   $ pip install talipp pandas statsmodels

.. _quickstart_backtesting:

回测(Backtesting)
-----------

以下大多数示例的结构如下：

* 一个交易策略(Trading Strategy)，实现了一组规则，用于定义**何时**根据市场条件进入或退出仓位(Position)。
  策略会生成称为交易信号(Trading Signals)的事件，以通知一个或多个交易对(Pairs)的仓位切换。
* 一个仓位管理器(Position Manager)，负责响应策略生成的交易信号执行交易。
  示例包括一个 `回测仓位管理器 <https://github.com/gbeced/basana/blob/master/samples/backtesting/position_manager.py>`_
  和一个 `Binance 仓位管理器 <https://github.com/gbeced/basana/blob/master/samples/binance/position_manager.py>`_。
  这些仓位管理器使用市价单(Market Orders)来保持示例简短，但在编写您自己的仓位管理器时，您可能希望使用限价单(Limit Orders)。

.. note::
    **这些示例仅供教育目的。使用风险自负，特别是实盘交易(Live Trading)示例**。

    示例的结构只是一种实现方式。您可以自由地以任何其他方式组织代码。

我们将用于回测的策略基于 `布林带(Bollinger Bands) <https://www.investopedia.com/articles/trading/07/bollinger.asp>`_，
本示例的目的只是让您了解如何将不同的组件连接在一起。

为了执行回测，我们首先需要历史数据。使用以下命令从 Binance 下载 K线(Bars)数据：

.. code-block:: console

    $ python -m basana.external.binance.tools.download_bars -c BTC/USDT -p 1d -s 2021-01-01 -e 2021-12-31 -o binance_btcusdt_day.csv

在此示例中有两种类型的事件发生：

* 由交易所生成的 K线(OHLC)事件。
* 由策略生成的交易信号(Trading Signals)。

当策略接收到新的 K线时，将使用该 K线的收盘价(Closing Price)来更新技术指标(Technical Indicator)。
如果技术指标已准备就绪，策略将检查其值以确定是否应该进行仓位切换，在这种情况下将推送交易信号。

当仓位管理器接收到交易信号时，将向交易所提交买入或卖出市价单，以开仓或平仓。

以下是将所有组件组合在一起的方式：

.. literalinclude:: ../samples/backtest_bbands.py
   :language: python
   :lines: 40-74
   :dedent: 4

此示例的完整源代码可以在 `这里 <https://github.com/gbeced/basana/tree/master/samples/backtest_bbands.py>`_ 找到，
如果您分叉该仓库，或下载并解压 `示例 <https://github.com/gbeced/basana/releases/download/1.9/samples.zip>`_，
可以使用以下命令执行回测：

.. code-block:: console

    $ python -m samples.backtest_bbands

类似于此图的图表应在浏览器中打开：

.. image:: _static/backtesting_bbands.png

.. _quickstart_livetrading:

实盘交易(Live Trading)
------------

我们将用于实盘交易的策略与用于回测的策略完全相同，但我们将使用 `Binance <https://www.binance.com/>`_ 加密货币交易所，而不是回测交易所。

.. literalinclude:: ../samples/binance_bbands.py
   :language: python
   :lines: 31-52
   :dedent: 4

.. note::
    这些提供的示例仅供教育目的。

    **如果您决定使用真实凭据执行它们，您将自行承担风险。**

您可以使用以下命令开始实盘交易：

.. code-block:: console

    $ python -m samples.binance_bbands

后续步骤
----------

这里介绍的示例以及许多其他示例可以在
`GitHub 上的示例文件夹 <https://github.com/gbeced/basana/tree/master/samples>`_ 中找到。
