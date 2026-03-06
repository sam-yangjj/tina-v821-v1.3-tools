#!/usr/bin/env python3
# Copyright (c) 2019-2025 Allwinner Technology Co., Ltd. ALL rights reserved.
#
# Allwinner is a trademark of Allwinner Technology Co.,Ltd., registered in
# the people's Republic of China and other countries.
# All Allwinner Technology Co.,Ltd. trademarks are used with permission.
#
# DISCLAIMER
# THIRD PARTY LICENCES MAY BE REQUIRED TO IMPLEMENT THE SOLUTION/PRODUCT.
# IF YOU NEED TO INTEGRATE THIRD PARTY’S TECHNOLOGY (SONY, DTS, DOLBY, AVS OR MPEGLA, ETC.)
# IN ALLWINNERS’SDK OR PRODUCTS, YOU SHALL BE SOLELY RESPONSIBLE TO OBTAIN
# ALL APPROPRIATELY REQUIRED THIRD PARTY LICENCES.
# ALLWINNER SHALL HAVE NO WARRANTY, INDEMNITY OR OTHER OBLIGATIONS WITH RESPECT TO MATTERS
# COVERED UNDER ANY REQUIRED THIRD PARTY LICENSE.
# YOU ARE SOLELY RESPONSIBLE FOR YOUR USAGE OF THIRD PARTY’S TECHNOLOGY.
#
# THIS SOFTWARE IS PROVIDED BY ALLWINNER"AS IS" AND TO THE MAXIMUM EXTENT
# PERMITTED BY LAW, ALLWINNER EXPRESSLY DISCLAIMS ALL WARRANTIES OF ANY KIND,
# WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING WITHOUT LIMITATION REGARDING
# THE TITLE, NON-INFRINGEMENT, ACCURACY, CONDITION, COMPLETENESS, PERFORMANCE
# OR MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
# IN NO EVENT SHALL ALLWINNER BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS, OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Author: Yuanjing Zhang <zhangyuanjing@allwinnertech.com>
#

import os, sys
import argparse
import re
import subprocess

'''
"defconfig" : [
	"fragment文件名 or 配置名 or !配置名(表示去掉某个配置)"
    "lock_defconfig.fragment", "ftrace_defconfig.fragment",
    "# CONFIG_AW_GPADC is not set", "CONFIG_LOG_BUF_SHIFT=15"
],
'''

from quickconfig.utils import backup_file, restore_file, DiffSummary, do_cmd


def find_target_file(search_path, file_name):
    for path in search_path:
        p = path + '/' + file_name
        if os.path.exists(p):
            return p
    return None


def merge_config(defconfig, fragment):
    config_list = {}
    work_path = os.path.dirname(defconfig)
    tmp_file = '{}/.quick_config_tmp_defconfig'.format(work_path)

    cmd = 'cp {} {}'.format(defconfig, tmp_file)
    do_cmd(cmd)
    output = open(defconfig, 'w')

    with open(fragment, 'r') as f:
        for line in f:
            if 'CONFIG_' not in line:
                continue
            if '=' in line:
                # CONFIG_xxx=y
                config_name = line.split('=')[0].strip()
            else:
                # # CONFIG_xxx is not set
                config_name = line.split()[1].strip()
            config_list[config_name] = line

    with open(tmp_file, 'r') as f:
        for line in f:
            if '=' in line:
                config_name = line.split('=')[0].strip()
            else:
                if len(line.split()) < 5:
                    output.write(line)
                    continue
                config_name = line.split()[1].strip()
            if not config_name.startswith('CONFIG_'):
                output.write(line)
                continue
            # print('parse: {}, {}'.format(line, config_name))
            if config_name in config_list.keys():
                output.write(config_list[config_name])
                config_list[config_name] = None
            else:
                output.write(line)
    for k in config_list.keys():
        if config_list[k] == None:
            continue
        output.write(config_list[k])
    output.close()
    do_cmd('rm {}'.format(tmp_file))


class act_openwrt_defconfig:
    def __init__(self, defconfig_path, env):
        self.defconfig = defconfig_path
        self.top_dir = env.get("top_dir")
        self.board_config_dir = env.get("board_config_dir")
        self.bsp_path = env.get("bsp_path")
        self.configs = env.get("configs")

    def parse_openwrt_defconfig(self, search_path, openwrt_dir, val):
        work_path = os.path.dirname(self.defconfig) + '/'
        tmpfile = '.tmp.fragment'
        special_conf = []
        dot_config = '{}/.config'.format(openwrt_dir)

        if not isinstance(val, list):
            print('kernel : invalid format, need list')
            sys.exit(1)

        if not search_path:
            print('current unsupport .fragment file')

        cmd = 'cp {} {}'.format(self.defconfig, dot_config)
        ret = do_cmd(cmd)
        if ret < 0:
            print('exec {} failed, ret = {}'.format(cmd, ret))
            return

        backup_file(self.defconfig)
        for item in val:
            if item.endswith('.fragment'):
                if not search_path:
                    continue
                p = find_target_file(search_path, item)
                if not p:
                    print('{} does not exist'.format(item))
                    continue
                merge_config(dot_config, p)
            else:
                if item[0] == '#':
                    # CONFIG_XXXX is not set
                    item = item.split()[1].strip()
                    if '=' in item:
                        item = item.split('=')[0].strip()
                    cfgline = '# {} is not set'.format(item)
                elif '=' in item:
                    cfgline = '{}'.format(item.strip())
                special_conf.append(cfgline)

        if len(special_conf) > 0:
            with open(work_path + tmpfile, 'w') as f:
                for item in special_conf:
                    f.write(item + '\n')
            merge_config(dot_config, work_path + tmpfile)

        cmd = '{}/build.sh openwrt_rootfs defconfig'.format(self.top_dir)
        ret = do_cmd(cmd)
        if ret < 0:
            print('exec {} failed, ret = {}'.format(cmd, ret))
            restore_file(self.defconfig)
            return

        cmd = 'cp {} {}'.format(dot_config, self.defconfig)
        ret = do_cmd(cmd)
        if ret < 0:
            print('exec {} failed, ret = {}'.format(cmd, ret))
            restore_file(self.defconfig)
            return

        if len(special_conf) > 0:
            cmd = "rm {}".format(work_path + tmpfile)
            do_cmd(cmd)

        diff = DiffSummary()
        diff.record_diff(self.defconfig)
