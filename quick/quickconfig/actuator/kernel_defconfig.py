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

'''
"kernel" : [
	"fragment文件名 or 配置名 or !配置名(表示去掉某个配置)"
    "lock_defconfig.fragment", "ftrace_defconfig.fragment",
    "# CONFIG_AW_GPADC is not set", "CONFIG_LOG_BUF_SHIFT=15"
],
'''

from quickconfig.utils import backup_file, restore_file, DiffSummary, do_cmd


class act_kernel_defconfig:
    def __init__(self, env):
        self.defconfig = env.get("kernel_defconf")
        self.top_dir = env.get("top_dir")
        self.board_config_dir = env.get("board_config_dir")
        self.kernel_ver = env.get("kernel_ver")
        self.kernel_src_path = env.get("kernel_src_path")
        self.bsp_path = env.get("bsp_path")
        self.kernel_cross_compile = env.get("kernel_cross_compile")
        self.configs = env.get("configs")

    def load_kernel_defconfig(self):
        cmd = "cd {}; ./build.sh loadconfig".format(self.top_dir)
        ret = do_cmd(cmd)
        if ret != 0:
            print('exec {} failed, ret = {}'.format(cmd, ret))
            return -1

        return 0

    def merge_kernel_config(self, fragment):
        framgment_list = [
            # 1. ${LICHEE_BOARD_CONFIG_DIR}/${LICHEE_KERN_VER}/
            '{}/{}'.format(self.board_config_dir, self.kernel_ver),
            # 2. $LICHEE_BSP_DIR/configs/$LICHEE_KERN_VER/
            '{}/configs/{}'.format(self.bsp_path, self.kernel_ver)
        ]

        fragment_path = fragment

        if os.path.exists(fragment):
            fragment_path = fragment
        else:
            for search in framgment_list:
                if os.path.exists('{}/{}'.format(search, fragment)):
                    fragment_path = '{}/{}'.format(search, fragment)

        if not os.path.exists(fragment_path):
            print('fragment: {} is not exist'.format(fragment))
            return -1

        kernel_build = '{}/out/kernel/build'.format(self.top_dir)
        merge_sh = '{}/scripts/kconfig/merge_config.sh'.format(self.kernel_src_path)
        kernel_config = '{}/.config'.format(kernel_build)
        pwd = os.getcwd()

        cmd = '{} -m {} {}'.format(merge_sh, kernel_config, fragment_path)
        do_cmd(cmd)
        cmd = 'mv {}/.config {}'.format(pwd, kernel_config)
        do_cmd(cmd)

        # cmd = "{} -m /build.sh loadconfig {}".format(top_dir, fragment_path)
        # do_cmd(cmd)
        return 0

    def save_kernel_defconfig(self):
        make = '{}/prebuilt/hostbuilt/make4.1/bin/make'.format(self.top_dir)

        kernel_build = '{}/out/kernel/build'.format(self.top_dir)
        tmp_defconf = '{}/defconfig'.format(kernel_build)
        arch = self.configs['LICHEE_KERNEL_ARCH']

        custom_env = {
            'BSP_TOP': self.configs['LICHEE_BSP_DIR'] + '/',
            'CROSS_COMPILE': self.kernel_cross_compile
        }
        cmd = 'cd {}; {} -C {} ARCH={} O={} savedefconfig'.format(self.kernel_src_path, make, self.kernel_src_path,
                                                                  arch,
                                                                  kernel_build)
        ret = do_cmd(cmd, custom_env)
        if ret != 0:
            print('exec {} failed, ret = {}'.format(cmd, ret))
            return -1

        cmd = 'mv {} {}'.format(tmp_defconf, self.defconfig)
        do_cmd(cmd)

        # cmd = "{}/build.sh saveconfig".format(top_dir)
        # do_cmd(cmd)
        return 0

    def parse_kernel_defconfig(self, val):
        work_path = '{}/{}/'.format(self.board_config_dir, self.kernel_ver)
        tmpfile = '.tmp.fragment'
        special_conf = []

        if not isinstance(val, list):
            print('kernel : invalid format, need list')
            sys.exit(1)

        ret = self.load_kernel_defconfig()
        if ret < 0:
            print('kernel : loadconfig for {} failed!'.format(self.defconfig))
            sys.exit(1)

        backup_file(self.defconfig)
        for item in val:
            if item.endswith('.fragment'):
                ret = self.merge_kernel_config(item)
                if ret < 0:
                    restore_file(self.defconfig)
                    sys.exit(1)
            else:
                if item[0] == '#':
                    # CONFIG_XXXX is not set
                    item = item.split()[1].strip()
                    if '=' in item:
                        item = item.split('=')[0].strip()
                    cfgline = '# {} is not set'.format(item)
                elif '=' in item:
                    cfgline = '{}'.format(item.strip())
                special_conf.append(cfgline)

        if len(special_conf) > 0:
            with open(work_path + tmpfile, 'w') as f:
                for item in special_conf:
                    f.write(item + '\n')
            ret = self.merge_kernel_config(tmpfile)
            if ret < 0:
                restore_file(self.defconfig)
                sys.exit(1)

        ret = self.save_kernel_defconfig()
        if ret < 0:
            restore_file(self.defconfig)
            sys.exit(1)

        if len(special_conf) > 0:
            cmd = "rm {}".format(work_path + tmpfile)
            do_cmd(cmd)

        diff = DiffSummary()
        diff.record_diff(self.defconfig)
