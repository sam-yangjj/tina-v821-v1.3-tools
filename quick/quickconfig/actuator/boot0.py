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
import re

from quickconfig.utils import backup_file, DiffSummary


def update_boot0_config(config, modify_list):
    modified_config = {}  # Dictionary to store modified configuration items
    # Iterate through the modify list to update configuration items
    for key, new_value in modify_list.items():
        if key in config:
            item = config[key]
            is_modified = False  # Flag to check if modification is done

            if isinstance(new_value, bool):
                # If the value in modify list is a boolean
                if new_value:  # True
                    if item['is_commented']:  # If currently commented, uncomment
                        item['is_commented'] = False
                        is_modified = True
                    if item['value']:  # If there is a value, change it to 'y'
                        item['value'] = 'y'
                        is_modified = True
                else:  # False
                    if item['is_commented']:  # If already commented, don't modify
                        continue
                    if item['value']:  # If there is a value, change it to 'n'
                        item['value'] = 'n'
                        is_modified = True
            elif new_value is None:
                if item['is_commented']:  # If already commented, don't modify
                    continue
                if item['value']:  # If there is a value, comment it out
                    item['is_commented'] = True
                    is_modified = True
            else:
                # If the value in modify list is a string
                if item['is_commented']:  # If currently commented, uncomment
                    item['is_commented'] = False
                    is_modified = True
                if item['value'] != new_value:  # If current value differs, update it
                    item['value'] = new_value
                    is_modified = True

            # If any modification was made, add it to the result
            if is_modified:
                modified_config[key] = item
        else:
            # If the configuration item doesn't exist, add it
            if new_value is None:
                modified_config[key] = {'is_commented': True, 'value': 'y'}
            else:
                modified_config[key] = {'is_commented': False, 'value': new_value}

    # Update the original configuration with the modified ones
    config.update(modified_config)
    return modified_config


def boot0_process_config(file_path, config):
    # Read the content of the file
    with open(file_path, 'r') as file:
        lines = file.readlines()

    result = []
    added_new_config = set()

    # Iterate through each line of the file to check if modifications are needed
    for line in lines:
        modified = False
        stripped_line = line.lstrip('#').strip()  # Remove the leading # and strip whitespaces
        for key, value in config.items():
            if stripped_line.startswith(key):  # If the stripped line starts with the key
                if value['is_commented']:  # If the item needs to be commented out
                    result.append(f"# {key}={value['value']}\n")
                else:  # Otherwise, replace or modify the value
                    if isinstance(value['value'], bool):
                        if value['value']:
                            result.append(f"{key}=y\n")
                        else:
                            result.append(f"{key}=n\n")
                    else:
                        result.append(f"{key}={value['value']}\n")
                modified = True
                added_new_config.add(key)
                break

        # If no modification was done for this line, keep the original line
        if not modified:
            result.append(line)

    # If a configuration item wasn't found in the file, append it at the end
    for key, value in config.items():
        if key not in added_new_config:
            if value['is_commented']:
                result.append(f"# {key}={value['value']}\n")
            else:
                if isinstance(value['value'], bool):
                    if value['value']:
                        result.append(f"{key}=y\n")
                    else:
                        result.append(f"{key}=n\n")
                else:
                    result.append(f"{key}={value['value']}\n")

    # Write the processed content back to the file
    with open(file_path, 'w') as file:
        file.writelines(result)


class act_boot0:
    def __init__(self, boot0_path):
        self.boot0_path = boot0_path

    def parse_boot0_config(self, val):
        # Initialize an empty dictionary to store key-value pairs of the configuration items
        config_dict = {}

        # Use a regular expression to match the format of configuration items: key = value
        pattern = re.compile(r"^([A-Za-z0-9_]+)\s*=\s*(\S+)\s*$")

        # Check if the provided 'val' is a dictionary
        if not isinstance(val, dict):
            # If 'val' is not a dictionary, print an error message and terminate the program
            print('boot0 : invalid format, need dict')
            sys.exit(1)

        # Iterate over each file name and its corresponding settings in the 'val' dictionary
        for file_name, settings in val.items():
            # Build the full path of the configuration file
            config_file_path = f"{self.boot0_path}/{file_name}"

            # Check if the configuration file path exists
            if not os.path.exists(config_file_path):
                # If the file path does not exist, print an error message and terminate the program
                print(f'boot0: invalid config path: {config_file_path}')
                sys.exit(1)

            # Backup the current configuration file for later restoration
            backup_file(config_file_path)

            # Initialize an empty dictionary to store the modified configuration items
            after_config = {}

            # Initialize an empty dictionary to store the original configuration items
            config_dict = {}

            # Open the configuration file and read it line by line
            with open(config_file_path, 'r') as file:
                for line in file:
                    # Strip leading and trailing whitespace from each line
                    line = line.strip()

                    # Skip the line if it is empty
                    if not line:
                        continue

                    # If the line is a comment (starts with '#')
                    if line.startswith("#"):
                        # Remove the '#' symbol and leading whitespace from the comment
                        commented_key = line.lstrip('#').strip()

                        # Use the regular expression to check if the configuration item matches the expected format
                        match = pattern.match(commented_key)
                        if match:
                            # If the match is successful, add the configuration item to the dictionary and mark it as commented
                            key, value = match.groups()
                            config_dict[key] = {"value": value, "is_commented": True}
                    else:
                        # If the line is not a comment, continue with the regular expression match
                        match = pattern.match(line)
                        if match:
                            # If the match is successful, add the configuration item to the dictionary and mark it as non-commented
                            key, value = match.groups()
                            config_dict[key] = {"value": value, "is_commented": False}

                # Update the configuration dictionary based on the provided settings
                after_config = update_boot0_config(config_dict, settings)

            # Apply the updated configuration to the configuration file
            boot0_process_config(config_file_path, after_config)

            # Record the differences between the original configuration and the updated configuration
            diff = DiffSummary()
            diff.record_diff(config_file_path)

        # After the function completes, return or perform other operations (return or termination is not implemented here)
        pass
