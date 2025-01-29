## 办公自动化脚本-拆分工资条-截图保存-发送邮件

## 安装须知
```shell
pip3 install -r requirements_win.txt

# 安装excel处理库 openpyxl
# 若要使用openpyxl进行截图的话, 需要用到win32库(windows系统支持) 和 pillow
python3 -m pip  install openpyxl pillow pypiwin32  -i https://pypi.tuna.tsinghua.edu.cn/simple


# macos系统下, 本想用xlwings替代openpyxl的， 但执行时可能会报错-1743, 参考该文章: https://zhuanlan.zhihu.com/p/426951278
# 可以直接在系统terminal中执行, 会弹出terminal的相关授权框
# 实际是在 `System Preferences...` -> `Security & Privacy` -> `Privacy` -> `Automation` 中, 但该选项无法手动添加
appscript.reference.CommandError: Command failed:
                OSERROR: -1743
                MESSAGE: The user has declined permission.
                COMMAND: app('/System/Library/CoreServices/System Events.app').processes[its.unix_id == 7987].visible.set(True)
```

## 工资条+邮箱 excel 信息验证处理
背景: 邮箱汇总excel中经常会出现邮箱名带空格, 或者姓名换行,带空格的情况,导致匹配不到,因此需要对数据进行清洗

对邮箱excel新增以下列:
A    B     C   D  
序号  姓名  社区 邮箱
数据从第3行开始,242行结束, 共计240个人

1. 在开头插入一列(假设为A列), 公式是: `=concat(D3,C3)` 拼接生成社区+姓名信息,用于匹配
2. 再最后新增一列检测社区姓名是否包含空格: `=find(" ", A3)` 对于不存在空格的会显示结果为: #value!, 通过excel过滤功能查看显示为具体数字的单元格,进行修改
3. 新增一列检测邮箱(假设为E列)是否包含空格: `=find(" ", E3)`, 过滤操作同上 
4. 新增一列检测邮箱(假设为E列)是否包含@符号: `=find("@", E3)`, 过滤操作同上
5. 新增一列检测邮箱(假设为E列)是否包含@符号: `=find(".com", E1)`, 过滤操作同上
6. 新增一列检测邮箱是否重复(假设邮箱列表区域为:E3:E242): `=COUNTIF(E$3:E$242,E3)`, 过滤出数量为2及以上的数据, 进行修改

对工资表excel新增以下列并检测:
B列是姓名 C列是社区 Z列是工资卡号, 人员信息从第5行开始

1. 在工资表最右边插入一列社区+姓名列(AA列): `=concat(C5,B5)` 
2. 新增一列AB列,根据 社区+姓名 列匹配邮箱信息: `=VLOOKUP(AA5,'邮箱汇总.xls]Sheet1'!$B$3:$E$242,4,FALSE)`
3. 将邮箱列复制并选择性粘贴到AA列中

## 工资条分割+邮件发送

1. 参考模板工资条汇总单: `assets/template_salary.xlsx` 自行根据 社区+姓名 来匹配搜索得到对应的邮箱信息,拼接到表格最后一列
    比如原始工资条区域是 A1:Z4, 则邮箱拼接到 Z 列的后一列, 也就是 AA 列
    之所以要用 '社区+姓名' 来匹配邮箱,是因为存在少数同名人员
2. 将工资条区域(包含邮箱列)复制并选择性粘贴为值内容
    此举是因为截图时,有公式的单元格会显示为空白,内容丢失
3. 执行 `src/SplitSalaryInfo.py` 脚本, 传入工资excel文件的绝度路径, 并设置分割参数(见 `src/config.ini`)
    p.s. 截图时,建议电脑屏幕不要锁屏,也不要有其他复制操作,测试下来比较容易截图失败
4. 执行完成后,默认不自动发送邮件,会将每个人的工资条截图存放于 excel 文件同目录下自动生成的 `imageCache/{年月日_时分秒}/` 子目录下 
5. 自行随机挑选几张进行验证(主要验证姓名/社区/邮箱/调资居龄/应发工资等内容), 确保数据准确, 可挑几个不同社区不同人进行验证
6. 运行 `src/SendSalaryEmail.py` 来进行邮件发送,按需传入截图所在目录路径即可
    发送后会在截图同目录下生成 `send_mail_success_history.txt` 发送成功的历史记录文件
    若有发送失败的需要重新发送,则重新运行该脚本即可自动跳过成功的部分