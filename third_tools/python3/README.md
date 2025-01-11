# python3非安装版本

对应版本及下载地址：

## windows:

*[官网下载页面](https://www.python.org/downloads/windows/)

Python 3.10.9 - Dec. 6, 2022
Note that Python 3.10.9 cannot be used on Windows 7 or earlier.
[Download Windows embeddable package (64-bit)](https://www.python.org/ftp/python/3.10.9/python-3.10.9-embed-amd64.zip)

通过 `third_tools/python3/windows/python3.exe -m site` 查看 site-packages 目录路径
当前 `third_tools/python3/windows/` 本身就是, 目前我内聚了 pycryptodome (Crypto目录) 和 zstd 库
若后续需要其他库, 则下载后将对应的库文件放到上述目录下即可

## macos

由于是安装版本， 因此未添加到本项目中

* [官网下载页面](https://www.python.org/downloads/macos/)

Python 3.10.9 - Dec. 6, 2022
[Download macOS 64-bit universal2 installer](https://www.python.org/ftp/python/3.10.9/python-3.10.9-macos11.pkg)


## Linux

我使用的KUbuntu22.10已内置python3.10
