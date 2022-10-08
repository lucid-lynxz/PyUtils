## 背景

在公司内部使用本脚本时, 可能有额外的特殊逻辑, 且不方便直接加入到版本管理, 因此增加自定义task功能
通过装饰器 `@taskWrapper` 将自定义处理函数注入到各脚本的对应的生命周期中

## 实现

1. 在 `base/BaseConfig.py` 中导入了 `extras_task/import_all.py`
2. `import_all.py` 会自动导入当前其所在目录下的所有python脚本, 进而触发装饰器功能,自动将各函数加入到 `TaskManager` 中

## 编写自定义task

1. 文件名格式: `task_xxx.py`, 即以 `task_` 开头, 以便 `.gitignore` 可以将之忽略, 不加入版本管理
2. 目前支持在脚本的三个生命周期中注入额外的处理函数, 见 `TaskLifeCycle` 类, 具体如下:
    * `TaskLifeCycle.afterConfigInit`: 会在 config.ini 组装完毕后触发
    * `TaskLifeCycle.beforeRun`: 会在执行 onRun() 方法前触发
    * `TaskLifeCycle.afterRun`: 会在执行 onRun() 方法后触发
   ```python
   from base.TaskManager import taskWrapper, TaskParam, TaskLifeCycle
   
   
   # 装饰器需填入两个参数: 脚本的tag信息和要注入的生命周期
   # 自定义函数带有一个 TaskParam 参数参数
   @taskWrapper('GetLogImpl', taskLifeCycle=TaskLifeCycle.beforeRun)
   def getLogBeforeRun(param: TaskParam):
       print('getLogBeforeRun fun %s' % param) # 执行额外的逻辑
   ```
3. 装饰器 `@taskWrapper` 说明
    * 需要明确待注入的脚本tag信息, 通常为: `BaseConfig` 的子类名称(实际是: `TagGenerator` 的子类名称)

   ```python
   from base.TaskManager import TaskManager, TaskLifeCycle
   
   def taskWrapper(tag: str, taskLifeCycle: TaskLifeCycle):
       """
       装饰器,用于将自定义的额外方法加入 TaskManager中
       :param tag: 唯一标识信息
       :param taskLifeCycle: func执行阶段, 参考枚举: TaskLifeCycle
       """
   
       def deco_fun(func):
           def wrapper(*args, **kwargs):
               func(*args, **kwargs)
   
           TaskManager.addTask(tag, taskLifeCycle, func)
           return wrapper
   
       return deco_fun
   ```