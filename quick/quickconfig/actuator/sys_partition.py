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

from quickconfig.utils import backup_file, restore_file, DiffSummary, do_cmd


def _find_part_info(info, name):
    for v in info:
        if name == v['name']['val']:
            return v
    return None


class act_sys_partition:
    def __init__(self, partition_path, env):
        self.partition_path = partition_path

    def _get_partition_info(self):
        item_dict = []
        tmp_dict = {}

        with open(self.partition_path, 'r') as f:
            lines = f.readlines()

        line_num = 0
        for line in lines:
            line_num = line_num + 1
            sline = line.strip()
            if sline.startswith(';'):
                continue
            if re.match(r'^\[mbr\]', sline):
                if 'name' in tmp_dict.keys():
                    tmp_dict['end'] = line_num - 1
                    item_dict.append(tmp_dict.copy())
                    tmp_dict.clear()
                tmp_dict['name'] = {}
                tmp_dict['name']['val'] = 'mbr'
                tmp_dict['name']['line'] = line_num
                tmp_dict['start'] = line_num
                continue
            match = re.match(r'^\[partition\]', sline)
            if match:  # last partition end
                if 'name' in tmp_dict.keys():
                    tmp_dict['end'] = line_num - 1
                    item_dict.append(tmp_dict.copy())
                    tmp_dict.clear()
                tmp_dict['start'] = line_num
                if len(item_dict) > 0:
                    item_dict[-1]['part_end'] = line_num - 1
                continue
            if '=' not in sline:
                if 'name' in tmp_dict.keys():
                    tmp_dict['end'] = line_num - 1
                    tmp_dict['part_end'] = line_num - 1
                    item_dict.append(tmp_dict.copy())
                    tmp_dict.clear()
                continue
            items = sline.split('=')
            if len(items) < 2:
                print('{}:{} Invalid format\n'.format(self.partition_path, line_num))
                continue
            prop_name = items[0].strip()
            prop_val = items[1].strip()
            tmp_dict[prop_name] = {}
            tmp_dict[prop_name]['val'] = prop_val
            tmp_dict[prop_name]['line'] = line_num

        if 'name' in tmp_dict.keys():
            tmp_dict['end'] = line_num - 1
            tmp_dict['part_end'] = line_num
            item_dict.append(tmp_dict.copy())
            tmp_dict.clear()

        # for v in item_dict:
        #     print('{}:'.format(v))
        #     for k1,v1 in v.items():
        #         if 'end' == k1 or 'start' == k1:
        #             print('{} = {}\t'.format(k1, v1))
        #             continue
        #         print('{}\t{} = {}'.format(v1['line'], k1, v1['val']))

        return item_dict

    def parse_sys_partition(self, val):
        if not isinstance(val, list):
            print('partition : invalid format, need list')
            sys.exit(1)
        backup_file(self.partition_path)

        last_partition_end = 0
        for part in val:
            if not isinstance(part, dict):
                print('partition : invalid format, need dict')
                restore_file(self.partition_path)
                sys.exit(1)
            items_dict = self._get_partition_info()

            if 'del' in part.keys():
                if part['del'] == True:
                    is_del = True
                del part['del']
            else:
                is_del = False

            if 'name' not in part.keys():
                print('partition : invalid format, {}, skip...'.format(part))
                continue
            n = _find_part_info(items_dict, part['name'])
            if not n and is_del == False:  # new partition
                if last_partition_end == 0:  # inster at last
                    with open(self.partition_path, 'a') as f:
                        f.write('\n[partition]\n')
                        for k, v in part.items():
                            f.write('\t{} = {}\n'.format(k, v))
                else:
                    idx = last_partition_end
                    cmd = 'sed -i \'{}a \\[partition]\' {}'.format(idx, self.partition_path)
                    do_cmd(cmd)
                    idx = idx + 1
                    for k, v in part.items():
                        cmd = 'sed -i \'{}a \\\\t{} = {}\' {}'.format(idx, k, v, self.partition_path)
                        do_cmd(cmd)
                        idx = idx + 1
                continue
            else:
                if is_del == True:
                    # del partition
                    # sed -i '5,9d' file
                    if n:
                        cmd = 'sed -i \'{},{}d\' {}'.format(n['start'], n['part_end'], self.partition_path)
                        do_cmd(cmd)
                    continue
                for k, v in part.items():
                    if k == 'name':  # special name
                        continue
                    if k in n.keys():
                        ln = n[k]['line']
                        # sed -i 'lines s/\(.*=\s\+\)\(.*\)$/\1{new}/' file
                        cmd = 'sed -i \'{} s/\\(.*=\\s\\+\\)\\(.*\\)$/\\1{}/\' {}'.format(ln, v, self.partition_path)
                        do_cmd(cmd)
                    else:
                        ln = n['end']
                        cmd = 'sed -i \'{}a \\\\t{} = {}\' {}'.format(ln, k, v, self.partition_path)
                        do_cmd(cmd)

            last_partition_end = n['part_end']
        diff = DiffSummary()
        diff.record_diff(self.partition_path)
