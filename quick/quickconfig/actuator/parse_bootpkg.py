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
format:
"bootpkg" : {
    "item_name" : val    重新设置val
    "item_name-enable" : 0/1    添加或减少item
}
'''

from quickconfig.utils import backup_file, DiffSummary


class act_parse_bootpkg:
    def __init__(self, bootpkg_path):
        self.bootpkg_path = bootpkg_path

    def set_bootpkg(self, option, item, val=None):
        done = False

        compress_suffix = {
            '-gz': '.gz',
            '-lzma': '.lzma',
            '-lz4': '.lz4',
        }
        valid_option = ['set', 'enable', 'disable']

        if option not in valid_option:
            print("bootpkg invalid option {} for {}" % (option, item))
            return -1

        if option == 'set' and val == None:
            print("parse bootpkg %s %s failed" % (option, item))
            return -1

        with open(self.bootpkg_path, 'r') as f:
            lines = f.readlines()

        f = open(self.bootpkg_path, 'w')
        for line in lines:
            match = re.match(r'^(;?)item=([a-z0-9-_\.]+)(,[ \t]*)([a-z0-9-_\.]+)(,?)$', line)

            if not match or done:
                f.write(line)
                continue
            item_name = match.group(2)
            for ignore in compress_suffix.keys():
                if item_name.endswith(ignore):
                    item_name = item_name[:-len(ignore)]
                    break
            if item != item_name:
                f.write(line)
                continue
            if option == 'enable':
                newline = '' + 'item=' + match.group(2) + match.group(3) + match.group(4) + match.group(5)
            elif option == 'disable':
                newline = ';' + 'item=' + match.group(2) + match.group(3) + match.group(4) + match.group(5)
            else:
                for k, v in compress_suffix.items():
                    if val.endswith(v):
                        item_name = item_name + k
                        break
                newline = match.group(1) + 'item=' + item_name + match.group(3) + val + match.group(5)
            f.write(newline + '\n')
            done = True
        if not done:
            newline = match.group(1) + 'item=' + item + match.group(3) + val + match.group(5)
            f.write(newline + '\n')
        f.close()
        return 0

    def get_bootpkg(self, item):
        with open(self.bootpkg_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            match = re.match(r'^(;?)item=([a-z0-9-_\.]+)(,[ \t]*)([a-z0-9-_\.]+)(,?)$', line)
            if not match or item != match.group(2):
                f.write(line)
                continue
            return match.group(4)
        return None

    def parse_bootpkg(self, v):
        '''
        format:
        "bootpkg" : {
            "item_name" : val    重新设置val
            "item_name-enable" : 0/1    添加或减少item
        }
        '''
        backup_file(self.bootpkg_path)
        for item, val in v.items():
            # print("\t%s : %s" % (item, val))
            if item.endswith('-enable'):
                item = item[:-len('-enable')]
                if val == 1:
                    self.set_bootpkg('enable', item)
                else:
                    self.set_bootpkg('disable', item)
            else:
                self.set_bootpkg('set', item, val)

        diff_summary = DiffSummary()
        diff_summary.record_diff(self.bootpkg_path)
