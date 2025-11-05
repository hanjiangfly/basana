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
回测错误模块

定义回测系统中使用的异常类。
"""

from basana.core import errors


class Error(errors.Error):
    """回测异常基类。"""
    pass


class NotEnoughBalance(Error):
    """余额不足异常。"""
    pass


class NotFound(Error):
    """未找到异常。"""
    pass
