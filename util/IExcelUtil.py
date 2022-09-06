# !/usr/bin/env python
# -*- coding:utf-8 -*-
from abc import ABCMeta, abstractmethod


class IExcelUtil(metaclass=ABCMeta):
    @abstractmethod
    def getAllSheetNames(self):
        """
        获取工作簿中所有的sheet表名
        :return:
        """
        raise NotImplementedError
