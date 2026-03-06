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

from quickconfig.utils import backup_file, restore_file, DiffSummary, do_cmd_with_output, do_cmd


class act_common_defconfig:
    def __init__(self, defconfig_path, env, pre_parse_action=None, post_parse_action=None):
        self.defconfig = defconfig_path
        self.top_dir = env.get("top_dir")
        self.board_config_dir = env.get("board_config_dir")
        self.bsp_path = env.get("bsp_path")
        self.configs = env.get("configs")

        self.post_parse_action = post_parse_action
        self.pre_parse_action = pre_parse_action

    def merge_common_defconfig(self, fragment):
        framgment_list = [
            '{}'.format(os.path.dirname(self.defconfig)),
        ]
        fragment_path = fragment

        if os.path.exists(fragment):
            fragment_path = fragment
        else:
            for search in framgment_list:
                if os.path.exists('{}/{}'.format(search, fragment)):
                    fragment_path = '{}/{}'.format(search, fragment)
        if not os.path.exists(fragment_path):
            print('fragment: {} is not exist'.format(fragment))
            return -1

        new_line = True
        with open(fragment_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('#'):
                    conf_name = line.split()[1]
                else:
                    conf_name = line.split('=', 1)[0]
                cmd = 'grep -Eo \'\\b{}\\b\' {}'.format(conf_name, self.defconfig)
                ret, out = do_cmd_with_output(cmd)
                if ret == 0:
                    cmd = 'sed -i \'/{}[ =].*/ c {}\' {}'.format(conf_name, line, self.defconfig)
                else:
                    if new_line:
                        cmd = 'echo "\n" >> {}'.format(self.defconfig)
                        do_cmd(cmd)
                        new_line = False
                    if line[-1] == '"':  # is string?
                        conf_val = line.split('=', 1)[1]
                        cmd = 'echo {}=\\\"{}\\\" >> {}'.format(conf_name, conf_val, self.defconfig)
                    else:
                        cmd = 'echo "{}" >> {}'.format(line, self.defconfig)
                do_cmd(cmd)
        return 0

    def parse_common_defconfig(self, val):
        work_path = os.path.dirname(self.defconfig)
        tmpfile = work_path + '/.tmp.fragment'
        special_conf = []

        if not isinstance(val, list):
            print('uboot : invalid format, need list')
            sys.exit(1)

        backup_file(self.defconfig)
        for item in val:
            if item.endswith('.fragment'):
                ret = self.merge_common_defconfig(item)
                if ret < 0:
                    restore_file(self.defconfig)
                    sys.exit(1)
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
            with open(tmpfile, 'w') as f:
                for item in special_conf:
                    f.write(item + '\n')
            ret = self.merge_common_defconfig(tmpfile)
            if ret < 0:
                restore_file(self.defconfig)
                sys.exit(1)

        if self.post_parse_action:
            self.post_parse_action()

        if len(special_conf) > 0:
            cmd = "rm {}".format(tmpfile)
            do_cmd(cmd)

        diff = DiffSummary()
        diff.record_diff(self.defconfig)
