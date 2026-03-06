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

import re


def nand_parse_partition_data(input_str):
    partitions = []
    lines = input_str.splitlines()
    part_name = None
    phy_block_num = None
    for line in lines:
        match_name = re.search(r'part_name = "(.*?)";', line)
        if match_name:
            part_name = match_name.group(1)
        match_blocks = re.search(r'phy_block_num = <(\d+)>;', line)
        if match_blocks:
            phy_block_num = int(match_blocks.group(1))
        if part_name and phy_block_num:
            partitions.append((part_name, phy_block_num))
            part_name = None
            phy_block_num = None
    return partitions


def nand_generate_ro_mtdparts(ro_parts_data):
    start_addr = 0
    mtdparts = []
    for part in ro_parts_data["ro_parts"]:
        part_name = part["name"]
        size_in_kb = int(part["size"].replace("k", ""))
        mtdparts.append(f"{size_in_kb}k@{start_addr}({part_name})ro,")
        start_addr += size_in_kb * 1024
    return mtdparts, start_addr


def nand_generate_mtdparts(partitions, start_addr):
    mtdparts = []
    for part_name, phy_block_num in partitions:
        size_in_kb = phy_block_num * 128
        mtdparts.append(f"{size_in_kb}k@{start_addr}({part_name}),")
        start_addr += size_in_kb * 1024
    return mtdparts


def nand_process_partition_table(input_str, val):
    mtdparts = ["nand:"]
    ro_part, start_addr = nand_generate_ro_mtdparts(val)
    mtdparts.extend(ro_part)
    partitions = nand_parse_partition_data(input_str)
    mtdparts.extend(nand_generate_mtdparts(partitions, start_addr))
    return mtdparts, partitions


class act_nand_map:
    def __init__(self, uboot_dts_path, items_dict):
        self.uboot_dts_path = uboot_dts_path
        self.items_dict = items_dict

    def update_nand_mtdparts(self, val):
        with open(self.uboot_dts_path, 'r') as uboot_file:
            uboot_content = uboot_file.read()
        mtdparts_data, uboot_partitions = nand_process_partition_table(uboot_content, val)
        mtdparts_data.append("-(sys)")

        partition = "mtd@ubi0_0:"
        has_udisk = False
        part_index = 1
        part_rootfs_index = 0
        for i in range(len(self.items_dict)):
            v = self.items_dict[i]
            if not any(v['name']['val'] == item[0] for item in uboot_partitions):
                if 'user_type' not in v.keys():
                    continue
                partition = partition + '{}@ubi0_{}:'.format(v['name']['val'], part_index)
                part_index += 1
                if v['name']['val'] == 'UDISK':
                    has_udisk = True
                if v['name']['val'] == 'rootfs':
                    part_rootfs_index = part_index - 1
        if not has_udisk:
            # add UDSIK partition
            partition = partition + 'UDISK@ubi0_{}:'.format(part_index + 1)
        if partition[-1] == ':':
            partition = partition[:-1]

        bootargs_dict = {'bootargs': {'mtdparts': ''.join(mtdparts_data), "partitions": partition,
                                      "root": '/dev/ubiblock0_{}'.format(part_rootfs_index)}}
        return bootargs_dict
