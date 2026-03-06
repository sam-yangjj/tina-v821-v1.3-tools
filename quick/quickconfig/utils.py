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


class DiffSummary:
    _instance = None  # Class variable to store the single instance

    def __new__(cls, *args, **kwargs):
        """
        Override the __new__ method to ensure only one instance of the class is created.
        """
        if not cls._instance:
            cls._instance = super(DiffSummary, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        """
        Initialize the DiffSummary instance.
        This method will only be called once due to the singleton pattern.
        """
        if not hasattr(self, 'initialized'):  # Check to ensure initialization happens only once
            self.diff_summary = '{}/.quick_config.diff'.format(os.getcwd())
            if os.path.exists(self.diff_summary):
                do_cmd('rm {}'.format(self.diff_summary))
            self.initialized = True  # Mark as initialized to prevent re-initialization

    def record_diff(self, target):
        """
        Record the differences between a target file and its backup.
        Appends the diff output to a global 'diff_summary' file.
        Then removes the backup file.
        """
        file_name = target + '.backup'
        do_cmd('echo "diff {}" >> {}'.format(target, self.diff_summary))
        do_cmd('diff {} {} >> {}'.format(file_name, target, self.diff_summary))
        do_cmd('rm {}'.format(file_name))

    def dump_diff(self):
        if os.path.exists(self.diff_summary):
            print('================================== dump modify diff ==================================')
            with open(self.diff_summary, 'r') as f:
                for line in f:
                    print(line[:-1])
            print('==================================   dump   end   ==================================')
            do_cmd('rm {}'.format(self.diff_summary))


def load_buildconfig(filepath):
    """
    Load environment variables from a file.
    Each line should be in the format: export KEY=VALUE
    Returns a dictionary of key-value pairs.
    """
    configs = {}
    # Compile regex to match lines like: export KEY=VALUE
    pattern = re.compile(r'^export ([^\s]+)=(.*)$')
    with open(filepath, "r") as f:
        for line in f:
            match = pattern.search(line)
            if not match:
                continue  # Skip lines that don't match the pattern
            key = match.group(1)  # Extract the variable name
            val = match.group(2)  # Extract the variable value
            configs[key] = val
    return configs


def do_cmd(cmd, env=None):
    """
    Execute a shell command without capturing output.
    If 'env' is provided, it will be used as the environment variables.
    Returns the command's exit code.
    """
    if env:
        s = subprocess.Popen(cmd, env=env, shell=True)
    else:
        s = subprocess.Popen(cmd, shell=True)
    return_code = s.wait()
    return return_code


def do_cmd_with_output(cmd, env=None):
    """
    Execute a shell command and capture its stdout output.
    If 'env' is provided, it will be used as the environment variables.
    Returns a tuple of (exit code, decoded stdout string).
    """
    if env:
        s = subprocess.Popen(cmd, env=env, shell=True, stdout=subprocess.PIPE)
    else:
        s = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    output = s.communicate()[0]  # Read command output
    return_code = s.returncode
    return return_code, output.decode()


def backup_file(target):
    """
    Create a backup of a file by copying it to target.backup.
    Does nothing if the backup already exists.
    """
    file_name = target + '.backup'
    if not os.path.exists(file_name):
        do_cmd('cp {} {}'.format(target, file_name))


def restore_file(target):
    """
    Restore a file from its backup.
    Moves target.backup back to the original target filename.
    """
    file_name = target + '.backup'
    do_cmd('mv {} {}'.format(file_name, target))


def leading_whitespace_count(s):
    """
    Count the number of leading whitespace characters in a string.
    Tabs are expanded to spaces before counting.
    """
    expanded = s.expandtabs()
    return len(expanded) - len(expanded.lstrip())


def check_sdk_diskclean_status(lichee_out_path, config_name):
    """
    Checks the specified output directory (`lichee_out_path`) for the presence of certain files and directories
    that should not exist when running a new configuration. If any of these files or directories are found,
    the function will print an error message and suggest running 'make distclean' to clean the environment before
    executing the configuration.

    Args:
        lichee_out_path (str): The path to the output directory where SDK build files are located.
        config_name (str): The name of the configuration being executed.

    Returns:
        bool: Returns `True` if no conflicting files are found, otherwise `False`.
    """

    # List of files and directories to check for existence in the output path
    check_list = [
        "staging_dir",  # Temporary build directory
        "build_dir",  # Build output directory
        "dist",  # Distribution folder
        "boot.img",  # Boot image file
    ]

    # Iterate over each item in the check_list to see if it exists in the output path
    for check_node in check_list:
        # Construct the full path of the file/directory to check
        check_path = lichee_out_path + "/{}".format(check_node)

        # If the file/directory exists, print an error and suggest cleaning the environment
        if os.path.exists(check_path):
            print("\n\n\033[31m###################### ERROR ##########################\033[0m\n\n")
            print("\033[31mERROR: Check file exists in {} \033[0m".format(check_path))
            print(
                "\033[31mYou must run 'make distclean' to clean the environment before executing this '{}' config\033[0m".format(
                    config_name))
            print("\033[31motherwise you will encounter compilation errors.\033[0m")
            print("\033[31mPlease run 'make distclean' before executing 'quick_config'.\033[0m\n\n")
            return False  # Return False if any conflicting file or directory is found

    # Return True if no conflicting files or directories are found
    return True


def parse_var(vars, var):
    """
    Parses the input string `var` and replaces variables enclosed in ${key}
    with the corresponding values from the `vars` dictionary. The process will
    iterate a maximum of 10 times to prevent infinite loops, and if unresolved
    variables remain, an error message is printed.

    Args:
        vars (dict): A dictionary where the key is the variable name and the value
                     is the replacement string.
        var (str): The string containing variables to be replaced.

    Returns:
        str: The string `var` with all variables replaced by their corresponding values
             from the `vars` dictionary. If some variables could not be replaced,
             they will remain in the string.

    """
    max_ref = 10
    while max_ref > 0:
        for k, v in vars.items():
            # Replace ${key} with the corresponding value in the input string
            var = var.replace('${%s}' % (k), v)

        # If no more '$' symbols are in the string, exit the loop
        if '$' not in var:
            break

        # Decrement the reference count to prevent infinite loops
        max_ref = max_ref - 1

    # If there are still unresolved variables, print an error message
    if '$' in var:
        print('Unknown \"{}\" var.'.format(var))

    return var
