## 功能说明

已知手机序列号, 获取手机的其他信息,比如ip等, 将信息绘制在图片上并push到手机中, 然后打开并显示该图片

主要用于机房设备分散状态下不好查找的问题

## 使用

需要安装pillow和adb工具

1. 修改 `auto_show_phone_info/config.ini` 文件
2. 执行 `auto_show_phone_info/main.py` 即可

## 自定义 config.ini 文件

默认的 `auto_show_phone_info/config.ini` 文件通常作为模板作为参考

自定义操作:

```shell script
python3 auto_show_phone_info/main.py --config {custom_config_path}
```
