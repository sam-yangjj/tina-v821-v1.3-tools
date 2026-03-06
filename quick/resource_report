#!/usr/bin/env python3

import os, sys
import argparse
import re
import subprocess
import string

parser = argparse.ArgumentParser()
parser.add_argument("buildconfig", default="../.buildconfig",
                    help="the buildconfig file")
parser.add_argument("-o", "--output", help="configuration info output file path")
parser.add_argument("-i", "--input", help="configuration info input file path")
parser.add_argument("-a", "--allpins", action='store_true', help="dont't skip disabled pin info")
parser.add_argument('-v', '--verbose', action='store_true', help='verbose output')

args = parser.parse_args()
work_mode = None
verbose = False
skip_unused = True

if not os.path.exists(args.buildconfig):
    print("%s not exists" % args.buildconfig)
    sys.exit(1)
if args.input and not os.path.exists(args.input):
    print("%s not exists" % args.input)
    sys.exit(1)

if args.input and os.path.exists(args.input):
    work_mode = 'input'
elif args.output:
    work_mode = 'output'
if args.verbose:
    verbose = True
if args.allpins:
    skip_unused = False

configs = {}
syconfig_path = None
kernel_dts_path = None
top_dir = None
kerenl_ver = None
board_config_dir = None
kernel_src_path = None
bsp_path = None

rtos_project = None
rtos_device = None
rtos_plat = None
rtos_sysconf = None

kernel_dts_include_path = []


def verbose_print(arg):
    if verbose:
        print(arg)


def do_cmd(cmd, env=None):
    if env:
        s = subprocess.Popen(cmd, env=env, shell=True)
    else:
        s = subprocess.Popen(cmd, shell=True)
    return_code = s.wait()
    return return_code


def do_cmd_with_output(cmd, env=None):
    if env:
        s = subprocess.Popen(cmd, env=env, shell=True, stdout=subprocess.PIPE)
    else:
        s = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    output = s.communicate()[0]
    return_code = s.returncode
    return return_code, output.decode()


def _load_config(filepath):
    pattern = re.compile(r'^export ([^\s]+)=(.*)$')
    with open(filepath, "r") as f:
        for line in f:
            match = pattern.search(line)
            if not match:
                continue
            key = match.group(1)
            val = match.group(2)
            configs[key] = val


def init_cfgval():
    global syconfig_path
    global kernel_dts_path
    global top_dir
    global kerenl_ver
    global board_config_dir
    global kernel_src_path
    global bsp_path
    global rtos_project, rtos_device, rtos_plat, rtos_sysconf
    global kernel_dts_include_path

    board_config_dir = configs['LICHEE_BOARD_CONFIG_DIR']
    linux_dev = configs['LICHEE_LINUX_DEV']
    kerenl_ver = configs['LICHEE_KERN_VER']

    if board_config_dir == None:
        print("LICHEE_BOARD_CONFIG_DIR not set in %s" % args.buildconfig)
        sys.exit(1)

    syconfig_path = board_config_dir + '/sys_config.fex'
    if not os.path.exists(syconfig_path):
        print("%s is not exists" % syconfig_path)
        sys.exit(1)

    kernel_src_path = configs['LICHEE_KERN_DIR']
    if not os.path.exists(kernel_src_path):
        print("%s is not exists" % kernel_src_path)
        sys.exit(1)

    bsp_path = configs['LICHEE_BSP_DIR']
    if not os.path.exists(bsp_path):
        print("%s is not exists" % bsp_path)

    kernel_dts_path = board_config_dir + '/{}/board.dts'.format(kerenl_ver)
    if not os.path.exists(kernel_dts_path):
        kernel_dts_path = board_config_dir + '/board.dts'
    if not os.path.exists(kernel_dts_path):
        print("%s is not exists" % kernel_dts_path)
        sys.exit(1)

    kernel_dts_include_path.append(bsp_path + '/configs/' + kerenl_ver)
    kernel_dts_include_path.append(bsp_path + '/include')

    top_dir = configs['LICHEE_TOP_DIR']
    if not os.path.exists(top_dir):
        print("%s is not exists" % top_dir)
        sys.exit(1)

    rtos_project = configs['LICHEE_RTOS_PROJECT_NAME']
    # scan rots dir
    # format:
    #       projec = v821_e907_perf2
    #       device = v821_e907
    #       plat   = perf2
    cmd = 'find {}/rtos/lichee/rtos/projects/ -maxdepth 2 -mindepth 2 -type d'.format(top_dir)
    ret, rtos_prjs = do_cmd_with_output(cmd)
    if ret == 0:
        for p in rtos_prjs.split():
            p = p.partition('{}/rtos/lichee/rtos/projects/'.format(top_dir))[2]
            if p.replace('/', '_') == rtos_project:
                rtos_device = p.split('/')[0]
                rtos_plat = p.split('/')[1]
    else:
        print("scan {}/rtos/lichee/rtos/projects/ fialed".format(top_dir))
        rtos_device = None
        rtos_plat = None

    if rtos_device == None:
        rtos_project = None
    rtos_sysconf = '{}/rtos/board/{}/{}/configs/sys_config.fex'.format(top_dir, rtos_device, rtos_plat)


def leading_whitespace_count(s):
    expanded = s.expandtabs()
    return len(expanded) - len(expanded.lstrip())


def rtos_sysconf_set(mainkey, subkey, val, create):
    global rtos_sysconf

    sysconf = parse_sysconfig(rtos_sysconf)
    # print(sysconf)
    if mainkey not in sysconf.keys():
        if not create:
            print('mainkey: {} not found at {}'.format(mainkey, rtos_sysconf))
            return
        # insert new mainkey
        print('Unsupport insert mainkey to sysconfig.fex')
        return
    else:
        for sub in sysconf[mainkey]:
            # [line, subkey, val]
            if subkey == sub[1]:
                if val != sub[2]:
                    cmd = 'sed -i "{}s/\\(.*=\\s*\\)\\([^\s]*\\)/\\1{}/" {}'.format(sub[0], val, rtos_sysconf)
                    do_cmd(cmd)
                return
        if not create:
            print('subkey: {} not found at mainkey {} [{}]'.format(subkey, mainkey, rtos_sysconf))
            return
        # insert new subkey
        print('Unsupport insert subkey to sysconfig.fex')
        return


def parse_sysconfig(syconfig):
    sysconf = {}
    num = 0
    mainkey = None
    val = None
    with open(syconfig, 'r') as f:
        for line in f:
            num = num + 1
            line = line.strip()
            if len(line) == 0:
                continue
            if line.startswith(';'):
                continue
            # print('{}: {}'.format(num, line))
            if line.startswith('['):
                # if mainkey:
                #     print(mainkey)
                #     for vv in sysconf[mainkey]:
                #         print('  {}'.format(vv))
                mainkey = line.replace('[', '').replace(']', '').strip()
                val = None
            elif '=' in line:
                line = line.replace('=', ' ', 1).split()
                if len(line) != 2:
                    continue
                val = [num, line[0], line[1]]
                # print(val)
            else:
                print('Unkonw: {}: {}'.format(num, line))
                continue

            if mainkey and val:
                if mainkey not in sysconf.keys():
                    sysconf[mainkey] = []
                sysconf[mainkey].append(val)

    # if mainkey:
    #     print(mainkey)
    #     for vv in sysconf[mainkey]:
    #         print('  {}'.format(vv))
    return sysconf


def get_dts_include(dts_file, include_file):
    global kernel_dts_include_path

    with open(dts_file, 'r') as f:
        file_name = None
        for line in f:
            line = line.strip()
            if not line.startswith('#include'):
                continue
            if '<' in line:  # include <xxxx/yyyy/zzz.dtsi>
                line = line.replace('>', '')
                file_name = line.split('<')[1].strip()
            elif '"' in line:  # include "xxxx/yyyy/zzz.dtsi"
                file_name = line.split('"')[1].strip()

            if not file_name.endswith('.dtsi'):
                continue

            for p in kernel_dts_include_path:
                full_path = '{}/{}'.format(p, file_name)
                if os.path.exists(full_path):
                    if full_path not in include_file:
                        include_file.append(full_path)
                        get_dts_include(full_path, include_file)
                    break


def parse_dts(dts_file):
    with open(dts_file, 'r') as f:
        lines = f.readlines()

    idx = 0
    in_comment = False
    in_property = False
    tree = {}
    node_line_list = []
    continue_prop_name = None

    # property_match1 = re.compile(r'^([\w:"-<>]+)\s*=?[ \t]*(.*);')
    # # prop type1: xxx = yyy; /* */
    property_type1 = re.compile(r'^([\w:"-<>]+)\s*=[ \t]*(.*);')
    # prop type2: xxx = x1, x2,
    #                  x3, x4;
    # property_type2_0 = re.compile(r'^([\w:"-<>]+)\s*=[ \t]*([^;]*)$')
    property_type2_0 = re.compile(r'^([\w:"-<>]+)\s*=[ \t]*([^;/]*)$')
    property_type2_1 = re.compile(r'^([\t\w:"-<> \]]+)\s*;')  # include space
    # prop type2: xxx = x1, x2, /* xxxx */
    property_type2_3 = re.compile(r'^([\w:"-<>]+)\s*=[ \t]*([^;/]*) */\*.*$')
    # prop type3: xxx;
    property_type3 = re.compile(r'^([\w:"-<>]+)\s*;')  # except space

    while idx < len(lines):
        line = lines[idx].strip()
        linenum = idx + 1
        space_cnt = leading_whitespace_count(lines[idx])

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
            # print('Warning: "{" and "}" are not supported on the same line %d, at %s' % (linenum, dts_file))
            idx = idx + 1
            continue

        # node start
        if '{' in line:
            # print("parse: [%d] %s" % (linenum, line))
            node_name = line.split('{')[0].strip()
            if node_name.startswith('&'):
                # &xxxx {
                node_name = node_name[1:]
            elif ':' in node_name:
                # xxxx: yyyy {
                node_name = node_name.split(':')[0].strip()
            tree[linenum] = {}
            tree[linenum]['name'] = node_name
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
                    print('BUG: [%d] %s nest in %s' % (linenum, prop_name, continue_prop_name))
                    sys.exit(1)

                if 'property' not in tree[node_line].keys():
                    tree[node_line]['property'] = {}
                tree[node_line]['property'][prop_name] = {}
                tree[node_line]['property'][prop_name]['line'] = []
                tree[node_line]['property'][prop_name]['line'].append(linenum)
                tree[node_line]['property'][prop_name]['val'] = prop_val.replace('\\', '')

                continue_prop_name = prop_name
                in_property = True
            elif match2_1 and in_property:
                # across lines property end
                # print('[%d] cross end %s' % (linenum, line))

                prop_name = continue_prop_name
                prop_val = tree[node_line]['property'][prop_name]['val'] + match2_1.group(1).strip()

                tree[node_line]['property'][prop_name]['line'].append(linenum)
                tree[node_line]['property'][prop_name]['val'] = prop_val.replace('\\', '')

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
            elif in_property:
                # print('[%d] cross prop %s: %s' % (linenum, continue_prop_name, line))
                prop_name = continue_prop_name
                prop_val = tree[node_line]['property'][prop_name]['val'] + line.strip().replace('\\', '')

                tree[node_line]['property'][prop_name]['val'] = prop_val
                # tree[node_line]['property'][prop_name]['line'].append(linenum)
            else:
                print('[%d] Unknow dts property "%s" skip..' % (linenum, line))
                idx = idx + 1
                continue

            # print('[%d] %s: proerty %s' % (linenum, node_name, line))
        idx = idx + 1

    return tree


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


def dts_property_query(option, dts_file, node_name, prop_name=None, prop_val=None):
    tree = parse_dts(dts_file)
    '''format
        node_name: tree[node_line]['name']
        startline: tree[node_line]['start']
        endline: tree[node_line]['end']
        property: tree[node_line]['property']
            lines: tree[node_line]['property'][prop_name]['line']
            val: tree[node_line]['property'][prop_name]['val']
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
        cmd = 'sed -i \'{} i\\{}\' {}'.format(insert_line, newline, dts_file)
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
            cmd = 'sed -i \'{} s|\\(\\s*\\){}.*|\\1{} = {};|\' {}'.format(start, prop_name, \
                                                                          prop_name, prop_val, dts_file)
        else:
            cmd = 'sed -i \'{} s|\\(\\s*\\){}.*|\\1{};|\' {}'.format(start, prop_name, \
                                                                     prop_name, dts_file)
        do_cmd(cmd)
        start = start + 1

    if option == 'setprop' or option == 'delprop':
        # del old prop
        if end >= start:
            # sed -i '5,9d' file
            if end == start:
                cmd = 'sed -i \'{}d\' {}'.format(start, dts_file)
            else:
                cmd = 'sed -i \'{},{}d\' {}'.format(start, end, dts_file)
            do_cmd(cmd)

    return 0


def dts_node_query(option, dts_file, parent_node, node_name):
    tree = parse_dts(dts_file)

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
            cmd = 'sed -i \'{}d\' {}'.format(start, dts_file)
        else:
            cmd = 'sed -i \'{},{}d\' {}'.format(start, end, dts_file)
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
            cmd = 'sed -i \'{} i\\{}\' {}'.format(pos, new_node, dts_file)
            do_cmd(cmd)
        else:
            new_node = "\n" + full_node_name + " {\n};\n"
            with open(dts_file, 'a') as f:
                f.write(new_node)

    return 0


def find_default_pinctrl(v):
    default_pin = -1
    for prop, val in v['property'].items():
        if prop != 'pinctrl-names':
            continue
        if not val['val']:  # e.g. pinctrl-names;
            continue

        pins = val['val'].split(',')
        # print(pins)
        for i in range(len(pins)):
            if pins[i].strip().endswith('default"'):
                default_pin = i
                break
            if pins[i].strip() == '"active"':
                default_pin = i
                break
    if 'pinctrl-0' in v['property'].keys() and default_pin == -1:
        print('\t!!!not fountd default pin from node: {}'.format(v['name']))
    return default_pin


def catch_gpio_info(dts_tree, all_pins, owner):
    pin_info = {}
    for v in dts_tree.values():
        pin_info.clear()
        is_en = False
        has_gpio = False
        n_name = v['name']
        if 'property' not in v.keys():
            continue
        if 'status' not in v['property']:
            continue

        if v['property']['status']['val'] == '"okay"':
            is_en = True

        if n_name in all_pins.keys():
            pin_info = all_pins[n_name]
        default_pin = find_default_pinctrl(v)

        # check gpio prop
        if 'pinctrl-names' not in v['property']:
            if v['name'] not in all_pins.keys():
                for prop, prov_v in v['property'].items():
                    # print('{} = {}'.format(prop, prov_v))
                    if prov_v['val'] and 'GPIO_ACTIVE_' in prov_v['val']:
                        # format:  xxx-gpio = <&xxx PX n GPIO_ACTIVE_yyy>
                        tmp_split = prov_v['val'].replace('<', '').replace('>', '').strip().split()
                        if 'gpios' not in pin_info.keys():
                            pin_info['gpios'] = []
                        if len(tmp_split) != 4:
                            print('Invalud gpio line: %s = %s\n', prop, prov_v)
                            continue
                        pin_name = tmp_split[1] + tmp_split[2]
                        tmp = [pin_name, prop]
                        pin_info['gpios'].append(tmp)
                        has_gpio = True

        if default_pin == -1 and 'idx' not in pin_info.keys() and not has_gpio:
            # print('skip {}...'.format(v))
            continue  # skip node

        # print('process {}...'.format(v))
        # update pin info
        if default_pin == -1:
            if 'idx' in pin_info.keys():
                default_pin = pin_info['idx']
                # print('\t get {} default pin idx from {}'.format(default_pin, n_name))
        else:
            # print('\t update {} default pin idx {}'.format(n_name, default_pin))
            pin_info['idx'] = default_pin

        # update node status
        pin_info['en'] = is_en

        if default_pin != -1:  # update pinctrl info
            new_pin_prop = 'pinctrl-{}'.format(default_pin)
            # update default pinctrl info
            if new_pin_prop in v['property'].keys():
                val = v['property'][new_pin_prop]
                pins = val['val'].replace('<', '').replace('>', '').split('&')
                # print(pins)
                for i in range(len(pins)):
                    if len(pins[i].strip()) == 0:
                        continue
                    # print('\t update {} pin = {}'.format(n_name, pins[i].strip()))
                    pin_info['pin'] = pins[i].strip()

        pin_info['owner'] = owner
        all_pins[n_name] = pin_info.copy()
    if verbose:
        for k, v in all_pins.items():
            print('  {} = {}'.format(k, v))
        print('')


def catch_gpio_cfg(dts_tree, pins_cfg, owner):
    pin_cfg = {}
    for v in dts_tree.values():
        if 'property' not in v.keys():
            continue
        if 'pins' in v['property'].keys() and 'function' in v['property'].keys():
            func = v['property']['function']['val']
            func = func.replace('"', '').strip()
            pins = v['property']['pins']['val']
            for pin in pins.replace(',', ' ').split():
                pin = pin.replace('"', '').strip()
                pin_cfg.clear()
                pin_cfg['func'] = func
                pin_cfg['pin'] = pin
                pin_cfg['pull'] = 'default'
                pin_cfg['drive'] = 'default'
                if 'bias-pull-down' in v['property']:
                    pin_cfg['pull'] = 0
                if 'bias-pull-up' in v['property']:
                    pin_cfg['pull'] = 1
                if 'allwinner,drive' in v['property'] and v['property']['allwinner,drive']['val']:
                    drive = v['property']['allwinner,drive']['val'].replace('<', '').replace('>', '').strip()
                    pin_cfg['drive'] = drive
                # print('----{} = {}'.format(v['name'], pin_cfg))
                if v['name'] not in pins_cfg.keys():
                    pins_cfg[v['name']] = []
                pin_cfg['owner'] = owner
                pins_cfg[v['name']].append(pin_cfg.copy())
        elif 'allwinner,pins' in v['property'].keys() and 'allwinner,function' in v['property'].keys():
            pass

    if verbose:
        for k, v in pins_cfg.items():
            print('{} = {}'.format(k, v[0]['func']))
            for pin in v:
                print('\t{}'.format(pin['pin']))
        print('')


def catch_sysconf_cfg(sysconf_path, all_pins, owner):
    sysconf = parse_sysconfig(sysconf_path)
    for mainkey, items in sysconf.items():
        # items = [[line_num, subkey, value], ...]

        # check used == 0 ?
        used_keyname = os.path.basename(mainkey) + '_used'
        item_used = 1  # default is used
        for item in items:
            if 'used' == item[1] and item[2] == '0':
                item_used = 0
            if used_keyname == item[1] and item[2] == '0':
                item_used = 0

        if skip_unused and item_used == 0:
            continue

        for item in items:
            subkey = item[1]
            val = item[2]
            # gpio format: port:pin<func_id><pull up/down><drive><output>
            # pins_info[0] -> port
            # pins_info[1] -> pin number
            # pins_info[2] -> func_id
            # pins_info[3] -> pull
            # pins_info[4] -> drive
            # pins_info[5] -> output
            pins_info = val.replace(':', ' ').replace('<', ' ').replace('>', ' ').split()
            if not val.startswith('port:'):
                continue
            if len(pins_info) != 6:
                continue

            if mainkey not in all_pins.keys():
                all_pins[mainkey] = []
            tmp = {}
            tmp['name'] = subkey
            tmp['pin'] = pins_info[1]
            tmp['func_id'] = pins_info[2]
            tmp['pull'] = pins_info[3]
            tmp['drive'] = pins_info[4]
            tmp['output'] = pins_info[5]
            tmp['en'] = item_used
            all_pins[mainkey].append(tmp.copy())


def update_gpio_info(all_pins, pins_cfg):
    need_del = []

    for k, v in all_pins.items():
        if skip_unused and not v['en']:
            need_del.append(k)
            continue
        if 'pin' not in v.keys() and 'gpios' not in v.keys():
            if v['en']:
                print('Warning: not fount pinctrl/gpio in dts node {}, continue...'.format(k))
            continue
        if 'pin' in v.keys():
            pin_cfg_name = v['pin']
            if pin_cfg_name not in pins_cfg.keys():
                print('Error: not fount pin {} in dts'.format(pin_cfg_name))
                break
            pin_cfg = pins_cfg[pin_cfg_name]
            v['pins'] = []
            for pin in pin_cfg:
                v['pins'].append(pin)
    for k in need_del:
        del all_pins[k]


def genera_gpio_pins(linux_pins, rtos_pins):
    # format: [pin] = { name , func, pull, drive, owner, node, func_id(opt) }
    all_pins = {}
    tmp = {}

    for k, v in linux_pins.items():
        tmp.clear()
        tmp['node'] = k
        tmp['owner'] = v['owner']
        tmp['pull'] = None
        tmp['drive'] = None
        tmp['func_id'] = None
        tmp['en'] = v['en']
        if 'pins' in v.keys():
            for pin in v['pins']:
                pin_port = pin['pin'][:2]
                pin_num = int(pin['pin'][2:])

                tmp['name'] = v['pin']
                tmp['func'] = pin['func']
                if 'pull' in pin.keys():
                    tmp['pull'] = str(pin['pull'])
                if 'drive' in pin.keys():
                    tmp['drive'] = str(pin['drive'])
                if 'func_id' in pin.keys():
                    tmp['func_id'] = pin['func_id']

                if '{}{}'.format(pin_port, pin_num) not in all_pins.keys():
                    all_pins['{}{}'.format(pin_port, pin_num)] = []
                all_pins['{}{}'.format(pin_port, pin_num)].append(tmp.copy())

        if 'gpios' in v.keys():
            for gpio in v['gpios']:
                # gpios = [['PD12', 'sensor0_reset'], ...]
                pin_port = gpio[0][:2]
                pin_num = int(gpio[0][2:])
                tmp['name'] = gpio[1]
                tmp['func'] = 'GPIO'
                if '{}{}'.format(pin_port, pin_num) not in all_pins.keys():
                    all_pins['{}{}'.format(pin_port, pin_num)] = []
                all_pins['{}{}'.format(pin_port, pin_num)].append(tmp.copy())

    for k, v in rtos_pins.items():
        if verbose:
            print(k)
            for vv in v:
                print('    {}'.format(vv))

        tmp.clear()
        tmp['node'] = k
        tmp['owner'] = 'RTOS'

        for vv in v:
            pin_port = vv['pin'][:2]
            pin_num = int(vv['pin'][2:])

            tmp['en'] = vv['en']
            tmp['name'] = vv['name']
            tmp['pull'] = str(vv['pull'])
            tmp['drive'] = str(vv['drive'])
            tmp['func_id'] = vv['func_id']
            tmp['func'] = vv['func_id']
            if '{}{}'.format(pin_port, pin_num) not in all_pins.keys():
                all_pins['{}{}'.format(pin_port, pin_num)] = []
            all_pins['{}{}'.format(pin_port, pin_num)].append(tmp.copy())

    return all_pins


def genera_csv_file(file_path, all_pins):
    may_conflit = False

    with open(file_path, 'w') as f:
        # f.write('GPIO, Function, OS, node, name, Pull, Drive\n')
        f.write('GPIO, OS, Function, node, name, Pull, Drive, enable\n')
        for port in string.ascii_uppercase:
            for i in range(0, 32):
                pin = 'P{}{}'.format(port, i)
                if pin not in all_pins.keys():
                    continue
                pin_os = None
                pin_name = None
                pin_node = None
                pin_pin = pin
                pin_func = None
                pin_pull = None
                pin_drive = None

                verbose_print(' ->> {}: {}'.format(pin, all_pins[pin]))

                if len(all_pins[pin]) > 1:
                    enable_cnt = 0
                    for pin_v in all_pins[pin]:
                        if pin_v['en']:
                            enable_cnt = enable_cnt + 1
                    if enable_cnt > 1:
                        may_conflit = True
                        print("\033[91m *** {} may conflit *** \033[0m".format(pin))
                    else:
                        may_conflit = False
                else:
                    may_conflit = False

                for pin_v in all_pins[pin]:
                    pin_os = pin_v['owner']
                    pin_name = pin_v['name']
                    pin_node = pin_v['node']
                    pin_func = str(pin_v['func'])
                    if not pin_v['pull']:
                        pin_pull = 'default'
                    else:
                        pin_pull = pin_v['pull']

                    if not pin_v['drive']:
                        pin_drive = 'default'
                    else:
                        pin_drive = pin_v['drive']
                    if may_conflit and pin_v['en']:
                        print("\033[91m     [{}] config at \'{}\' func is \'{}\'\033[0m".format(pin_os, pin_name,
                                                                                                pin_func))

                    if skip_unused and not pin_v['en']:
                        continue

                    f.write('{: <5}'.format(pin_pin))
                    f.write(', {: <5}'.format(pin_os))
                    f.write(', {: <10}'.format(pin_func))
                    f.write(', {: <5}'.format(pin_node))
                    f.write(', {: <5}'.format(pin_name))
                    f.write(', {: <5}'.format(pin_pull))
                    f.write(', {: <5}'.format(pin_drive))
                    f.write(', {: <5}'.format(pin_v['en']))
                    f.write('\n')
                f.write('\n')
                if may_conflit:
                    print('')

    return may_conflit


def parse_csv_file(file_path):
    all_pins = {}
    tmp = {}

    # file format: GPIO, Function, OS, node, name, Pull, Drive
    #  -> PC6: [{node, owner, pull, drive, func_id, name, func}, ...]
    line_num = 0
    with open(file_path, 'r') as f:
        for line in f:
            line_num = line_num + 1
            # skip GPIO, Function, OS, node, name, Pull, Drive
            if line_num == 1:
                continue
            items = line.replace(',', ' ').split()
            # print(items)
            if len(items) == 0:
                continue

            if len(items) != 8:
                print('Unknow line: {}'.format(line))
                continue

            pin_pin = items[0]
            pin_os = items[1]
            pin_func = items[2]
            pin_node = items[3]
            pin_name = items[4]
            pin_pull = items[5]
            pin_drive = items[6]
            pin_en = items[7]

            if pin_pin not in all_pins.keys():
                all_pins[pin_pin] = []
            tmp.clear()
            tmp['node'] = pin_node
            tmp['owner'] = pin_os
            tmp['pull'] = pin_pull
            tmp['drive'] = pin_drive
            tmp['name'] = pin_name
            tmp['en'] = pin_en
            if pin_func.isdigit():
                tmp['func_id'] = pin_func
                tmp['func'] = None
            else:
                tmp['func_id'] = None
                tmp['func'] = pin_func
            all_pins[pin_pin].append(tmp.copy())

            verbose_print(' <<- {}: {}'.format(pin_pin, all_pins[pin_pin]))

    return all_pins


def parse_linux_dts():
    global kernel_dts_path
    include_file = []
    linux_pins = {}
    pins_cfg = {}

    get_dts_include(kernel_dts_path, include_file)
    include_file.append(kernel_dts_path)
    for dts in include_file:
        print('parse dts = {}'.format(dts))
        tree = parse_dts(dts)
        catch_gpio_info(tree, linux_pins, 'Linux')
        catch_gpio_cfg(tree, pins_cfg, 'Linux')
    update_gpio_info(linux_pins, pins_cfg)

    return linux_pins


def parse_rtos_sysconf():
    global rtos_sysconf

    rtos_pins = {}
    # parse rtos sys_config.fex
    print('parse sys_config.fex = {}'.format(rtos_sysconf))
    catch_sysconf_cfg(rtos_sysconf, rtos_pins, 'RTOS')

    return rtos_pins


def dts_pin_is_change(prop_val, pin_info):
    dts_pins = prop_val.replace('"', '').replace(',', ' ').split()
    cfg_pins = pin_info['pins']
    is_change = False

    if len(dts_pins) != len(cfg_pins):
        return True

    for pin in dts_pins:
        if pin not in cfg_pins:
            is_change = True
            break
    return is_change


def update_linux_pins(all_pins):
    global kernel_dts_path

    include_file = []
    get_dts_include(kernel_dts_path, include_file)
    include_file.reverse()

    pin_group_cfg = {}
    # format: PC6: [{node, owner, pull, drive, func_id, name, func}, ...]
    # convert: 'PA0' : { xxxx, spi0 }, 'PA1' : { xxxx, spi0 } -> 'spi0' : { PA0, PA1, ...}
    for pin, val in all_pins.items():
        for pin_info in val:
            if pin_info['owner'] != 'Linux':
                continue
            if pin_info['name'] not in pin_group_cfg.keys():
                pin_group_cfg[pin_info['name']] = {}
                pin_group_cfg[pin_info['name']]['func'] = pin_info['func']
                pin_group_cfg[pin_info['name']]['drive'] = pin_info['drive']
                pin_group_cfg[pin_info['name']]['pull'] = pin_info['pull']
                pin_group_cfg[pin_info['name']]['node'] = pin_info['node']
                pin_group_cfg[pin_info['name']]['en'] = pin_info['en']
                pin_group_cfg[pin_info['name']]['func_id'] = None
                pin_group_cfg[pin_info['name']]['pins'] = []
            if pin not in pin_group_cfg[pin_info['name']]['pins']:
                pin_group_cfg[pin_info['name']]['pins'].append(pin)

    # format: PC6: [{node, owner, pull, drive, func_id, name, func}, ...]
    for group, val in pin_group_cfg.items():
        verbose_print('parse: {}: {}'.format(group, val))
        if val['func'] != 'GPIO':  # pinctrl format
            found = False
            found_at_dtsi = False
            pin_is_change = False
            pin_func_is_change = False
            pin_drive_is_change = False
            pin_pull_is_change = False

            prop_val = dts_property_query('getprop', kernel_dts_path, group, 'pins', None)
            if isinstance(prop_val, int) and prop_val == 0:
                prop_val = dts_property_query('getprop', kernel_dts_path, group, 'allwinner,pins', None)
                if isinstance(prop_val, int) and prop_val == 0:
                    # try to found at dtsi
                    for dts_file in include_file:
                        prop_val = dts_property_query('getprop', dts_file, group, 'pins', None)
                        if isinstance(prop_val, int) and prop_val == 0:
                            continue
                        found_at_dtsi = True
                        break
                    if not found_at_dtsi:
                        print(' pins: {} not found!'.format(group))
                        continue
            else:
                found = True
                dts_file = kernel_dts_path
            verbose_print('pins:  {} fount at {}'.format(group, dts_file))
            pin_is_change = dts_pin_is_change(prop_val, val)
            if pin_is_change:
                print(' pins: {} is change to {}'.format(prop_val, val['pins']))

            prop_val = dts_property_query('getprop', dts_file, group, 'function', None)
            if '\"{}\"'.format(val['func']) != prop_val:
                pin_func_is_change = True
                print(' function: {} is change to \"{}\"'.format(prop_val, val['func']))

            prop_val = dts_property_query('getprop', dts_file, group, 'allwinner,drive', None)
            if isinstance(prop_val, int) and prop_val == 0:
                prop_val = '<default>'
            if '<{}>'.format(val['drive']) != prop_val:
                pin_drive_is_change = True
            if pin_drive_is_change:
                print(' allwinner,drive: {} is change to {}'.format(prop_val, val['drive']))

            prop_val = dts_property_query('getprop', dts_file, group, 'bias-pull-up', None)
            if prop_val == None and val['pull'] != '1':
                pin_pull_is_change = True
            prop_val = dts_property_query('getprop', dts_file, group, 'bias-pull-down', None)
            if prop_val == None and val['pull'] != '0':
                pin_pull_is_change = True
            if pin_pull_is_change:
                print('  {} is change to {}'.format(prop_val, val['pull']))

            if not found and not found_at_dtsi:
                print('******Error******: {} not found at any dts file, skip...'.format(group))
                print('  {}'.format(kernel_dts_path))
                for dts in include_file:
                    print('  {}'.format(dts))
                continue
            if pin_is_change or pin_func_is_change or pin_drive_is_change or pin_pull_is_change:
                if found_at_dtsi and not found:
                    # don't touch dtsi, create new ref node
                    dts_node_query('add_tail', kernel_dts_path, '', '&' + group)

                if pin_is_change:
                    # set 'pins'
                    prop_val = '\"{}\"'.format(val['pins'][0])
                    for pin in val['pins'][1:]:
                        prop_val = prop_val + ', \"{}\"'.format(pin)
                    dts_property_query('setprop', kernel_dts_path, group, 'pins', prop_val)
                if pin_func_is_change:
                    # set 'function'
                    dts_property_query('setprop', kernel_dts_path, group, 'function', '\"{}\"'.format(val['func']))
                if pin_drive_is_change:
                    # set 'allwinner,drive'
                    if val['drive'] and val['drive'] != 'default':
                        dts_property_query('setprop', kernel_dts_path, group, 'allwinner,drive',
                                           '<{}>'.format(val['drive']))
                if pin_pull_is_change:
                    # set 'bias-pull-up' or 'bias-pull-down' or 'bias-disable'
                    if val['pull'] and val['pull'] != 'default':
                        if val['pull'] == '1':
                            dts_property_query('setprop', kernel_dts_path, group, 'bias-pull-up', None)
                        else:
                            dts_property_query('setprop', kernel_dts_path, group, 'bias-pull-down', None)
            else:
                print(' {} not any change skip...'.format(group))

            # check 'enable' property
            prop_val = dts_property_query('getprop', dts_file, val['node'], 'status', None)
            if isinstance(prop_val, int):
                if prop_val == 0:  # not found
                    if val['en'] == '1':
                        print(' {}: is change to \"okay\"'.format(val['node']))
                        dts_property_query('setprop', dts_file, val['node'], 'status', '\"okay\"')
            else:
                en_str = '\"disabled\"'
                if val['en'] == '1':
                    en_str = '\"okay\"'
                if prop_val != en_str:
                    print(' {}: status = {} is change to \"{}\"'.format(val['node'], prop_val, en_str))
                    dts_property_query('setprop', dts_file, val['node'], 'status', en_str)

        else:  # foramt:  xxxxx =  <&pio PX Y GPIO_ACTIVE_HIGH>
            found = False
            found_at_dtsi = False
            pin_is_change = False
            pin_list = None

            prop_val = dts_property_query('getprop', kernel_dts_path, val['node'], group, None)
            if isinstance(prop_val, int) and prop_val == 0:
                prop_val = dts_property_query('getprop', kernel_dts_path, val['node'], group, None)
                if isinstance(prop_val, int) and prop_val == 0:
                    # try to found at dtsi
                    for dts_file in include_file:
                        prop_val = dts_property_query('getprop', dts_file, val['node'], group, None)
                        if isinstance(prop_val, int) and prop_val == 0:
                            continue
                        found_at_dtsi = True
                        print('{}:{} fount at {}'.format(val['node'], group, dts_file))

                        break
            else:
                found = True

            if not found and not found_at_dtsi:
                print('******Error******: {} not found at any dts file, skip...'.format(group))
                print('  {}'.format(kernel_dts_path))
                for dts in include_file:
                    print('  {}'.format(dts))
                continue

            # format:  xxx-gpio = <&xxx PX n GPIO_ACTIVE_yyy>
            pin_list = prop_val.replace('<', '').replace('>', '').strip().split()
            if len(pin_list) != 4:
                print('Invalud gpio line: %s = %s\n', group, prop_val)
                continue

            if '{}{}'.format(pin_list[1], int(pin_list[2])) != val['pins'][0]:
                pin_is_change = True
                print(' GPIO: {} is change to {}'.format(prop_val, val['pins'][0]))

                if found_at_dtsi and not found:
                    # don't touch dtsi, create new ref node
                    dts_node_query('add_tail', kernel_dts_path, '', '&' + val['node'])

                # set 'pins'
                prop_val = '<{} {} {} {}>'.format(pin_list[0], val['pins'][0][:2], val['pins'][0][2:], pin_list[3])
                dts_property_query('setprop', kernel_dts_path, val['node'], group, prop_val)
            else:
                print(' {} not any change skip...'.format(group))

            # check 'enable' property
            prop_val = dts_property_query('getprop', kernel_dts_path, val['node'], "status", None)
            if isinstance(prop_val, int):
                if prop_val == 0:  # not found
                    if val['en'] == '1':
                        if found_at_dtsi and not found:
                            # don't touch dtsi, create new ref node
                            dts_node_query('add_tail', kernel_dts_path, '', '&' + val['node'])
                        dts_property_query('setprop', kernel_dts_path, val['node'], group, '<>')
            else:
                en_str = '\"disabled\"'
                if val['en'] == '1':
                    en_str = '\"okay\"'
                if prop_val != en_str:
                    print(' {}: status = {} is change to \"{}\"'.format(val['node'], prop_val, en_str))
                    if found_at_dtsi and not found:
                        # don't touch dtsi, create new ref node
                        dts_node_query('add_tail', kernel_dts_path, '', '&' + val['node'])
                    dts_property_query('setprop', kernel_dts_path, val['node'], group, '<>')

        verbose_print('\n')
    print('\n')


def update_rtos_pins(all_pins, rtos_pins):
    # format: PC6: [{node, owner, pull, drive, func_id, name, func}, ...]
    for pin, val in all_pins.items():
        for pin_info in val:
            if pin_info['owner'] != 'RTOS':
                continue
            verbose_print('parse: {} = {}'.format(pin, pin_info))
            mainkey = pin_info['node']
            subkey = pin_info['name']
            pull = pin_info['pull']
            drive = pin_info['drive']
            func_id = pin_info['func_id']
            pin_en = pin_info['en']

            if pin_en == '0':
                val = '\"none\"'.format(pin, func_id, pull, drive)
                rtos_sysconf_set(mainkey, subkey, val, True)

            if func_id == None:
                func_id = 'default'

            val = 'port:{}<{}><{}><{}><default>'.format(pin, func_id, pull, drive)
            if mainkey not in rtos_pins.keys():
                rtos_sysconf_set(mainkey, subkey, val, True)
            else:
                found = False
                for rtos_sub in rtos_pins[mainkey]:
                    if rtos_sub['name'] == subkey:
                        found = True
                        is_change = False

                        pin_port = rtos_sub['pin'][:2]
                        pin_num = int(rtos_sub['pin'][2:])
                        if pin != '{}{}'.format(pin_port, pin_num):
                            is_change = True
                        if func_id != rtos_sub['func_id']:
                            is_change = True
                        if pull != rtos_sub['pull']:
                            is_change = True
                        if drive != rtos_sub['drive']:
                            is_change = True

                        if is_change:
                            print('{} {} is change'.format(mainkey, subkey))
                            rtos_sysconf_set(mainkey, subkey, val, False)
                        break
                if found == False:
                    rtos_sysconf_set(mainkey, subkey, val, True)


if __name__ == "__main__":
    try:
        _load_config(args.buildconfig)
        init_cfgval()
        rtos_pins = parse_rtos_sysconf()
        if work_mode == 'output':
            linux_pins = parse_linux_dts()
            all_pins = genera_gpio_pins(linux_pins, rtos_pins)
            genera_csv_file(args.output, all_pins)
        elif work_mode == 'input':
            all_pins = parse_csv_file(args.input)
            update_linux_pins(all_pins)
            update_rtos_pins(all_pins, rtos_pins)
    except KeyboardInterrupt:
        print("\n")
        pass
