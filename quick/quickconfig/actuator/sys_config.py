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

'''
"sysconfig" : {
    /*
    * 规则:
    *   "mainkey" : {
    *       "subkey" : val   重新设置val,字符串需要添加\"str\"
    *    }
    */
}

"rtos_sysconfig" : {
    /*
    * 规则:
    *   "mainkey" : {
    *       "subkey" : val   重新设置val,字符串需要添加\"str\"
    *    }
    */
}

"del_property" : {
    /*
    * 删除属性规则:
    *   "mainkey" : {
    *       "subkey" : "del"   删除指定的subkey
    *    }
    */
}
'''

import sys
import os
import argparse
import re
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from quickconfig.utils import backup_file, DiffSummary

class act_sys_config:
    def __init__(self, sysconfig_path):
        self.sysconfig_path = sysconfig_path

    def get_lichee_flash_from_sys_config(self):
        if os.path.exists(self.sysconfig_path):
            with open(self.sysconfig_path, 'r') as f:
                for line in f:
                    if line.startswith('storage_type'):
                        storage_type = line.split('=')[1].strip()
                        break

        if storage_type == "3":
            return "nor"
        elif storage_type == "5":
            return "nand"
        else:
            return "default"

    def del_config_value(self, mainkey, subkey):
        """Delete a config value from the sysconfig file"""
        with open(self.sysconfig_path, 'r') as file:
            lines = file.readlines()

        found_mainkey = False
        new_lines = []
        deleted = False

        for i, line in enumerate(lines):
            if line.strip() == f"[{mainkey}]":
                found_mainkey = True
                new_lines.append(line)
                continue

            if found_mainkey:
                # Check if line starts with subkey followed by whitespace or =
                line_stripped = line.strip()
                if line_stripped.startswith(subkey):
                    # Check if it's exactly this subkey (followed by whitespace or =)
                    remaining = line_stripped[len(subkey):].strip()
                    if remaining.startswith('=') or remaining == '':
                        # Skip this line (delete it)
                        deleted = True
                        continue
                if line.strip().startswith("[") and line.strip() != f"[{mainkey}]":
                    # Reached next mainkey section
                    found_mainkey = False

            new_lines.append(line)

        if not deleted:
            print(f"Warning: subkey '{subkey}' not found in mainkey '{mainkey}'")
            return -1

        with open(self.sysconfig_path, 'w') as file:
            file.writelines(new_lines)

        return 0

    def del_config_value_from_lines(self, lines, mainkey, subkey):
        """Delete a config value from lines (in-memory version)"""
        found_mainkey = False
        new_lines = []
        deleted = False

        for i, line in enumerate(lines):
            if line.strip() == f"[{mainkey}]":
                found_mainkey = True
                new_lines.append(line)
                continue

            if found_mainkey:
                # Check if line starts with subkey followed by whitespace or =
                line_stripped = line.strip()
                if line_stripped.startswith(subkey):
                    # Check if it's exactly this subkey (followed by whitespace or =)
                    remaining = line_stripped[len(subkey):].strip()
                    if remaining.startswith('=') or remaining == '':
                        # Skip this line (delete it)
                        deleted = True
                        continue
                if line.strip().startswith("[") and line.strip() != f"[{mainkey}]":
                    # Reached next mainkey section
                    found_mainkey = False

            new_lines.append(line)

        if not deleted:
            print(f"Warning: subkey '{subkey}' not found in mainkey '{mainkey}'")
            return -1, lines

        return 0, new_lines

    def set_config_value(self, mainkey, subkey, val):
        with open(self.sysconfig_path, 'r') as file:
            lines = file.readlines()

        found_mainkey = False
        found_subkey = False
        new_lines = []
        mainkey_start_line = -1

        for i, line in enumerate(lines):
            if line.strip() == f"[{mainkey}]":
                found_mainkey = True
                found_subkey = False
                mainkey_start_line = i
                new_lines.append(line)
                continue

            if found_mainkey and not found_subkey:
                if line.strip().startswith(subkey):
                    new_lines.append(f"{subkey} = {val}\n")
                    found_subkey = True
                    continue
                if line.strip().startswith("[") and line.strip() != f"[{mainkey}]":
                    new_lines.append(f"{subkey} = {val}\n")
                    new_lines.append(line)
                    found_subkey = True
                    found_mainkey = False
                    continue

            new_lines.append(line)

        if not found_mainkey:
            new_lines.append(f"\n[{mainkey}]\n")
            new_lines.append(f"{subkey} = {val}\n")
        elif found_mainkey and not found_subkey:
            insert_pos = len(new_lines)
            for i in range(mainkey_start_line + 1, len(new_lines)):
                if new_lines[i].strip().startswith("["):
                    insert_pos = i
                    break
            new_lines.insert(insert_pos, f"{subkey} = {val}\n")

        with open(self.sysconfig_path, 'w') as file:
            file.writelines(new_lines)

    def parse_sysconfig(self, v):
        if not isinstance(v, dict):
            print('sysconfig : invalid format, need { }')
            return 0

        backup_file(self.sysconfig_path)

        with open(self.sysconfig_path, 'r') as file:
            lines = file.readlines()

        new_lines = []

        for line in lines:
            new_lines.append(line)

        # Handle del_property first (before normal property processing)
        if 'del_property' in v.keys():
            items = v['del_property']
            if not isinstance(items, dict):
                print('sysconfig : del_property invalid format, need { }')
                return 0
            for mainkey, subkeys in items.items():
                if not isinstance(subkeys, dict):
                    print('sysconfig : del_property invalid item format, need { }')
                    return 0
                for subkey, subval in subkeys.items():
                    ret, new_lines = self.del_config_value_from_lines(new_lines, mainkey, subkey)
                    if ret < 0:
                        print(f'parse del_property {subkey}: {subval} failed')
                        return 0

        for mainkey, subkeys in v.items():
            if mainkey == 'del_property':
                continue  # Skip del_property as it's already handled
            if not isinstance(subkeys, dict):
                continue

            found_mainkey = False
            found_subkeys = set()
            mainkey_start_idx = -1
            mainkey_end_idx = -1

            for i, line in enumerate(new_lines):
                if line.strip() == f"[{mainkey}]":
                    found_mainkey = True
                    mainkey_start_idx = i
                    for j in range(i + 1, len(new_lines)):
                        if new_lines[j].strip().startswith("[") and new_lines[j].strip() != f"[{mainkey}]":
                            mainkey_end_idx = j - 1
                            break
                    if mainkey_end_idx == -1:
                        mainkey_end_idx = len(new_lines) - 1
                    break

            if found_mainkey:
                temp_lines = []
                i = mainkey_start_idx + 1

                while i <= mainkey_end_idx:
                    line = new_lines[i]
                    line_stripped = line.strip()

                    if line_stripped and not line_stripped.startswith("#"):
                        parts = line_stripped.split("=", 1)
                        if len(parts) == 2:
                            current_subkey = parts[0].strip()
                            if current_subkey in subkeys:
                                val = subkeys[current_subkey]
                                original_val = parts[1].strip()
                                if original_val.startswith('0x') and isinstance(val, (int, str)):
                                    try:
                                        int_val = int(val)
                                        hex_str = f"0x{int_val:02x}"
                                        temp_lines.append(f"{current_subkey} = {hex_str}\n")
                                    except (ValueError, TypeError):
                                        temp_lines.append(f"{current_subkey} = {val}\n")
                                else:
                                    temp_lines.append(f"{current_subkey} = {val}\n")
                                found_subkeys.add(current_subkey)
                            else:
                                temp_lines.append(line)
                        else:
                            temp_lines.append(line)
                    else:
                        temp_lines.append(line)

                    i += 1

                for subkey, val in subkeys.items():
                    if subkey not in found_subkeys:
                        temp_lines.append(f"{subkey} = {val}\n")

                new_lines[mainkey_start_idx + 1:mainkey_end_idx + 1] = temp_lines
            else:
                new_lines.append(f"\n[{mainkey}]\n")
                for subkey, val in subkeys.items():
                    new_lines.append(f"{subkey} = {val}\n")

        with open(self.sysconfig_path, 'w') as file:
            file.writelines(new_lines)

        diff_summary = DiffSummary()
        diff_summary.record_diff(self.sysconfig_path)

        return 0