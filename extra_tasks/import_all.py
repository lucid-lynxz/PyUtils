import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入当前目录下所有py模块,用于触发装饰器功能
# 参考: https://stackoverflow.com/questions/66571752/import-all-modules-in-a-package-programatically
for module in os.listdir(os.path.dirname(__file__)):
    if module == '__init__.py' or module == 'import_all.py' or module[-3:] != '.py':
        continue
    __import__('extra_tasks.%s' % module[:-3], locals(), globals())
del module
