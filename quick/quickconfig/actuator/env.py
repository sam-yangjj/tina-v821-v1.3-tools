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
sysconfig" : {
    "mainkey" : {
        "subkey1" : val1,
        "subkey2" : val2
    }
}
'''

from quickconfig.utils import backup_file, DiffSummary, do_cmd


class act_env:
    def __init__(self, env_path):
        self.env_path = env_path

    def parse_env_cfg(self, val):
        work_path = os.path.dirname(self.env_path) + '/'
        tmp_file = '{}/.quick_config_tmp_env'.format(work_path)

        if not isinstance(val, list):
            print('env : invalid format, need list')
            sys.exit(1)
        item_dict = {}

        backup_file(self.env_path)

        cmd = 'cp {} {}'.format(self.env_path, tmp_file)
        do_cmd(cmd)

        for val_dict in val:
            if 'name' not in val_dict.keys():
                print('env : {} invalid format, need name'.format(val_dict))
                continue
            if 'method' not in val_dict.keys():
                print('env : {} invalid format, need method'.format(val_dict))
                continue

            name = val_dict['name']
            method = val_dict['method']
            if method == 'add' or method == 'append':
                if 'val' not in val_dict.keys():
                    print('env : {} invalid format, need val'.format(val_dict))
                    continue
                v = val_dict['val']
            elif method == 'del':
                v = None
            else:
                print('env : {} invalid method'.format(val_dict))
                continue
            item_dict[name] = {}
            item_dict[name]['val'] = v
            item_dict[name]['method'] = method
            item_dict[name]['done'] = 0

        fenv = open(self.env_path, 'w')
        with open(tmp_file, 'r') as f:
            for line in f:
                if line.strip().startswith('#'):
                    fenv.write(line)
                elif '=' in line:
                    l = line.strip().split('=', 1)
                    key = l[0].strip()
                    v = l[1].strip()
                    if key in item_dict.keys():
                        if item_dict[key]['method'] == 'add':
                            tmp = '{}={}\n'.format(key, item_dict[key]['val'])
                            fenv.write(tmp)
                        elif item_dict[key]['method'] == 'del':
                            continue
                        elif item_dict[key]['method'] == 'append':
                            if item_dict[key]['val'] not in line:
                                if line[-1] == '\n':
                                    line = line[:-1]
                                line = line + item_dict[key]['val'] + '\n'
                            fenv.write(line)
                        item_dict[key]['done'] = 1
                    else:
                        fenv.write(line)
                else:
                    # unkonw line
                    fenv.write(line)

        # Add new entries at the end if they are not already written
        for key, data in item_dict.items():
            if data['done'] == 0:
                if data['method'] == 'add':
                    tmp = '{}={}\n'.format(key, data['val'])
                    fenv.write(tmp)
                elif data['method'] == 'append':
                    tmp = '{}={}\n'.format(key, data['val'])
                    fenv.write(tmp)

        fenv.close()

        cmd = 'rm {}'.format(tmp_file)
        do_cmd(cmd)

        diff = DiffSummary()
        diff.record_diff(self.env_path)
