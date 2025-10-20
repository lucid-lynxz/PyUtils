# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
自动编译并拷贝编译产物到指定目录
具体以 config.ini 文件配置信息为准
"""

import os
import sys
import subprocess

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from util.CommonUtil import CommonUtil
from util.NetUtil import NetUtil
from util.FileUtil import FileUtil
from util.TimeUtil import TimeUtil

from base.BaseConfig import BaseConfig


class AutoBuildCopyApkImpl(BaseConfig):
    def __init__(self, configPath: str):
        super().__init__(configPath, optFirst=True, delimiters='=')

    def onRun(self):
        start_ts = TimeUtil.currentTimeMillis()
        projects = self.configParser.getSectionItems('projects').keys()

        # 适配命令中包含等号的场景
        buildCmds = self.configParser.getSectionItems('buildCmds')
        build_cmd_list = []
        for k, v in buildCmds.items():
            if CommonUtil.isNoneOrBlank(v):
                cmd = k.strip()
            else:
                cmd = f'{k.strip()}={v.strip()}'
            build_cmd_list.append(cmd.strip())

        CommonUtil.printLog(f'all build_cmd_list:{build_cmd_list}')

        setting = self.configParser.getSectionItems('setting')
        output_rel_path = setting['output_rel_path']
        target_parent_path = setting['target_parent_path'].rstrip('/')  # 目标目录路径, 自动删除结尾的 '/'
        project_info_file = setting['project_info_file']
        use_zsh = setting['use_zsh'] == 'True'  # 是否使用zsh进行编译
        backup_old_target = setting['backup_old_target'] == 'True'  # 是否备份现有的 target_parent_path 目录

        pending_copy_file_dict = self.configParser.getSectionItems('copy')  # 待拷贝的文件相对路径
        NetUtil.robot_dict = self.configParser.getSectionItems('robot')  # 推送消息设置

        if backup_old_target and FileUtil.isDirFile(target_parent_path):
            backup_path = f'{target_parent_path}_backup_{TimeUtil.getTimeStr(fmt="%Y%m%d_%H%M%S")}/'
            # FileUtil.copy(target_parent_path,backup_path)
            result = FileUtil.rename(target_parent_path, backup_path)
            NetUtil.push_to_robot(f'AutoBuildCopyApkImpl 备份{"成功" if result else "失败"}\n:{backup_path}')

        total_project_cnt = len(projects)
        progress = 0

        # 编译并提取 APK 文件
        fail_project = []  # 失败的项目路径信息
        for project in projects:
            start_ts_project = TimeUtil.currentTimeMillis()
            CommonUtil.printLog(f"\n\nProcessing project: {project}")

            # 切换到项目目录
            os.chdir(project)

            # 执行每个命令
            err_msg = ''
            cmd = ' && '.join(build_cmd_list)
            # for cmd in build_cmd_list:
            # -i: 表示交互模式（interactive mode），这会使 ZSH 加载用户的初始化文件（如 .zshrc），从而使别名和其他配置生效
            # -c: 表示从命令行传递一个命令来执行
            try:
                # cmd = f'java -version && {cmd}'
                CommonUtil.printLog(f'start exec cmd:{cmd}')
                if use_zsh:
                    result = subprocess.run(["zsh", "-ic", cmd], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                CommonUtil.printLog(result.stdout.decode('utf-8'))
            except subprocess.CalledProcessError as e:
                err_msg = f"exec cmd: {cmd} failed:{CommonUtil.safe_decode(e.stderr)}"
                CommonUtil.printLog(err_msg)
                break  # 如果其中一个命令失败，则不再执行后续命令

            project_name = FileUtil.getFileName(project)[0]
            output_dir_path = FileUtil.recookPath(f'{project}/{output_rel_path}/')
            target_dir_path = FileUtil.recookPath(f'{target_parent_path}/{project_name}/')
            FileUtil.createFile(target_dir_path, True)  # 清空目标目录文件
            CommonUtil.printLog(f'target_dir_path: {target_dir_path}')

            for k, v in pending_copy_file_dict.items():
                src_name = FileUtil.getFileName(k)[0]  # 文件名, 如: Demo.apk
                src_path = FileUtil.recookPath(f'{output_dir_path}/{k}')  # 源文件路径
                if CommonUtil.isNoneOrBlank(v):
                    v = src_name
                dst_path = FileUtil.recookPath(f'{target_dir_path}/{v}')

                if FileUtil.isFileExist(src_path):
                    CommonUtil.printLog(f'copy {src_path} --> {dst_path}')
                    FileUtil.copy(src_path, dst_path)
                else:
                    CommonUtil.printLog(f'{src_path} not exist')

            # 确认文件数量正常
            expected_cnt = len(pending_copy_file_dict)
            actual_files = FileUtil.listAllFilePath(target_dir_path)
            actual_cnt = len(actual_files)
            success = expected_cnt == actual_cnt
            CommonUtil.printLog(f'actual_files: {actual_files}')
            if not success:
                fail_project.append(project)
                CommonUtil.printLog(f'Expected {expected_cnt} files, but got {actual_cnt} files for {project}')

            # 读取编译信息内容文件
            info_msg = ''
            if not CommonUtil.isNoneOrBlank(project_info_file):
                info_file_path = FileUtil.recookPath(f'{output_dir_path}/{project_info_file}')
                info_msg = ''.join(FileUtil.readFile(info_file_path)).strip()
                if not CommonUtil.isNoneOrBlank(info_msg):
                    info_msg = f'\n\n{project_info_file}\n{info_msg}'

            if not CommonUtil.isNoneOrBlank(err_msg):
                err_msg = f'\n\nerr_msg:{err_msg[:200]}'

            progress += 1
            progress_tip = f'总进度: {progress} / {total_project_cnt}'

            delta_ms_project = TimeUtil.currentTimeMillis() - start_ts_project
            delta_time_project = TimeUtil.convertSecsDuration(delta_ms_project / 1000)
            time_consume_tip = f'耗时: {delta_time_project}'

            result_tip = f'成功' if success else '失败'
            NetUtil.push_to_robot(f'{project}\nAutoBuildCopyApkImpl {result_tip}\n{progress_tip}\n{time_consume_tip}{info_msg}{err_msg}')

            # 切换回原始目录
            os.chdir("..")

        new_line = '\n'
        fail_project_info = '' if CommonUtil.isNoneOrBlank(fail_project) else f"\n\n失败的项目: {new_line.join(fail_project)}"

        cmd_after_all = setting['exec_cmd_after_all']
        cmd_after_all_info = '' if CommonUtil.isNoneOrBlank(cmd_after_all) else f'\n\n正在执行命令:{cmd_after_all}'

        delta_ms = TimeUtil.currentTimeMillis() - start_ts
        total_time = TimeUtil.convertSecsDuration(delta_ms / 1000)
        NetUtil.push_to_robot(f'AutoBuildCopyApkImpl 已全部完成\n耗时:{total_time}{fail_project_info}{cmd_after_all_info}')

        if not CommonUtil.isNoneOrBlank(cmd_after_all):
            result = CommonUtil.exeCmdBySubprocess(cmd_after_all, timeout=600)
            NetUtil.push_to_robot(f'AutoBuildCopyApkImpl 执行命令:{cmd_after_all}\n结果:{result}')
