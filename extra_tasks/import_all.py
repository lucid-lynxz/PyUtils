import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

# 导入当前目录下所有py模块,用于触发装饰器功能
# 参考: https://stackoverflow.com/questions/66571752/import-all-modules-in-a-package-programatically
for module in os.listdir(os.path.dirname(__file__)):
    if module == '__init__.py' or module == 'import_all.py' or module[-3:] != '.py':
        continue
    __import__('extra_tasks.%s' % module[:-3], locals(), globals())
del module
