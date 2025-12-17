# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
给类属性用的 @property 注解, 改为: @classproperty 即可
"""


class ClassPropertyDescriptor:
    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)
        return self.fget(klass)  # fget 是普通函数，接收 cls 参数

    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError("can't set attribute")
        klass = type(obj)
        return self.fset(klass, value)


def classproperty(func):
    """用于定义类级别的 property"""
    if isinstance(func, ClassPropertyDescriptor):
        # 支持 setter 链式调用
        return func
    return ClassPropertyDescriptor(func)


# 支持 setter
def _classproperty_setter(class_prop, fset):
    return ClassPropertyDescriptor(class_prop.fget, fset)
