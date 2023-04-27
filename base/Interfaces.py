# !/usr/bin/env python3
# -*- coding:utf-8 -*-


from abc import abstractmethod, ABCMeta


class Runnable(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def run(self, **kwargs):
        pass


class TagGenerator(metaclass=ABCMeta):
    @abstractmethod
    def getTag(self) -> str:
        """
        返回当前功能模块的tag信息,用于唯一标志
        """
        pass
