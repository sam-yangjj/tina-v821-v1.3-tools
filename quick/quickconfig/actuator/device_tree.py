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
"board.dts" : {
	"add_node" : [	# 要添加的节点
		{ "path" : "路径(可选), "name" : "节点名", "add_tail" : 是否在尾部插入 }
	],
	"del_node" : [	# 要删除的节点
		{ "path" : "路径(可选), "name" : "节点名" }
	],
	"set_property" : { # 要添加的属性
		"节点名" : {
			"属性名称" : "属性值"
		}
	},
	"del_property" : { # 要删除的属性
		"节点名" : {
			"属性名称" : "属性值"
		}
	},
	"bootargs" : {
		"loglevel" : 8,	# 修改
		"rootwait" : null,	# 删除
	}
}
'''

from quickconfig.utils import (
    backup_file, restore_file,
    DiffSummary, leading_whitespace_count,
    do_cmd
)


def dts_find_node_idx(dts_tree, node_name):
    for line, node in dts_tree.items():
        if node['name'] == node_name:
            return line
    return 0


def dts_find_node(dts_tree, node_name):
    node_names = []

    if node_name != '/':
        if node_name.startswith('/'):
            node_names.append('/')
            node_name = node_name[1:]

        if '/' in node_name:
            for tmp in node_name.split('/'):
                if tmp.strip() == '':
                    continue
                node_names.append(tmp.strip())
        else:
            node_names.append(node_name)
    else:
        node_names.append('/')

    linenum = dts_find_node_idx(dts_tree, node_names[0])
    if linenum == 0:
        return 0
    node = dts_tree[linenum]

    if len(node_names) > 1:
        for n in node_names[1:]:
            if 'subnode' not in node.keys():
                print('dts_find_node: %s is leaf node' % (node['name']))
                return 0

            find_nodeline = 0
            for line in node['subnode']:
                tmp_node = dts_tree[line]
                if n != tmp_node['name']:
                    continue
                find_nodeline = line
            if find_nodeline == 0:
                return 0
            linenum = find_nodeline
            node = dts_tree[linenum]

    return linenum


def extract_node_sign_device_name_address(node_sign):
    match = re.match(r'(.*)@([0-9a-fA-F]+)', node_sign)
    if match:
        device_name = match.group(1)
        address = match.group(2)
        return device_name, address
    else:
        return None, None


def extract_reg_start_address(reg_string):
    pattern = r'<\s*([^>]+?)\s*>'
    matches = re.findall(pattern, reg_string)
    results = []
    for match in matches:
        addresses = match.strip().split()
        results.extend(addresses)

    if len(results) == 4:
        # <0x0 0x42000000 0x0 0x10000>
        if results[0] == '0x0':
            return results[1].replace('0x', '')
        else:
            # <0x42000000 0x0 0x0 0x10000>
            return results[0].replace('0x', '')
    elif len(results) == 2:
        # <0x42000000 0x10000>
        return results[0].replace('0x', '')
    return None


class act_device_tree:
    def __init__(self, dts_file):
        self.dts_file = dts_file
        self.diff = DiffSummary()

    def record_diff(self):
        self.diff.record_diff(self.dts_file)

    def restore_file(self):
        restore_file(self.dts_file)

    def parse_dts(self):
        with open(self.dts_file, 'r') as f:
            lines = f.readlines()

        idx = 0
        in_comment = False
        in_property = False
        prefix = None
        tree = {}
        node_line_list = []
        continue_prop_name = None
        in_if_block = False  # To track if we're inside an #if block
        include_block = True  # To track whether to include or skip the block

        # dts prefix for control
        prefixes = ['/delete-property/', '/delete-node/']

        # property_match1 = re.compile(r'^([\w:"-<>]+)\s*=?[ \t]*(.*);')
        # # prop type1: xxx = yyy; /* */
        property_type1 = re.compile(r'^([\w:"-<>]+)\s*=[ \t]*(.*);')
        # prop type2: xxx = x1, x2,
        #                  x3, x4;
        property_type2_0 = re.compile(r'^([\w:"-<>]+)\s*=[ \t]*([^;]*)$')
        property_type2_1 = re.compile(r'^([\t\w:"-<> \]]+)\s*;')  # include space
        # prop type2: xxx = x1, x2, /* xxxx */
        property_type2_3 = re.compile(r'^([\w:"-<>]+)\s*=[ \t]*([^;/]*) */\*.*$')
        # prop type3: xxx;
        property_type3 = re.compile(r'^([\w:"-<>]+)\s*;')  # except space

        while idx < len(lines):
            line = lines[idx].strip()
            line_with_prefix = line
            linenum = idx + 1
            space_cnt = leading_whitespace_count(lines[idx])

            # /omit-if-no-ref/ no care
            if '/omit-if-no-ref/' in line:
                idx = idx + 1
                continue

            if line.startswith('//'):
                idx = idx + 1
                continue
            # comment: /* ... */
            if line.startswith('/*') and line.endswith('*/'):
                idx = idx + 1
                continue
            # comment: /* ...
            if line.startswith('/*') and not line.endswith('*/'):
                in_comment = True
                idx = idx + 1
                continue
            # comment: ... */
            if not line.startswith('/*') and line.endswith('*/') and in_comment == True:
                in_comment = False
                idx = idx + 1
                continue
            if in_comment:
                idx = idx + 1
                continue
            if '{' in line and '}' in line:
                print('ERROR: "{" and "}" are not supported on the same line %d' % (linenum))
                sys.exit(1)

            # remove prefix and record prefix for dts
            for prefix_to_remove in prefixes:
                if prefix_to_remove in line:
                    line = line.replace(prefix_to_remove, '').strip()
                    prefix = prefix_to_remove

            # Handling #if preprocessor directive
            if line.startswith('#if 0'):
                in_if_block = True
                # A simple mechanism to check if the block should be included
                # For now, assuming that any #if 0 is treated as False
                include_block = False
                idx = idx + 1
                continue
            elif line.startswith('#if 1'):
                in_if_block = True
                # A simple mechanism to check if the block should be included
                # For now, assuming that any #if 1 is treated as true
                include_block = True
                idx = idx + 1
                continue
            elif line.startswith('#if'):
                in_if_block = True
                # A simple mechanism to check if the block should be included
                # For now, assuming that any #if is treated as true
                include_block = True
                idx = idx + 1
                continue
            elif line.startswith('#else') and in_if_block:
                # Toggle the block's inclusion if else is encountered
                include_block = not include_block
                idx = idx + 1
                continue
            elif line.startswith('#endif') and in_if_block:
                # End the #if block
                in_if_block = False
                idx = idx + 1
                continue

            # Skip lines inside #if block if the condition is false
            if not include_block:
                idx = idx + 1
                continue

            # node start
            if '{' in line:
                # print("parse: [%d] %s" % (linenum, line))
                node_name_original = line.split('{')[0].strip()
                node_sign_address = None
                if node_name_original.startswith('&'):
                    # &xxxx {
                    node_name = node_name_original[1:]
                elif ':' in node_name_original:
                    # xxxx: yyyy {
                    node_name = node_name_original.split(':')[0].strip()
                    node_sign_address = node_name_original.split(':')[1].strip()
                else:
                    node_name = node_name_original

                tree[linenum] = {}
                tree[linenum]['name'] = node_name
                tree[linenum]['sign'] = node_sign_address
                tree[linenum]['start'] = linenum
                tree[linenum]['lspace'] = space_cnt
                tree[linenum]['subnode'] = []
                if len(node_line_list) > 0:
                    tree[node_line_list[-1]]['subnode'].append(linenum)
                node_line_list.append(linenum)
            # node end
            elif '}' in line:
                # print("parse: [%d] %s" % (linenum, line))
                node_line = node_line_list.pop()
                node_name = tree[node_line]['name']

                if not line.startswith('}'):
                    print('ERROR: unsupport %s, need }; in line %d' % (line, linenum))
                    sys.exit(1)

                tree[node_line]['end'] = linenum
                # print("node_name: <%s> start:%d end:%d\n" % (node_name, tree[node_line]['start'], tree[node_line]['end']))

                # print('node_name: %s [%d-%d]' % (node_name, tree[node_line]['start'], tree[node_line]['end']))
                # if 'property' in tree[node_line].keys():
                #     for k,v in tree[node_line]['property'].items():
                #         print('\t%s = %s;' %(k, v))
            # property range
            else:
                if len(node_line_list) == 0 or len(line) == 0:
                    idx = idx + 1
                    continue
                # print("%s" % (line))
                node_line = node_line_list[-1]
                node_name = tree[node_line]['name']
                # prop type3: xxx;
                match1 = property_type1.search(line)
                match2_0 = property_type2_0.search(line)
                match2_1 = property_type2_1.search(line)
                match2_3 = property_type2_3.search(line)
                match3 = property_type3.search(line)

                if match1:
                    # prop type1: xxx = yyy;
                    prop_name = match1.group(1)
                    prop_val = match1.group(2)
                    # print('[%d] %s = |%s|' % (linenum, prop_name, prop_val))
                    if 'property' not in tree[node_line].keys():
                        tree[node_line]['property'] = {}
                    tree[node_line]['property'][prop_name] = {}
                    tree[node_line]['property'][prop_name]['line'] = []
                    tree[node_line]['property'][prop_name]['line'].append(linenum)
                    tree[node_line]['property'][prop_name]['val'] = prop_val
                    if prefix and prefix in line_with_prefix:
                        tree[node_line]['property'][prop_name]['prefix'] = prefix
                    else:
                        tree[node_line]['property'][prop_name]['prefix'] = None
                elif match2_0 or match2_3:
                    if match2_3:
                        # print(line)
                        prop_name = match2_3.group(1).strip()
                        prop_val = match2_3.group(2).strip()
                    else:
                        prop_name = match2_0.group(1).strip()
                        prop_val = match2_0.group(2).strip()
                    # across lines property start
                    # suce as:
                    #   pins = "pin1", "pin2"
                    #           "pin3", "pin4";
                    # print('[%d] cross prop start %s' % (linenum, line))
                    if continue_prop_name != None:
                        print('BUG: [%d] %s nest in %s' % (linenum, match2_0.group(1), continue_prop_name))
                        sys.exit(1)

                    if 'property' not in tree[node_line].keys():
                        tree[node_line]['property'] = {}
                    tree[node_line]['property'][prop_name] = {}
                    tree[node_line]['property'][prop_name]['line'] = []
                    tree[node_line]['property'][prop_name]['line'].append(linenum)
                    tree[node_line]['property'][prop_name]['val'] = prop_val
                    if prefix and prefix in line_with_prefix:
                        tree[node_line]['property'][prop_name]['prefix'] = prefix
                    else:
                        tree[node_line]['property'][prop_name]['prefix'] = None

                    continue_prop_name = match2_0.group(1)
                    in_property = True
                elif match2_1 and in_property:
                    # across lines property end
                    # print('[%d] cross end %s' % (linenum, line))

                    prop_name = continue_prop_name
                    prop_val = tree[node_line]['property'][prop_name]['val'] + match2_1.group(1).strip()

                    tree[node_line]['property'][prop_name]['line'].append(linenum)
                    tree[node_line]['property'][prop_name]['val'] = prop_val
                    if prefix and prefix in line_with_prefix:
                        tree[node_line]['property'][prop_name]['prefix'] = prefix
                    else:
                        tree[node_line]['property'][prop_name]['prefix'] = None

                    continue_prop_name = None
                    in_property = False
                elif match3:
                    # prop type3: xxx;
                    # print('[%d] bool prop: %s' % (linenum, line))
                    prop_name = match3.group(1).strip()
                    prop_val = None

                    if 'property' not in tree[node_line].keys():
                        tree[node_line]['property'] = {}
                    tree[node_line]['property'][prop_name] = {}
                    tree[node_line]['property'][prop_name]['line'] = []
                    tree[node_line]['property'][prop_name]['line'].append(linenum)
                    tree[node_line]['property'][prop_name]['val'] = prop_val
                    if prefix and prefix in line_with_prefix:
                        tree[node_line]['property'][prop_name]['prefix'] = prefix
                    else:
                        tree[node_line]['property'][prop_name]['prefix'] = None
                elif in_property:
                    # print('[%d] cross prop %s: %s' % (linenum, continue_prop_name, line))
                    prop_name = continue_prop_name
                    prop_val = tree[node_line]['property'][prop_name]['val'] + line.strip()
                    tree[node_line]['property'][prop_name]['val'] = prop_val

                    if prefix and prefix in line_with_prefix:
                        tree[node_line]['property'][prop_name]['prefix'] = prefix
                    else:
                        tree[node_line]['property'][prop_name]['prefix'] = None
                    # tree[node_line]['property'][prop_name]['line'].append(linenum)
                else:
                    print('DTS Line: [%d] Parser Fail. Unknow Syntax "%s" for device tree. Skip it' % (linenum, line))

                # print('[%d] %s: proerty %s' % (linenum, node_name, line))
            idx = idx + 1
        return tree

    def dts_node_query(self, option, parent_node, node_name):
        tree = self.parse_dts()

        # print('dts_node_query: %s parent_node=%s node_name=%s' % (option, parent_node, node_name))
        '''format
            node_name: tree[node_line]['name']
            startline: tree[linenum]['start']
            endline: tree[linenum]['end']
            property: tree[linenum]['property']
                lines: tree[linenum]['property'][prop_name]['line']
                val: tree[linenum]['property'][prop_name]['val']

            option: "add" or 'add_tail' or "del"
        '''
        full_node_name = node_name
        if ':' in node_name:  # xxx: yyy -> node_name = xxxx
            node_name = node_name.split(':')[0].strip()
        elif '&' in node_name:  # &xxxx -> node_name = xxxx
            node_name = node_name[1:]

        if '/' in full_node_name:
            print('unsupport opratem multi node name %s' % full_node_name)

        if parent_node != '':
            if parent_node != '/':
                full_path = parent_node + '/' + node_name
            else:
                full_path = '/' + node_name
        else:
            full_path = node_name

        linenum = dts_find_node(tree, full_path)
        if linenum == 0:
            # print('can\'t find %s'% full_path)
            if option == 'del':
                return 0
        else:
            if option.startswith('add'):
                print('dts_node_query: node %s already exist' % (full_path))
                return 1

        if len(parent_node) > 0 and dts_find_node(tree, parent_node) == 0:
            print('parent node %s not exist, can\'t %s %s' % (parent_node, option, node_name))
            return 2

        if option == 'del':
            node = tree[linenum]

            start = node['start']
            end = node['end']
            # sed -i '5,9d' file
            if end == start:
                cmd = 'sed -i \'{}d\' {}'.format(start, self.dts_file)
            else:
                cmd = 'sed -i \'{},{}d\' {}'.format(start, end, self.dts_file)
            do_cmd(cmd)
        elif option.startswith('add'):
            if len(parent_node) > 0:
                parent = tree[dts_find_node(tree, parent_node)]
                pos = parent['end']

                # print('%s [%s - %s]' % (parent_node, parent['start'], parent['end']))
                if option == 'add' and len(parent['subnode']) > 0:
                    # print('change pos to %s [%s - %s]' % (parent['subnode'][0], tree[parent['subnode'][0]]['start'], parent['end']))
                    pos = tree[parent['subnode'][0]]['start']

                space = int(parent['lspace'] / 8) + 1
                new_node = "\\t" * space + full_node_name + " {\\n"
                new_node += "\\t" * space + "};"
                # sed -i 'lines i\New Line' file.txt
                cmd = 'sed -i \'{} i\\{}\' {}'.format(pos, new_node, self.dts_file)
                do_cmd(cmd)
            else:
                new_node = "\n" + full_node_name + " {\n};\n"
                with open(self.dts_file, 'a') as f:
                    f.write(new_node)

        return 0

    def dts_property_query(self, option, node_name, prop_name=None, prop_val=None, with_sign=False):
        tree = self.parse_dts()

        '''format
            node_name: tree[node_line]['name']
            startline: tree[node_line]['start']
            endline: tree[node_line]['end']
            property: tree[node_line]['property']
                lines: tree[node_line]['property'][prop_name]['line']
                val: tree[node_line]['property'][prop_name]['val']
                prefix: tree[node_line]['property'][prop_name]['prefix']
        '''
        # print('dts_property_query: %s node_name=%s %s=%s' % (option, node_name, prop_name, prop_val))
        linenum = dts_find_node(tree, node_name)
        if linenum == 0:
            return 0
        node = tree[linenum]

        if prop_name == None:
            print('BUG: prop_name=None, option=  %s' % (option))
            sys.exit(1)

        if option == 'getprop':
            if prop_name not in node['property'].keys():
                return 0
            return node['property'][prop_name]['val']

        if prop_val != None:
            prop_val = prop_val.replace('&', '\&')

        if 'property' not in node.keys() or prop_name not in node['property'].keys():
            if option != 'setprop':
                return 0
            # need to insert new property to node
            if len(node['subnode']) > 0:
                insert_line = node['subnode'][0]
            else:
                insert_line = node['end']
            space = int(tree[linenum]['lspace'] / 8) + 1
            if prop_val != None:
                newline = '{}{} = {};'.format("\t" * space, prop_name, prop_val)
                # print('inster %s = %s to node: %s' % (prop_name, prop_val, node_name))
            else:
                newline = '{}{};'.format("\t" * space, prop_name)
                # print('inster %s to node: %s' % (prop_name, node_name))
            cmd = 'sed -i \'{} i\\{}\' {}'.format(insert_line, newline, self.dts_file)
            do_cmd(cmd)
            return 0

        # insert new property
        start = node['property'][prop_name]['line'][0]
        if len(node['property'][prop_name]['line']) == 2:
            end = node['property'][prop_name]['line'][1]
        else:
            end = start

        if option == 'setprop':
            if prop_val != None:
                # sed -i 'lines s/\(\s*\)$prop_name.*/\1prop_name = prop_val;/ file'
                cmd = 'sed -i \'{} s|\\(\\s*\\){}.*|\\1{} = {};|\' {}'.format(start, prop_name, prop_name, prop_val,
                                                                              self.dts_file)
            else:
                cmd = 'sed -i \'{} s|\\(\\s*\\){}.*|\\1{};|\' {}'.format(start, prop_name, prop_name, self.dts_file)
            do_cmd(cmd)
            if with_sign and prop_name == 'reg':
                node_start = node['start']
                node_sign = node['sign']
                device_name, address = extract_node_sign_device_name_address(node_sign)
                reg_address = extract_reg_start_address(prop_val)
                cmd = 'sed -i \'{} s|\\(\\s*\\){}|\\1{}@{}|\' {}'.format(node_start, node_sign, device_name,
                                                                         reg_address,
                                                                         self.dts_file)
                do_cmd(cmd)

            start = start + 1

        if option == 'setprop' or option == 'delprop':
            # del old prop
            if end >= start:
                # sed -i '5,9d' file
                if end == start:
                    cmd = 'sed -i \'{}d\' {}'.format(start, self.dts_file)
                else:
                    cmd = 'sed -i \'{},{}d\' {}'.format(start, end, self.dts_file)
                do_cmd(cmd)

        if option == 'addprefix':
            # Add prefix to the property name
            if prop_val != node['property'][prop_name]['prefix']:
                new_prop_name = "{} {}".format(prop_val, prop_name)
                cmd = 'sed -i \'{} s|\\(\\s*\\){}|\\1{}|\' {}'.format(start, prop_name, new_prop_name, self.dts_file)
                do_cmd(cmd)

        if option == 'delprefix':
            # Remove prefix from the property name if it exists
            if prop_val == node['property'][prop_name]['prefix']:
                new_prop_name = prop_name
                prop_name = "{} {}".format(prop_val, prop_name)
                cmd = 'sed -i \'{} s|\\(\\s*\\){}|\\1{}|\' {}'.format(start, prop_name, new_prop_name, self.dts_file)
                do_cmd(cmd)

        return 0

    def parse_dts_bootargs(self, items):
        bootargs_val = self.dts_property_query('getprop', 'chosen', 'bootargs', None)
        if isinstance(bootargs_val, int):
            print('board.dts -> bootargs: not exists, skip...')
            return 0  # node not exists

        if not isinstance(bootargs_val, str):
            print('board.dts -> bootargs: invalid format, need str')
            return -1

        bootargs_list = bootargs_val[1:-1].split()
        for k1, v1 in items.items():
            for i in range(len(bootargs_list) - 1, -1, -1):
                v2 = bootargs_list[i]
                if v2.startswith(k1 + '='):
                    if v1 == None:  # del item
                        del bootargs_list[i]
                    else:
                        bootargs_list[i] = '{}={}'.format(k1, v1)
                    items[k1] = None
        for k1, v1 in items.items():
            if v1 != None:
                bootargs_list.append('{}={}'.format(k1, v1))
        bootargs_val = '"'
        for i in range(len(bootargs_list) - 1):
            v2 = bootargs_list[i]
            bootargs_val = bootargs_val + v2 + ' '
        bootargs_val = bootargs_val + bootargs_list[-1] + '"'
        bootargs_val = self.dts_property_query('setprop', 'chosen', 'bootargs', bootargs_val)
        return bootargs_val

    def parse_dts_cfg(self, val):
        backup_file(self.dts_file)
        if 'del_node' in val.keys():
            items = val['del_node']
            if not isinstance(items, list):
                print('board.dts -> del_node: invalid format, need list')
                self.record_diff()
                sys.exit(1)
            for node_info in items:
                if not isinstance(node_info, dict):
                    print('board.dts -> del_node: invalid item format, need { }')
                    self.record_diff()
                    sys.exit(1)
                if 'name' not in node_info.keys():
                    print('del_node item need \'name\' key')
                    continue
                node_name = node_info['name']
                parent_node = ''
                option = 'del'
                if 'path' in node_info.keys():
                    parent_node = node_info['path']
                    if len(parent_node) > 1 and parent_node[-1] == '/':
                        parent_node = parent_node[:-1]
                ret = self.dts_node_query(option, parent_node, node_name)
                if ret < 0:
                    print('parse: %s failed' % node_info)
                    self.record_diff()
                    sys.exit(1)
        if 'add_node' in val.keys():
            items = val['add_node']
            if not isinstance(items, list):
                print('board.dts -> add_node: invalid format, need list')
                self.record_diff()
                sys.exit(1)
            for node_info in items:
                if not isinstance(node_info, dict):
                    print('board.dts -> add_node: invalid item format, need { }')
                    self.record_diff()
                    sys.exit(1)
                if 'name' not in node_info.keys():
                    print('add_node item need \'name\' key')
                    continue
                node_name = node_info['name']
                parent_node = ''
                option = 'add'
                if 'path' in node_info.keys():
                    parent_node = node_info['path']
                    if len(parent_node) > 1 and parent_node[-1] == '/':
                        parent_node = parent_node[:-1]
                if 'add_tail' in node_info.keys():
                    if node_info['add_tail'] > 0:
                        option = 'add_tail'
                ret = self.dts_node_query(option, parent_node, node_name)
                if ret < 0:
                    print('parse: %s failed' % node_info)
                    self.record_diff()
                    sys.exit(1)
        if 'set_property' in val.keys():
            items = val['set_property']
            if not isinstance(items, dict):
                print('board.dts -> set_property: invalid format, need { }')
                self.record_diff()
                sys.exit(1)
            for node_name, prop_info in items.items():
                if not isinstance(prop_info, dict):
                    print('board.dts -> set_property: invalid item format, need { }')
                    self.record_diff()
                    sys.exit(1)
                for prop_name, prop_val in prop_info.items():
                    ret = self.dts_property_query('setprop', node_name, prop_name, prop_val)
                    if ret < 0:
                        print('parse %s: %s failed' % (prop_name, prop_val))
                        self.record_diff()
                        sys.exit(1)
        if 'set_property_with_address' in val.keys():
            items = val['set_property_with_address']
            if not isinstance(items, dict):
                print('board.dts -> set_property_with_address: invalid format, need { }')
                self.record_diff()
                sys.exit(1)
            for node_name, prop_info in items.items():
                if not isinstance(prop_info, dict):
                    print('board.dts -> set_property_with_address: invalid item format, need { }')
                    self.record_diff()
                    sys.exit(1)
                for prop_name, prop_val in prop_info.items():
                    ret = self.dts_property_query('setprop', node_name, prop_name, prop_val, with_sign=True)
                    if ret < 0:
                        print('parse %s: %s failed' % (prop_name, prop_val))
                        self.record_diff()
                        sys.exit(1)
        if 'del_property' in val.keys():
            items = val['del_property']
            if not isinstance(items, dict):
                print('board.dts -> del_property: invalid format, need { }')
                self.record_diff()
                sys.exit(1)
            for node_name, prop_info in items.items():
                if not isinstance(prop_info, dict):
                    print('board.dts -> del_property: invalid item format, need { }')
                    self.record_diff()
                    sys.exit(1)
                for prop_name, prop_val in prop_info.items():
                    ret = self.dts_property_query('delprop', node_name, prop_name, prop_val)
                    if ret < 0:
                        print('parse %s: %s failed' % (prop_name, prop_val))
                        self.record_diff()
                        sys.exit(1)
        if 'bootargs' in val.keys():
            items = val['bootargs']
            if not isinstance(items, dict):
                print('board.dts -> bootargs: invalid format, need { }')
                self.restore_file()
                sys.exit(1)
            ret = self.parse_dts_bootargs(items)
            if ret < 0:
                self.restore_file()
                sys.exit(1)
        if 'add_prefix' in val.keys():
            items = val['add_prefix']
            if not isinstance(items, dict):
                print('board.dts -> add_prefix: invalid format, need { }')
                self.record_diff()
                sys.exit(1)
            for node_name, prop_info in items.items():
                if not isinstance(prop_info, dict):
                    print('board.dts -> add_prefix: invalid item format, need { }')
                    self.record_diff()
                    sys.exit(1)
                for prop_name, prop_val in prop_info.items():
                    ret = self.dts_property_query('addprefix', node_name, prop_name, prop_val)
                    if ret < 0:
                        print('parse %s: %s failed' % (prop_name, prop_val))
                        self.record_diff()
                        sys.exit(1)
        if 'del_prefix' in val.keys():
            items = val['del_prefix']
            if not isinstance(items, dict):
                print('board.dts -> del_prefix: invalid format, need { }')
                self.record_diff()
                sys.exit(1)
            for node_name, prop_info in items.items():
                if not isinstance(prop_info, dict):
                    print('board.dts -> del_prefix: invalid item format, need { }')
                    self.record_diff()
                    sys.exit(1)
                for prop_name, prop_val in prop_info.items():
                    ret = self.dts_property_query('delprefix', node_name, prop_name, prop_val)
                    if ret < 0:
                        print('parse %s: %s failed' % (prop_name, prop_val))
                        self.record_diff()
                        sys.exit(1)
        self.record_diff()

    def update_bootargs_by_partitions(self, items_dict, lichee_flash):
        # update kernel board.dts chosen/bootargs: partitions var if exists
        backup_file(self.dts_file)
        partition = ""
        has_udisk = False
        for i in range(len(items_dict)):
            v = items_dict[i]
            if 'user_type' not in v.keys():
                continue
            if lichee_flash == 'nor':
                partition = partition + '{}@mtdblock{}:'.format(v['name']['val'], i)
            elif lichee_flash == 'nand':
                partition = partition + '{}@ubi0_{}:'.format(v['name']['val'], i)
            else:
                partition = partition + '{}@mmcblk0p{}:'.format(v['name']['val'], i)
            if v['name']['val'] == 'UDISK':
                has_udisk = True
        if not has_udisk:
            # add UDSIK partition
            if lichee_flash == 'nor':
                partition = partition + 'UDISK@mtdblock{}'.format(i + 1)
            elif lichee_flash == 'nand':
                partition = partition + 'UDISK@ubi0_{}:'.format(i + 1)
            else:
                partition = partition + 'UDISK@mmcblk0p{}'.format(i + 1)
        if partition[-1] == ':':
            partition = partition[:-1]

        ret = self.parse_dts_bootargs({"partitions": partition})
        if ret < 0:
            print("\033[91m partition changed, but board.dts partition update fialed\033[0m")
            restore_file(self.dts_file)

        # update root=
        matches = re.findall(r'([^@]+)@([^:]+)', partition)
        for name, medium in matches:
            if 'rootfs' == name.strip(':'):
                if 'ubi' in medium:
                    match = re.search(r'(\d+)', medium)
                    if match:
                        root_string = f'/dev/ubiblock{match.group(1)}'
                    else:
                        root_string = f'/dev/{medium}'
                else:
                    root_string = f'/dev/{medium}'
                ret = self.parse_dts_bootargs({"root": root_string})
                if ret < 0:
                    print("\033[91m partition changed, but board.dts root= update fialed\033[0m")
                    restore_file(self.dts_file)

        self.diff.record_diff(self.dts_file)

    def generate_device_tree_base(self, v1):
        # Parse the device tree from the DTS file
        tree = self.parse_dts()
        result = {}

        # Recursive function to process each node and its subnodes
        def process_node(node_data, parent_name=""):
            # Extract the name of the current node
            node_name = node_data.get('name')
            # Get the properties of the current node
            properties = node_data.get('property')
            node_properties = {}

            # Process the properties of the current node
            if properties is not None:
                for key, value in properties.items():
                    node_properties[key] = value.get('val', None)

            # Add the current node's properties to the result with its full path as the key
            result[node_name] = node_properties

            # Process the subnodes of the current node
            subnodes = node_data.get('subnode', [])
            for subnode_linenum in subnodes:
                # Get the subnode data from the tree
                subnode_data = tree[subnode_linenum]
                # Recursively process the subnode, passing the parent path
                process_node(subnode_data, node_name)

        # Process the nodes specified in "only_nodes"
        only_nodes = v1.get("nodes")
        if only_nodes is not None:
            for node in only_nodes:
                # Find the node in the tree
                linenum = dts_find_node(tree, node)
                if linenum == 0:
                    continue  # Skip if the node is not found
                # Get the data for the node
                node_data = tree[linenum]
                # Process the node and add its properties to the result
                process_node(node_data)

        # Process the nodes specified in "nodes_with_subnodes"
        nodes_with_subnodes = v1.get("nodes_with_subnodes")
        if nodes_with_subnodes is not None:
            for node in nodes_with_subnodes:
                # Find the node in the tree
                linenum = dts_find_node(tree, node)
                if linenum == 0:
                    continue  # Skip if the node is not found
                # Get the data for the node
                node_data = tree[linenum]
                # Process the node and add its properties to the result
                process_node(node_data)

        # Return the final result containing all the node properties in a flat structure
        return result
