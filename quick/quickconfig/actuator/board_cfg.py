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

'''"BoardConfig" : {
    "LICHEE_FLASH" : "default",			# Modify value
    "LICHEE_RTOS_PROJECT_NAME" : null,	# Delete item
    "LICHEE_XXXXXX" : "add",			# Add item
},

"BoardConfigItem": {
    "LICHEE_SPL_BOARD_MK": {
        "spinor-cfg_nor_fastboot": null, # Delete item
        "spinor-cfg_meta_param": true,   # Add item
    }
}'''

from quickconfig.utils import backup_file, DiffSummary, do_cmd_with_output, do_cmd


class act_board_config:
    def __init__(self, BoardConfig_path):
        self.BoardConfig_path = BoardConfig_path

    def parse_board_cfg(self, val):
        if not isinstance(val, dict):
            print('partition : invalid format, need dict')
            sys.exit(1)
        cmd_bak = ""
        backup_file(self.BoardConfig_path)
        for k, v in val.items():
            cmd = 'grep -Eo \'{}\' {}'.format(k, self.BoardConfig_path)
            ret, out = do_cmd_with_output(cmd)
            if ret == 0:
                if v != None:
                    cmd = 'sed -i \'s/^{}:=.*/{}:={}/g\' {}'.format(k, k, v, self.BoardConfig_path)
                    cmd_bak = 'sed -i \'s#^{}:=.*#{}:={}#g\' {}'.format(k, k, v, self.BoardConfig_path)
                else:
                    cmd = 'sed -i \'/{}:=/d\' {}'.format(k, self.BoardConfig_path)
                    cmd_bak = 'sed -i \'#{}:=#d\' {}'.format(k, self.BoardConfig_path)
            else:
                if v != None:
                    cmd = 'echo "{}:={}" >> {}'.format(k, v, self.BoardConfig_path)
            ret = do_cmd(cmd)
            if ret != 0:
                do_cmd(cmd_bak)
        diff = DiffSummary()
        diff.record_diff(self.BoardConfig_path)
        return

    def parse_board_multi_string_cfg(self, val):
        # Backup file
        backup_file(self.BoardConfig_path)

        # Read file content
        with open(self.BoardConfig_path, 'r') as file:
            text = file.readlines()

        # Modify file content directly in memory
        modified = False
        # Track which board_keys have been processed
        processed_keys = set()

        for board_key, board_config in val.items():
            key_found = False
            for i, line in enumerate(text):
                if board_key in line and ':=' in line:
                    key_found = True
                    processed_keys.add(board_key)
                    # Extract current configuration value and remove quotes and escape characters
                    current_config = line.split(':=')[1].strip()
                    # Handle possible quotes and escaped quotes
                    if current_config.startswith('"') and current_config.endswith('"'):
                        current_config = current_config[1:-1]
                    elif current_config.startswith('\\"') and current_config.endswith('\\"'):
                        current_config = current_config[2:-2]

                    # Split configuration items
                    updated_config = current_config.split()

                    # Update configuration items
                    config_modified = False
                    for config_item, value in board_config.items():
                        if value is True:
                            if config_item not in updated_config:
                                updated_config.append(config_item)
                                config_modified = True
                        elif value is None:
                            if config_item in updated_config:
                                updated_config.remove(config_item)
                                config_modified = True

                    # Build new configuration line, ensuring correct escaped quote format
                    if config_modified:
                        updated_config_str = " ".join(updated_config)
                        # Format as: KEY:="value1 value2 value3"
                        new_line = board_key + ":=\\\"" + updated_config_str + "\\\"\n"
                        text[i] = new_line
                        modified = True

            # Handle case where board_key doesn't exist in file
            if not key_found:
                # Create new configuration items list
                new_config_items = []
                for config_item, value in board_config.items():
                    if value is True:  # Only add items marked as True for new keys
                        new_config_items.append(config_item)

                if new_config_items:  # Only add the key if there are items to add
                    updated_config_str = " ".join(new_config_items)
                    # Format as: KEY:="value1 value2 value3"
                    new_line = board_key + ":=\\\"" + updated_config_str + "\\\"\n"
                    text.append(new_line)
                    modified = True

        # If modified, write back to file directly
        if modified:
            with open(self.BoardConfig_path, 'w') as file:
                file.writelines(text)

        diff = DiffSummary()
        diff.record_diff(self.BoardConfig_path)
