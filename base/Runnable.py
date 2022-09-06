# !/usr/bin/env python3
# -*- coding:utf-8 -*-


from abc import abstractmethod, ABCMeta


class Runnable(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def run(self):
        pass
