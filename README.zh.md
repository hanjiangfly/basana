[![测试用例](https://github.com/gbeced/basana/actions/workflows/runtests.yml/badge.svg?branch=master)](https://github.com/gbeced/basana/actions/workflows/runtests.yml)
[![PyPI 版本](https://badge.fury.io/py/basana.svg)](https://badge.fury.io/py/basana)
[![Read The Docs](https://readthedocs.org/projects/basana/badge/?version=latest)](https://basana.readthedocs.io/en/latest/)
[![许可证](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![下载量](https://static.pepy.tech/badge/basana/month)](https://pepy.tech/project/basana)

# Basana

**Basana** 是一个用于**算法交易**的 Python **异步和事件驱动**框架，专注于**加密货币**交易。

## 主要特性

* **回测交易所** - 在使用真实资金之前测试您的交易策略
* **实盘交易** - 支持 [Binance](https://www.binance.com/) 和 [Bitstamp](https://www.bitstamp.net/) 加密货币交易所
* **异步 I/O 和事件驱动** - 高性能的异步架构设计

## 快速开始

### 安装

```
$ pip install basana[charts]
```

示例代码使用 [TALIpp](https://github.com/nardew/talipp) 进行技术指标计算，同时需要 pandas、statsmodels，如果您想运行 Binance 订单簿镜像示例，还需要安装 [Textual](https://textual.textualize.io/)。

```
$ pip install talipp pandas statsmodels textual
```

下载并解压 [示例代码](https://github.com/gbeced/basana/releases/download/1.9/samples.zip) 或克隆 [GitHub](https://github.com/gbeced/basana/) 仓库。

### 回测配对交易策略

1. 下载历史数据用于回测

	```
	$ python -m basana.external.binance.tools.download_bars -c BCH/USDT -p 1h -s 2021-12-01 -e 2021-12-26 -o binance_bchusdt_hourly.csv
	$ python -m basana.external.binance.tools.download_bars -c CVC/USDT -p 1h -s 2021-12-01 -e 2021-12-26 -o binance_cvcusdt_hourly.csv
	```

2. 运行回测

	```
	$ python -m samples.backtest_pairs_trading
	```

![./docs/_static/readme_pairs_trading.png](./docs/_static/readme_pairs_trading.png)

### Binance 订单簿镜像

以下示例演示了如何使用 Basana 的事件驱动架构维护一个同步的本地 Binance 订单簿副本。它从 REST API 快照初始化订单簿，然后通过 WebSocket 流实时更新差异，同时定期验证与新鲜快照的一致性，以处理潜在的同步问题。

![./docs/_static/order_book_mirror.png](./docs/_static/order_book_mirror.png)

使用以下命令运行示例：

```
$ python -m samples.binance_order_book_mirror
```

镜像代码可以在 [这里](./samples/binance/order_book_mirror.py) 找到。

Basana 仓库提供了多个 [示例](./samples)，您可以进行实验或用作自己项目的模板：

**请注意，这些示例仅供教育目的。使用风险自负。**

## 文档

[https://basana.readthedocs.io/en/latest/](https://basana.readthedocs.io/en/latest/)

## 帮助

您可以在 [GitHub](https://github.com/gbeced/basana/discussions) 的讨论区寻求使用 Basana 的帮助。
