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

def check_last_comma(str_list, before_index, json5_str, json5_file_path):
    i = before_index - 1
    while str_list[i].isspace() or not str_list[i]:
        i -= 1

    if str_list[i] == ',':
        line_num = json5_str.count('\n', 0, i) + 1
        col_num = i - json5_str.rfind('\n', 0, i)
        start_index = json5_str.rfind('\n', 0, i) + 1
        end_index = json5_str.find('\n', i)
        current_line = json5_str[start_index:end_index].strip() if start_index < end_index else ''
        print(f"\033[31mTrailing comma at file {json5_file_path} line {line_num}, column {col_num}\033[0m\n")
        print(f"\033[31m\t{current_line} <-- Trailing comma here\033[0m\n")
        print(f"\033[31mPlease Avoid add Trailing comma for quick_config \033[0m\n")
        return True

    return False


def check_trailing_comma(json5_file_path):
    with open(json5_file_path, 'r') as file:
        json_str = file.read()

    result_str = list(json_str)
    escaped = False
    normal = True
    sl_comment = False
    ml_comment = False
    quoted = False

    a_step_from_comment = False
    a_step_from_comment_away = False

    former_index = None
    has_trailing_comma = False

    for index, char in enumerate(json_str):
        if escaped:  # We have just met a '\'
            escaped = False
            continue

        if a_step_from_comment:  # We have just met a '/'
            if char != '/' and char != '*':
                a_step_from_comment = False
                normal = True
                continue

        if a_step_from_comment_away:  # We have just met a '*'
            if char != '/':
                a_step_from_comment_away = False

        if char == '"':
            if normal and not escaped:
                # We are now in a string
                quoted = True
                normal = False
            elif quoted and not escaped:
                # We are now out of a string
                quoted = False
                normal = True

        elif char == '\\':
            # '\' should not take effect in comment
            if normal or quoted:
                escaped = True

        elif char == '/':
            if a_step_from_comment:
                # Now we are in single line comment
                a_step_from_comment = False
                sl_comment = True
                normal = False
                former_index = index - 1
            elif a_step_from_comment_away:
                # Now we are out of comment
                a_step_from_comment_away = False
                normal = True
                ml_comment = False
                for i in range(former_index, index + 1):
                    result_str[i] = ""

            elif normal:
                # Now we are just one step away from comment
                a_step_from_comment = True
                normal = False

        elif char == '*':
            if a_step_from_comment:
                # We are now in multi-line comment
                a_step_from_comment = False
                ml_comment = True
                normal = False
                former_index = index - 1
            elif ml_comment:
                a_step_from_comment_away = True
        elif char == '\n':
            if sl_comment:
                sl_comment = False
                normal = True
                for i in range(former_index, index + 1):
                    result_str[i] = ""
        elif char == ']' or char == '}':
            if normal:
                if check_last_comma(result_str, index, json_str, json5_file_path):
                    has_trailing_comma = True
    return has_trailing_comma

