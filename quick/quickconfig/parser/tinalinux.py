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

import os, sys, copy
import json

sys.path.append(os.path.dirname(__file__) + '/../../pylib/json5-0.9.25')
import json5

from concurrent.futures import ThreadPoolExecutor, as_completed

from quickconfig.syntax import check_trailing_comma

from quickconfig.utils import (
    do_cmd_with_output, check_sdk_diskclean_status,
    parse_var, do_cmd, DiffSummary
)

from quickconfig.actuator import (
    act_sys_config, act_parse_bootpkg,
    act_device_tree, act_board_config,
    act_kernel_defconfig, act_common_defconfig,
    act_openwrt_defconfig, act_openwrt_makefile,
    act_env, act_sys_partition, act_rtos_defconfig,
    act_uboot_defconfig, act_boot0, act_nand_map,
    act_rtos_reserved_memory
)


class TinaLinuxEnvironmentParser:
    def __init__(self, configs):
        self.build_dir = None
        self.common_config_file = None
        self.config_file = None
        self.uboot_config_path = None
        self.uboot_brandy_ver = None
        self.uboot_efex_defconfig = None
        self.configs = configs
        self.board_config_dir = None
        self.linux_dev = None
        self.syconfig_path = None
        self.kernel_src_path = None
        self.kernel_dts_path = None
        self.uboot_dts_path = None
        self.kernel_defconf = None
        self.kernel_recovery_defconf = None
        self.top_dir = None
        self.kernel_ver = None
        self.search_list = []
        self.bsp_path = None
        self.kernel_cross_compile = None
        self.rtos_project = None
        self.rtos_device = None
        self.rtos_plat = None
        self.uboot_version = None
        self.uboot_defconfig = None
        self.uboot_defconfig_path = None
        self.uboot_nor_defconfig_path = None
        self.uboot_efex_defconfig_path = None
        self.lichee_chip = None
        self.builtin_var = {}

        self.search_list = None

        self.init_cfgval()

    def init_cfgval(self):
        # Initialize all configuration values
        self.board_config_dir = self.configs['LICHEE_BOARD_CONFIG_DIR'] + '/'
        self.linux_dev = self.configs['LICHEE_LINUX_DEV']
        self.kernel_ver = self.configs['LICHEE_KERN_VER']

        self.search_list = [
            # 1. ${LICHEE_BOARD_CONFIG_DIR}/${LICHEE_LINUX_DEV}/
            '{}/{}'.format(self.board_config_dir, self.linux_dev),
            # 2. ${LICHEE_BOARD_CONFIG_DIR}/${LICHEE_KERN_VER}/
            '{}/{}'.format(self.board_config_dir, self.kernel_ver),
            # 3. ${LICHEE_BOARD_CONFIG_DIR}/
            '{}'.format(self.board_config_dir),
            # 4. ${LICHEE_BOARD_CONFIG_DIR}/../default/
            '{}/../default'.format(self.board_config_dir),
        ]

        if self.board_config_dir is None:
            print("LICHEE_BOARD_CONFIG_DIR not set")
            sys.exit(1)

        self.syconfig_path = os.path.normpath(self.board_config_dir + '/sys_config.fex')
        if not os.path.exists(self.syconfig_path):
            print(f"{self.syconfig_path} is not exists")
            sys.exit(1)

        self.kernel_src_path = self.configs['LICHEE_KERN_DIR']
        if not os.path.exists(self.kernel_src_path):
            print(f"{self.kernel_src_path} is not exists")
            sys.exit(1)

        cmd = f'find {self.configs["LICHEE_TOOLCHAIN_PATH"]} -perm /a+x -a -regex \'.*-gcc\' | head -n 1'
        ret, self.kernel_cross_compile = do_cmd_with_output(cmd)
        if ret != 0:
            print(f'Execution of {cmd} failed, ret = {ret}')
            sys.exit(1)
        self.kernel_cross_compile = self.kernel_cross_compile[:-4]

        self.bsp_path = self.configs['LICHEE_BSP_DIR']
        if not os.path.exists(self.bsp_path):
            print(f"{self.bsp_path} is not exists")

        self.kernel_dts_path = os.path.normpath(self.board_config_dir + f'/{self.kernel_ver}/board.dts')
        if not os.path.exists(self.kernel_dts_path):
            self.kernel_dts_path = os.path.normpath(self.board_config_dir + '/board.dts')
        if not os.path.exists(self.kernel_dts_path):
            print(f"{self.kernel_dts_path} is not exists")
            sys.exit(1)

        self.kernel_defconf = self.configs['LICHEE_KERN_DEFCONF_ABSOLUTE']
        if not os.path.exists(self.kernel_defconf):
            print(f"{self.kernel_defconf} is not exists")
            sys.exit(1)

        self.kernel_recovery_defconf = self.configs.get('LICHEE_KERN_DEFCONF_RECOVERY_ABSOLUTE', None)
        if self.kernel_recovery_defconf or not os.path.exists(self.kernel_recovery_defconf):
            self.kernel_recovery_defconf = None

        self.top_dir = self.configs['LICHEE_TOP_DIR']
        if not os.path.exists(self.top_dir):
            print(f"{self.top_dir} is not exists")
            sys.exit(1)

        # U-Boot info
        self.lichee_chip = self.configs['LICHEE_CHIP']
        self.uboot_version = self.configs['LICHEE_BRANDY_UBOOT_VER']
        self.uboot_defconfig = self.configs['LICHEE_BRANDY_DEFCONF']
        self.uboot_efex_defconfig = f"{self.lichee_chip}_{self.configs['LICHEE_EFEX_BIN_NAME']}_defconfig"
        self.uboot_brandy_ver = self.configs['LICHEE_BRANDY_VER']

        self.uboot_config_path = f'{self.top_dir}/brandy/brandy-{self.uboot_brandy_ver}/u-boot-2018/configs/' \
            if self.uboot_version == "2018" else (f'{self.top_dir}/brandy/brandy-{self.uboot_brandy_ver}/u-boot-bsp'
                                                  f'/configs/')

        if os.path.exists(self.uboot_config_path):
            self.uboot_defconfig_path = os.path.normpath(self.uboot_config_path + self.uboot_defconfig)
            self.uboot_efex_defconfig_path = os.path.normpath(self.uboot_config_path + self.uboot_efex_defconfig)
            self.uboot_nor_defconfig_path = self.uboot_defconfig_path.replace("_defconfig", "_nor_defconfig")
        else:
            print(f"{self.uboot_config_path} is not exists, skip parse")

        if not os.path.exists(self.uboot_defconfig_path):
            print(f"{self.uboot_defconfig_path} is not exists, skip parse")
            self.uboot_defconfig_path = None

        if not os.path.exists(self.uboot_nor_defconfig_path):
            print(f"{self.uboot_nor_defconfig_path} is not exists, skip parse")
            self.uboot_nor_defconfig_path = None

        if not os.path.exists(self.uboot_efex_defconfig_path):
            print(f"{self.uboot_efex_defconfig_path} is not exists, skip parse")
            self.uboot_efex_defconfig_path = None

        self.uboot_dts_path = os.path.normpath(self.board_config_dir + f'uboot-{self.uboot_version}/uboot-board.dts')
        if not os.path.exists(self.uboot_dts_path):
            self.uboot_dts_path = os.path.normpath(self.board_config_dir + 'uboot-board.dts')
        if not os.path.exists(self.uboot_dts_path):
            print(f"{self.uboot_dts_path} is not exists")
            self.uboot_dts_path = None

        self.config_file = os.path.normpath(self.board_config_dir + 'quick_config.json')
        if not os.path.exists(self.config_file):
            self.config_file = os.path.normpath(self.board_config_dir + '/../default/quick_config.json')
        if not os.path.exists(self.config_file):
            print(f"{self.config_file} is not exists")
            sys.exit(1)

        self.common_config_file = os.path.normpath(self.board_config_dir + '/../default/quick_config.json')
        if not os.path.exists(self.common_config_file):
            self.common_config_file = None

        self.build_dir = self.configs.get('LICHEE_BUILD_DIR')
        if self.build_dir is None:
            print(f"LICHEE_BUILD_DIR not set")
            sys.exit(1)

        self.rtos_project = self.configs['LICHEE_RTOS_PROJECT_NAME']

        # Scan RTOS dir for project, device, and platform information
        cmd = f'find {self.top_dir}/rtos/lichee/rtos/projects/ -maxdepth 2 -mindepth 2 -type d'
        ret, rtos_prjs = do_cmd_with_output(cmd)
        if ret == 0:
            for p in rtos_prjs.split():
                p = p.partition(f'{self.top_dir}/rtos/lichee/rtos/projects/')[2]
                if p.replace('/', '_') == self.rtos_project:
                    self.rtos_device = p.split('/')[0]
                    self.rtos_plat = p.split('/')[1]
        else:
            print(f"Scan {self.top_dir}/rtos/lichee/rtos/projects/ failed")
            self.rtos_device = None
            self.rtos_plat = None

        if self.rtos_device is None:
            self.rtos_project = None

        self.builtin_var['rootfs'] = (
            f'{self.configs["LICHEE_TOP_DIR"]}/out/{self.configs["LICHEE_IC"]}/{self.configs["LICHEE_BOARD"]}/'
            f'{self.configs["LICHEE_LINUX_DEV"]}/build_dir/target/root-{self.configs["LICHEE_IC"]}'
            f'-{self.configs["LICHEE_BOARD"]}')
        self.builtin_var['configs'] = self.configs['LICHEE_BOARD_CONFIG_DIR']
        self.builtin_var['plat'] = (f'{self.configs["LICHEE_TOP_DIR"]}/openwrt/target/{self.configs["LICHEE_IC"]}/'
                                    f'{self.configs["LICHEE_IC"]}-{self.configs["LICHEE_BOARD"]}')
        self.builtin_var.update(self.configs)

    def get(self, attribute):
        return getattr(self, attribute, None)

    def get_buildconfigs(self, key):
        return self.configs.get(key, None)

    def set_buildconfigs(self, key, data):
        self.configs[key] = data


class TinaLinuxParser:
    def __init__(self, args, buildconfigs, print_banner=None):
        # args configs
        self.config_name = args.config
        self.args_force_config = args.force
        self.args_include_config = args.include
        self.args_gen_dts_base = args.gen_dts_base

        # info configs
        self.data = {}
        self.common_data = {}
        self.device_data = {}
        self.handlers = {}
        self.config_file = None
        self.is_trailing_comma_found = False
        self.need_sync_env = False

        self.print_banner = print_banner

        # internal data
        self.prepare_note = None
        self.check_distclean = None
        self.finish_note = None
        self.force_config = None

        # init Environment Info
        self.env = TinaLinuxEnvironmentParser(buildconfigs)

        diff = DiffSummary()

        self.init_quick_config_config()

        self.show_quick_config_configs_select()

        self.init_handle()

        self.parse_cfgfile()

        diff.dump_diff()

        self.show_finish_note_info(self.finish_note)

    def update_trailing_comma_status(self, status):
        if status:
            self.is_trailing_comma_found = True

    def init_quick_config_config(self):
        self.config_file = self.env.get("config_file")

        if not os.path.exists(self.config_file):
            print('{} is not exist'.format(self.config_file))
            sys.exit(0)

        if os.path.exists(self.env.get("common_config_file")):
            self.update_trailing_comma_status(check_trailing_comma(self.env.get("common_config_file")))
            with open(self.env.get("common_config_file"), "r") as json_file:
                self.common_data = json5.load(json_file)

        self.update_trailing_comma_status(check_trailing_comma(self.config_file))
        with open(self.config_file, "r") as json_file:
            self.device_data = json5.load(json_file)

        # if use_common_conifg is true, then we include connon_config
        if self.device_data.get("use_common_conifg", False):
            self.device_data.pop("use_common_conifg")
            # Add common_data to data list
            self.data.update(self.common_data)

        import_json_file_list = self.device_data.get("quick_config_include", [])
        if len(import_json_file_list) != 0:
            self.device_data.pop("quick_config_include")

        if self.args_include_config != None and len(self.args_include_config) != 0:
            import_json_file_list.append(self.args_include_config)

        for json_file in import_json_file_list:
            json_file_path = self.env.get("board_config_dir") + "/../default/quick_config/" + json_file
            if os.path.exists(json_file_path):
                self.update_trailing_comma_status(check_trailing_comma(json_file_path))
                with open(json_file_path, "r") as json_data:
                    include_data = json5.load(json_data)
                    self.data.update(include_data)
            else:
                print(f"Cannot find {json_file_path} file, skip load.")

        self.data.update(self.device_data)

        if self.is_trailing_comma_found:
            print("Please fix Trailing comma in your quick_config")
            sys.exit(1)

    def show_quick_config_configs_select(self):
        if not self.config_name or len(self.config_name) == 0:

            if self.print_banner:
                self.print_banner()

            print("Available Quick Config Name:")
            i = 0
            max_key_length = max(len(k) for k in self.data.keys())

            # Collect all configurations and categorize by tags
            # Default category and internal category
            categories = {}
            default_items = []
            internal_items = []

            for k in self.data.keys():
                if 'internal' in self.data[k].keys():
                    internal_items.append(k)
                else:
                    # Check if tag exists
                    tag = self.data[k].get('tag', 'others').upper()
                    if tag not in categories:
                        categories[tag] = []
                    categories[tag].append(k)

            # First show default category configurations (no explicit tag)
            if 'others' in categories:
                for k in categories['others']:
                    desc = ""
                    if 'desc' in self.data[k].keys():
                        desc = self.data[k]['desc']
                    print("{: 5d} {: <{width}} : {: <}".format(i, k, desc.capitalize(), width=max_key_length))
                    i = i + 1
                del categories['others']  # Remove default category to avoid duplicate display

            # Show other tag categories in alphabetical order
            sorted_tags = sorted(categories.keys())
            for tag in sorted_tags:
                print(f"\n[{tag.upper()}]")
                for k in categories[tag]:
                    desc = ""
                    if 'desc' in self.data[k].keys():
                        desc = self.data[k]['desc']
                    print("{: 5d} {: <{width}} : {: <}".format(i, k, desc.capitalize(), width=max_key_length))
                    i = i + 1

            # Show internal category (gray color)
            if internal_items:
                print("\n\033[90m[INTERNAL CONFIGS]\033[0m")
                for k in internal_items:
                    desc = ""
                    if 'desc' in self.data[k].keys():
                        desc = self.data[k]['desc']
                    print("\033[90m{: 5d} {: <{width}} : {: <}\033[0m".format(i, k, desc.capitalize(),
                                                                              width=max_key_length))
                    i = i + 1

            self.config_name = input('Which would you like? ')

        if self.config_name.isdigit():
            config_list = {}
            i = 0

            categories = {}
            default_items = []
            internal_items = []

            for k in self.data.keys():
                if 'internal' in self.data[k].keys():
                    internal_items.append(k)
                else:
                    tag = self.data[k].get('tag', 'others').upper()
                    if tag not in categories:
                        categories[tag] = []
                    categories[tag].append(k)

            if 'others' in categories:
                for k in categories['others']:
                    config_list[i] = k
                    i = i + 1
                del categories['others']

            sorted_tags = sorted(categories.keys())
            for tag in sorted_tags:
                for k in categories[tag]:
                    config_list[i] = k
                    i = i + 1

            for k in internal_items:
                config_list[i] = k
                i = i + 1

            if int(self.config_name) >= int(i):
                print("config index {}: out of range, max {}".format(self.config_name, i - 1))
                sys.exit(1)
            self.config_name = config_list[int(self.config_name)]

    def sync_env_for_new_config(self):
        lichee_ic = self.env.get_buildconfigs('LICHEE_IC')
        lichee_board = self.env.get_buildconfigs('LICHEE_BOARD')

        # if config for non-nor flash. we change to default
        act = act_sys_config(self.env.get("syconfig_path"))
        lichee_flash = act.get_lichee_flash_from_sys_config()
        if lichee_flash != 'nor':
            lichee_flash = 'default'
        top_dir = self.env.get("top_dir")
        do_cmd(f"cd {top_dir}; ./build.sh autoconfig -o openwrt -i {lichee_ic} -b {lichee_board} -n {lichee_flash}")

    def show_prepare_note_info(self, info, config_name):
        if info:
            print("\n\033[1;33m==================== [note]: {} ====================".format(config_name))
            for sstr in info:
                print("\033[1;33m" + sstr)
            print("\033[0m\n\n")
            user_input = input("\033[1;33m I have finished the processing. Please continue. [y/n] \033[0m")
            if user_input != 'y':
                sys.exit(1)

    def show_finish_note_info(self, info):
        if info:
            print("\n\033[1;33m==================== [note] ====================")
            for sstr in info:
                print("\033[1;33m" + sstr)
            print("\033[0m\n\n")

    def parse_cfgfile(self, in_depends=False, dep=None):
        quick_config_name = self.config_name
        if in_depends:
            quick_config_name = dep

        # pre-check options
        if quick_config_name in self.data:
            for k1, v1 in self.data[quick_config_name].items():
                k1 = str(k1)
                if k1 == 'prepare_note':
                    if not isinstance(v1, list):
                        print('Invalid Format, prepare_note need list. e.g.: ["aa", "bb"]')
                        return
                    self.prepare_note = v1
                    continue
                if k1 == 'check_distclean':
                    if not isinstance(v1, bool):
                        print('Invalid Format, check_distclean need bool. e.g.: True')
                        return
                    self.check_distclean = v1
                    continue
                if k1 == 'finish_note':
                    if not isinstance(v1, list):
                        print('Invalid Format, finish_noteneed list. e.g.: ["aa", "bb"]')
                        return
                    self.finish_note = v1
                    continue
                if k1 == 'force_config':
                    if not isinstance(v1, bool):
                        print('Invalid Format, force_config need bool. e.g.: True')
                        return
                    self.force_config = v1
                    continue
        else:
            print(f"Error: {quick_config_name} does not exist in quick_config")
            sys.exit(1)

        # check if distclean
        if not in_depends and self.check_distclean:
            if not self.args_force_config:
                if not check_sdk_diskclean_status(self.env.get_buildconfigs("LICHEE_PLAT_OUT"), quick_config_name):
                    sys.exit(1)

        # check config in key
        if quick_config_name not in self.data.keys():
            print("config: %s is not exists in %s" % (quick_config_name, self.config_file))
            sys.exit(1)

        if not in_depends:
            if 'internal' in self.data[quick_config_name].keys():
                if not self.force_config and not self.args_force_config:
                    print("\n[error]: \033[91m {} \033[0m".format(
                        "This is internal use quick_config, please do not use it directly!"))
                    sys.exit(1)

        if not in_depends and not self.force_config and not self.args_force_config:
            input_info = 'It will be overwrite SDK configuration with \'{}\' config, agree? [y/N] '.format(
                quick_config_name)
            user_input = input("\n[info]: \033[91m {} \033[0m".format(input_info))
            if user_input.lower() != 'y':
                sys.exit(1)

        # check depends
        if 'depends' in self.data[quick_config_name].keys():
            for dep in self.data[quick_config_name]['depends']:
                print('depends on {}'.format(dep))
                self.parse_cfgfile(dep=dep, in_depends=True)

        if 'configs' in self.data[quick_config_name].keys():
            val = self.data[quick_config_name]['configs']
            if not isinstance(val, dict):
                print('configs : invalid format, need dict')
                sys.exit(1)
            for k, v in val.items():
                print('Update quick_config configs: {}={}'.format(k, v))
                self.env.set_buildconfigs(k, v)

        if 'sync_env' in self.data[quick_config_name].keys():
            self.need_sync_env = True

        # when args_gen_dts_base is enable, we only run gen_dts_base
        if self.args_gen_dts_base:
            if quick_config_name in self.data:
                for k1, v1 in self.data[quick_config_name].items():
                    k1 = str(k1)
                    if k1 == 'gen_dts_base':
                        handler = self.handlers.get('gen_dts_base')
                        if handler:
                            handler(k1, v1)
                            return
            else:
                print(f"Error: {quick_config_name} does not exist in quick_config")
                sys.exit(1)

        if quick_config_name in self.data:
            self.show_prepare_note_info(self.prepare_note, quick_config_name)
            for k1, v1 in self.data[quick_config_name].items():
                k1 = str(k1)
                # Check if the key exists in the handlers dictionary
                handler = self.handlers.get(k1)
                if handler:
                    if handler != self.handle_default_handler:
                        print(f"\033[47;30m[QuickConfig] Now Parse {str(k1)} Configs {''.ljust(100 - len(k1))}\033[0m")
                    # Check if key starts with 'BoardConfig' to match all BoardConfig related keys
                    if k1.startswith('BoardConfig'):
                        self.need_sync_env = True
                    item_v1 = copy.deepcopy(v1)
                    handler(k1, item_v1)
                else:
                    print("unknown type : %s" % (k1))
        else:
            print(f"Error: {quick_config_name} does not exist in quick_config")
            sys.exit(1)

        if self.need_sync_env:
            self.sync_env_for_new_config()

    def init_handle(self):
        # Define a dictionary to map config types to their respective handler functions
        self.handlers = {
            'sysconfig': self.handle_sysconfig,
            'rtos_sysconfig': self.handle_rtos_sysconfig,
            'bootpkg': self.handle_bootpkg,
            'bootpkg_nor': self.handle_bootpkg_nor,
            'board.dts': self.handle_board_dts,
            'uboot-board.dts': self.handle_uboot_dts,
            'BoardConfig': self.handle_board_config,
            'BoardConfig_nor': self.handle_board_config_nor,
            'BoardConfigItem': self.handle_board_config_item,
            'BoardConfigItem_nor': self.handle_board_config_item_nor,
            'kernel': self.handle_kernel,
            'kernel_recovery': self.handle_kernel_recovery,
            'openwrt': self.handle_openwrt_defconfig,
            'env': self.handle_env,
            'env_nor': self.handle_env_nor,
            'partition': self.handle_partition,
            'partition_nor': self.handle_partition_nor,
            'rtos': self.handle_rtos,
            'uboot': self.handle_uboot,
            'uboot_nor': self.handle_uboot_nor,
            'uboot_efex': self.handle_uboot_efex,
            'boot0': self.handle_boot0,
            'cmd': self.handle_cmd,
            'sync_nand_map': self.handle_sync_nand_map,
            'amp_reserved_memory': self.handle_amp_reserved_memory,
            'gen_dts_base': self.handle_generate_device_tree_base,
        }

        default_handle = {
            'depends': self.handle_default_handler,
            'desc': self.handle_default_handler,
            'prepare_note': self.handle_default_handler,
            'finish_note': self.handle_default_handler,
            'configs': self.handle_default_handler,
            'force_config': self.handle_default_handler,
            'internal': self.handle_default_handler,
            'check_distclean': self.handle_default_handler,
            'sync_env': self.handle_default_handler,
            'tag': self.handle_default_handler,
        }

        self.handlers.update(default_handle)

    def handle_default_handler(self, _k1, _v1):
        return

    def handle_sysconfig(self, _k1, v1):
        sysconfig_act = act_sys_config(self.env.get("syconfig_path"))
        sysconfig_act.parse_sysconfig(v1)

    def handle_rtos_sysconfig(self, _k1, v1):
        if self.env.get("rtos_project") is None:
            print('rtos project not exists! ignore rtos_project config')
            return
        rtos_sysconf = '{}/rtos/board/{}/{}/configs/sys_config.fex'.format(
            self.env.get("top_dir"),
            self.env.get("rtos_device"),
            self.env.get("rtos_plat")
        )
        sysconfig_act = act_sys_config(rtos_sysconf)
        sysconfig_act.parse_sysconfig(v1)

    def handle_bootpkg(self, k1, v1):
        bootpkg_path = self.env.get("board_config_dir") + '/boot_package.cfg'
        if not os.path.exists(bootpkg_path):
            bootpkg_path = self.env.get("board_config_dir") + '/../default/boot_package.cfg'
        if not os.path.exists(bootpkg_path):
            print("%s is not exists" % bootpkg_path)
            return
        bootpkg_act = act_parse_bootpkg(bootpkg_path)
        bootpkg_act.parse_bootpkg(v1)

    def handle_bootpkg_nor(self, k1, v1):
        bootpkg_path = self.env.get("board_config_dir") + '/boot_package_nor.cfg'
        if not os.path.exists(bootpkg_path):
            bootpkg_path = self.env.get("board_config_dir") + '/../default/boot_package_nor.cfg'
        if not os.path.exists(bootpkg_path):
            print("%s is not exists" % bootpkg_path)
            return
        bootpkg_act = act_parse_bootpkg(bootpkg_path)
        bootpkg_act.parse_bootpkg(v1)

    def handle_board_dts(self, k1, v1):
        dts = act_device_tree(self.env.get("kernel_dts_path"))
        dts.parse_dts_cfg(v1)

    def handle_uboot_dts(self, k1, v1):
        if self.env.get("uboot_dts_path") is not None:
            dts = act_device_tree(self.env.get("uboot_dts_path"))
            dts.parse_dts_cfg(v1)
        else:
            print('uboot-board.dts not exist, skip uboot-board.dts item')

    def handle_board_config(self, k1, v1):
        BoardConfig = None
        for p in self.env.get("search_list"):
            BoardConfig_path = '{}/BoardConfig.mk'.format(p)
            if os.path.exists(BoardConfig_path):
                BoardConfig = BoardConfig_path
                break
        if BoardConfig is not None:
            act = act_board_config(BoardConfig_path=BoardConfig)
            act.parse_board_cfg(v1)
        else:
            print('BoardConfig not exist, skip BoardConfig item')

    def handle_board_config_nor(self, k1, v1):
        BoardConfig = None
        for p in self.env.get("search_list"):
            BoardConfig_path = '{}/BoardConfig_nor.mk'.format(p)
            if os.path.exists(BoardConfig_path):
                BoardConfig = BoardConfig_path
                break
        if BoardConfig is not None:
            act = act_board_config(BoardConfig_path=BoardConfig)
            act.parse_board_cfg(v1)
        else:
            print('BoardConfig not exist, skip BoardConfig_nor item')

    def handle_board_config_item(self, k1, v1):
        BoardConfig = None
        for p in self.env.get("search_list"):
            BoardConfig_path = '{}/BoardConfig.mk'.format(p)
            if os.path.exists(BoardConfig_path):
                BoardConfig = BoardConfig_path
                break
        if BoardConfig is not None:
            act = act_board_config(BoardConfig_path=BoardConfig)
            act.parse_board_multi_string_cfg(v1)
        else:
            print('BoardConfig not exist, skip BoardConfig item')

    def handle_board_config_item_nor(self, k1, v1):
        BoardConfig = None
        for p in self.env.get("search_list"):
            BoardConfig_path = '{}/BoardConfig_nor.mk'.format(p)
            if os.path.exists(BoardConfig_path):
                BoardConfig = BoardConfig_path
                break
        if BoardConfig is not None:
            act = act_board_config(BoardConfig_path=BoardConfig)
            act.parse_board_multi_string_cfg(v1)
        else:
            print('BoardConfig not exist, skip BoardConfig_nor item')

    def handle_kernel(self, k1, v1):
        act = act_kernel_defconfig(self.env)
        act.parse_kernel_defconfig(v1)

    def handle_kernel_recovery(self, k1, v1):
        defconfig_path = self.env.get("kernel_recovery_defconf")
        if defconfig_path is not None:
            act = act_common_defconfig(defconfig_path, env=self.env)
            act.parse_common_defconfig(v1)
        else:
            print(f"kernel_recovery_defconf {defconfig_path} not found, skip it.")

    def handle_openwrt_defconfig(self, k1, v1):
        lichee_ic = self.env.get_buildconfigs('LICHEE_IC')
        lichee_board = self.env.get_buildconfigs('LICHEE_BOARD')
        openwrt_dir = '{}/openwrt/openwrt/'.format(self.env.get("top_dir"))
        search_path = []
        if os.path.exists(
                '{}/target/{}/openwrt/{}-{}/defconfig'.format(self.env.get("top_dir"), lichee_ic, lichee_ic,
                                                              lichee_board)):
            # ${TINA_TOPDIR}/target/$LICHEE_IC/openwrt/$LICHEE_IC-$LICHEE_BOARD
            defconfig = '{}/target/{}/openwrt/{}-{}/defconfig'.format(self.env.get("top_dir"), lichee_ic, lichee_ic,
                                                                      lichee_board)
            search_path.append(os.path.dirname(defconfig) + '/configs')
            search_path.append(os.path.dirname(defconfig))
            search_path.append(
                '{}/target/{}/openwrt/{}-common/configs'.format(self.env.get("top_dir"), lichee_ic, lichee_ic))
            search_path.append('{}/target/{}/openwrt/{}-common'.format(self.env.get("top_dir"), lichee_ic, lichee_ic))
        else:
            # ${TINA_TOPDIR}/openwrt/target/$LICHEE_IC/$LICHEE_IC-$LICHEE_BOARD
            defconfig = '{}/openwrt/target/{}/{}-{}/defconfig'.format(self.env.get("top_dir"), lichee_ic, lichee_ic,
                                                                      lichee_board)
            search_path.append(os.path.dirname(defconfig) + '/configs')
            search_path.append(os.path.dirname(defconfig))
            search_path.append(
                '{}/openwrt/target/{}/{}-common/configs'.format(self.env.get("top_dir"), lichee_ic, lichee_ic))
            search_path.append('{}/openwrt/target/{}/{}-common'.format(self.env.get("top_dir"), lichee_ic, lichee_ic))
        act = act_openwrt_defconfig(defconfig_path=defconfig, env=self.env)
        act.parse_openwrt_defconfig(search_path, openwrt_dir, v1)

    def handle_openwrt_board_makefile(self, k1, v1):
        lichee_ic = self.env.get_buildconfigs('LICHEE_IC')
        lichee_board = self.env.get_buildconfigs('LICHEE_BOARD')
        if (os.path.exists(
                '{}/target/{}/openwrt/{}-{}/Makefile'.format(self.env.get("top_dir"), lichee_ic, lichee_ic,
                                                             lichee_board))):
            board_makefile = '{}/target/{}/openwrt/{}-{}/Makefile'.format(self.env.get("top_dir"), lichee_ic, lichee_ic,
                                                                          lichee_board)
        else:
            board_makefile = '{}/openwrt/target/{}/{}-{}/Makefile'.format(self.env.get("top_dir"), lichee_ic, lichee_ic,
                                                                          lichee_board)
        if os.path.exists(board_makefile):
            act = act_openwrt_makefile(board_makefile)
            act.parse_openwrt_board_makefile(v1)
        else:
            print("%s is not exists, skip parse" % board_makefile)
            return

    def handle_env(self, k1, v1):
        env_fils = [
            'env-{}.cfg'.format(self.env.get_buildconfigs('LICHEE_KERNEL_VERSION').rsplit('.', 1)[0]),
            "env.cfg"
        ]
        env_path = ''
        for p in self.env.get("search_list"):
            for f in env_fils:
                env_path = '{}/{}'.format(p, f)
                if os.path.exists(env_path):
                    break
            if os.path.exists(env_path):
                break
        if not os.path.exists(env_path):
            print("%s is not exists" % env_path)
            return
        act = act_env(env_path)
        act.parse_env_cfg(v1)

    def handle_env_nor(self, k1, v1):
        env_fils = [
            'env-{}.cfg'.format(self.env.get_buildconfigs('LICHEE_KERNEL_VERSION').rsplit('.', 1)[0]),
            "env_nor.cfg"
        ]
        for p in self.env.get("search_list"):
            for f in env_fils:
                env_path = '{}/{}'.format(p, f)
                if os.path.exists(env_path):
                    break
            if os.path.exists(env_path):
                break
        if not os.path.exists(env_path):
            print("%s is not exists" % env_path)
            return
        act = act_env(env_path)
        act.parse_env_cfg(v1)

    def handle_partition(self, k1, v1):
        partition_path = ''
        for search in self.env.get("search_list"):
            partition_path = '{}/sys_partition.fex'.format(search)
            if os.path.exists(partition_path):
                break
        if not os.path.exists(partition_path):
            print("%s is not exists" % partition_path)
            return
        act_part = act_sys_partition(partition_path, self.env)
        act_part.parse_sys_partition(v1)
        item_dict = act_part._get_partition_info()

        act_dts = act_device_tree(self.env.get("kernel_dts_path"))
        act_dts.update_bootargs_by_partitions(item_dict, self.env.get_buildconfigs('LICHEE_FLASH'))

    def handle_partition_nor(self, k1, v1):
        partition_path = ''
        for search in self.env.get("search_list"):
            partition_path = '{}/sys_partition_nor.fex'.format(search)
            if os.path.exists(partition_path):
                break
        if not os.path.exists(partition_path):
            print("%s is not exists" % partition_path)
            return
        act_part = act_sys_partition(partition_path, self.env)
        act_part.parse_sys_partition(v1)
        item_dict = act_part._get_partition_info()

        act_dts = act_device_tree(self.env.get("kernel_dts_path"))
        act_dts.update_bootargs_by_partitions(item_dict, self.env.get_buildconfigs('LICHEE_FLASH'))

    def handle_rtos(self, k1, v1):
        if self.env.get("rtos_project") is None:
            print('rtos project not exist, skip it')
            return
        rtos_defconf = '{}/rtos/lichee/rtos/projects/{}/{}/defconfig'.format(
            self.env.get("top_dir"),
            self.env.get("rtos_device"),
            self.env.get("rtos_plat")
        )
        act = act_rtos_defconfig(rtos_defconf, self.env)
        act.parse_rtos_defconfig(v1)

    def handle_uboot(self, k1, v1):
        uboot_defconfig_path = self.env.get("uboot_defconfig_path")
        if uboot_defconfig_path is None:
            print('uboot defconfig not exist, skip it')
            return
        act = act_uboot_defconfig(uboot_defconfig_path, self.env)
        act.parse_uboot_defconfig(v1)

    def handle_uboot_nor(self, k1, v1):
        uboot_defconfig_path = self.env.get("uboot_nor_defconfig_path")
        if uboot_defconfig_path is None:
            print('uboot nor defconfig not exist, skip it')
            return
        act = act_uboot_defconfig(uboot_defconfig_path, self.env)
        act.parse_uboot_defconfig(v1)

    def handle_uboot_efex(self, k1, v1):
        uboot_defconfig_path = self.env.get("uboot_efex_defconfig_path")
        if uboot_defconfig_path is None:
            print('uboot efex defconfig not exist, skip it')
            return
        act = act_uboot_defconfig(uboot_defconfig_path, self.env)
        act.parse_uboot_defconfig(v1)

    def handle_boot0(self, k1, v1):
        lichee_chip = self.env.get_buildconfigs('LICHEE_CHIP')
        boot0_board_path = '{}/brandy/brandy-2.0/spl/board/{}'.format(self.env.get("top_dir"), lichee_chip)
        if os.path.exists(boot0_board_path):
            act = act_boot0(boot0_board_path)
            act.parse_boot0_config(v1)
        else:
            print('boot not exist, skip it')
            return

    def handle_cmd(self, k1, v1):
        if not isinstance(v1, list):
            print('cmd : invalid item format, need [ ]')
            return

        custom_env = self.env.get("configs").copy()
        custom_env.update(os.environ.copy())

        for cmd in v1:
            cmd = parse_var(self.env.get("builtin_var"), cmd)
            ret = do_cmd(cmd, custom_env)
            if ret != 0:
                print('exec {} failed, ret = {}'.format(cmd, ret))
                break
        return

    def handle_sync_nand_map(self, k1, v1):
        uboot_dts_path = self.env.get("uboot_dts_path")
        kernel_dts_path = self.env.get("kernel_dts_path")
        if uboot_dts_path is not None and kernel_dts_path is not None:
            partition_path = ''
            for search in self.env.get("search_list"):
                partition_path = '{}/sys_partition.fex'.format(search)
                if os.path.exists(partition_path):
                    break
            if not os.path.exists(partition_path):
                print("%s is not exists" % partition_path)
                return
            act_part = act_sys_partition(partition_path, self.env)
            items_dict = act_part._get_partition_info()
            act_map = act_nand_map(uboot_dts_path, items_dict)

            nand_info_bootargs = act_map.update_nand_mtdparts(v1)

            act_dts = act_device_tree(kernel_dts_path)
            act_dts.parse_dts_cfg(nand_info_bootargs)
        else:
            print('uboot-board.dts or board.dts not exist, skip sync_nand_map item')

    def handle_amp_reserved_memory(self, k1, v1):
        kernel_dts_path = self.env.get("kernel_dts_path")
        if self.env.get("rtos_project") is None:
            print('rtos project not exist, skip it')
            return
        rtos_defconf = '{}/rtos/lichee/rtos/projects/{}/{}/defconfig'.format(
            self.env.get("top_dir"),
            self.env.get("rtos_device"),
            self.env.get("rtos_plat")
        )
        act = act_rtos_reserved_memory(kernel_dts_path)
        act.update_reserved_memory_layout(v1)
        dts_config = act.get_update_reserved_memory_layout_quick_config()

        rtos_defconfig_lines = act.get_update_reserved_memory_layout_rtos_link_config(v1)
        kernel_defconfig_lines = act.get_update_reserved_memory_layout_kernel_link_config(v1)

        act_dts = act_device_tree(kernel_dts_path)
        act_dts.parse_dts_cfg(dts_config)

        if kernel_defconfig_lines != None and len(kernel_defconfig_lines) != 0:
            act_kernel = act_kernel_defconfig(self.env)
            act_kernel.parse_kernel_defconfig(kernel_defconfig_lines)

        if rtos_defconfig_lines != None and len(rtos_defconfig_lines) != 0:
            act_rtos = act_rtos_defconfig(rtos_defconf, self.env)
            act_rtos.parse_rtos_defconfig(rtos_defconfig_lines)

    def handle_generate_device_tree_base(self, k1, v1):
        if self.args_gen_dts_base:
            act = act_device_tree(self.env.get("kernel_dts_path"))
            ret = act.generate_device_tree_base(v1)
            json_str = json.dumps(ret, indent=4)
            print(json_str)
