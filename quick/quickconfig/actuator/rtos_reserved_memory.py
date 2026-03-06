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
"amp_reserved_memory": {
    "memory_regions": [
        {
            "name": "e907_dram_reserved",
            "addr": "0x41000000",
            "size": "0x500000",
            "type": "independent"
        },
        {
            "name": "e907_rpbuf_reserved",
            "size": "0x100000",
            "type": "follow_prev"
        }
    ],
    "kernel_config_link": [
        {
            "name": "isp_dram_reserved",
            "type": "end_address_offset",
            "link": "CONFIG_VIN_SENSOR_RESERVE_ADDR",
            "offset": "0x2000"
        }
    ],
    "rtos_config_link": [
        {
            "name": "e907_dram_reserved",
            "type": "address_start",
            "link": "CONFIG_ARCH_START_ADDRESS"
        },
        {
            "name": "e907_dram_reserved",
            "type": "size_hex",
            "link": "CONFIG_ARCH_MEM_LENGTH"
        },
        {
            "name": "isp_dram_reserved",
            "type": "address_start",
            "link": "CONFIG_ISP_MEMRESERVE_ADDR"
        },
        {
            "name": "isp_dram_reserved",
            "type": "size_hex",
            "link": "CONFIG_ISP_MEMRESERVE_LEN"
        },
        {
            "name": "e907_rpbuf_reserved",
            "type": "address_start",
            "link": "CONFIG_COMPONENTS_RPBUF_RESERVED_MEM_ADDR"
        },
        {
            "name": "e907_rpbuf_reserved",
            "type": "size_hex",
            "link": "CONFIG_COMPONENTS_RPBUF_RESERVED_MEM_SIZE"
        }
    ]
}
'''

from quickconfig.utils import backup_file, restore_file, DiffSummary, do_cmd_with_output, do_cmd

MODULE_DEBUG = False


class MemoryRegion:
    def __init__(self, name, base, size, compatible=None, no_map=False, follow_prev=False):
        self.name = name
        self.base = base
        self.size = size
        self.compatible = compatible
        self.no_map = no_map
        self.follow_prev = follow_prev

    def __repr__(self):
        return f"MemoryRegion(name={self.name}, base=0x{self.base:x}, size=0x{self.size:x}, compatible={self.compatible}, no_map={self.no_map}, follow_prev={self.follow_prev})"

    def end_address(self):
        return self.base + self.size


def adjust_memory_region_base(previous_region, current_region):
    # Calculate the new base address so that the base of the current region is greater than the end address of the previous region
    new_base = previous_region.end_address()

    # If the base address has changed, update the base of the current region
    if current_region.base < new_base:
        current_region.base = new_base
        if MODULE_DEBUG:
            print(f"Adjusting memory region: {current_region.name} -> New base address: 0x{new_base:x}")


def parse_device_tree(device_tree):
    regions = []
    node_pattern = re.compile(r"(\w+):\s*(\w+@[\w\.\:]+)\s*\{(.*?)\}", re.DOTALL)
    reg_pattern = re.compile(r"reg\s*=\s*<0x0\s*(0x[0-9a-fA-F]+)\s*0x0\s*(0x[0-9a-fA-F]+)>;")
    compatible_pattern = re.compile(r"compatible\s*=\s*\"([^\"]+)\";")
    no_map_pattern = re.compile(r"no-map;")

    for match in node_pattern.finditer(device_tree):
        name = match.group(1)
        address = match.group(2)
        properties = match.group(3)
        compatible = None
        no_map = False

        reg_match = reg_pattern.search(properties)
        if reg_match:
            base = int(reg_match.group(1), 16)
            size = int(reg_match.group(2), 16)
        else:
            continue

        compatible_match = compatible_pattern.search(properties)
        if compatible_match:
            compatible = compatible_match.group(1)

        if no_map_pattern.search(properties):
            no_map = True

        region = MemoryRegion(name, base, size, compatible, no_map)
        regions.append(region)

    return regions


def check_contiguous(region1, region2):
    if region1.end_address() == region2.base:
        return True
    return False


class act_rtos_reserved_memory:
    def __init__(self, dts_file_path):
        self.dts_file_path = dts_file_path
        self.reserved_memory_regions = None
        self.parser_rtos_reserved_memory()

    def parser_rtos_reserved_memory(self):
        with open(self.dts_file_path, 'r') as f:
            dts_data = f.read()
        self.reserved_memory_regions = parse_device_tree(dts_data)
        self.check_rtos_reserved_memory_contiguous()

    def check_rtos_reserved_memory_contiguous(self):
        contiguous = []
        non_contiguous = []

        for i in range(len(self.reserved_memory_regions) - 1):
            if check_contiguous(self.reserved_memory_regions[i], self.reserved_memory_regions[i + 1]):
                contiguous.append((self.reserved_memory_regions[i].name, self.reserved_memory_regions[i + 1].name))
                self.reserved_memory_regions[i + 1].follow_prev = True
            else:
                non_contiguous.append((self.reserved_memory_regions[i].name, self.reserved_memory_regions[i + 1].name))
                self.reserved_memory_regions[i + 1].follow_prev = False

    def check_memory_overlap(self):
        overlap_regions = []

        # Traverse all memory regions and check for overlaps
        for i in range(1, len(self.reserved_memory_regions)):
            current_region = self.reserved_memory_regions[i]
            previous_region = self.reserved_memory_regions[i - 1]

            # If the base address of the current region is less than the end address of the previous region, an overlap has occurred
            if current_region.follow_prev:
                if current_region.base < previous_region.end_address():
                    overlap_regions.append((previous_region.name, current_region.name))

                    # Adjust the base address of the current region to avoid overlap
                    adjust_memory_region_base(previous_region, current_region)

        return overlap_regions

    def update_reserved_memory_layout(self, v1):
        # Map the regions from the new layout
        new_regions = {}

        try:
            for region in v1["memory_regions"]:
                new_regions[region["name"]] = {
                    "addr": region.get("addr"),
                    "size": region.get("size"),
                    "type": region.get("type", "independent")  # Default to independent if not specified
                }

            # Iterate through the current memory regions and update based on new layout
            for region in self.reserved_memory_regions:
                if region.name in new_regions:
                    new_region = new_regions[region.name]
                    if new_region["type"] == "independent":
                        region.follow_prev = False
                        # Set the base address and size directly from the JSON
                        if "addr" in new_region and new_region["addr"] is not None:
                            region.base = int(new_region["addr"], 16)  # Update base address
                        if "size" in new_region and new_region["size"] is not None:
                            region.size = int(new_region["size"], 16)  # Update size
                    elif new_region["type"] == "follow_prev":
                        # For "follow_prev", calculate the start address as the end of the previous region
                        region.follow_prev = True
                        if len(self.reserved_memory_regions) > 0:
                            previous_region = self.reserved_memory_regions[self.reserved_memory_regions.index(region) - 1]
                            region.base = previous_region.end_address()  # Set start address to the end of the previous region
                        if "size" in new_region and new_region["size"] is not None:
                            region.size = int(new_region["size"], 16)  # Update size

            if MODULE_DEBUG:
                print(self.reserved_memory_regions)

            # Check and adjust memory overlap
            overlap_regions = self.check_memory_overlap()
            if MODULE_DEBUG:
                if overlap_regions:
                    print("Memory overlap regions adjusted:")
                    for overlap in overlap_regions:
                        print(f"Overlapping regions: {overlap[0]} and {overlap[1]}")
                for region in self.reserved_memory_regions:
                    print(region)
        except KeyError:
            print("KeyError found in config, skip update_reserved_memory_layout")
            pass

    def get_update_reserved_memory_layout_quick_config(self):
        dts_config = {
            'set_property_with_address': {}
        }

        for region in self.reserved_memory_regions:
            rtos_memory_reg = {
                'reg': f'<0x0 {hex(region.base).lower()} 0x0 {hex(region.size).lower()}>'
            }
            dts_config['set_property_with_address'][region.name] = rtos_memory_reg

        return dts_config

    def get_update_reserved_memory_layout_link_config(self, links):
        config_line = []
        for link in links:
            for region in self.reserved_memory_regions:
                if link.get('name') == region.name:
                    if link.get('type') == 'address_start':
                        link_name = link.get('link')
                        config_line.append(f'{link_name}={hex(region.base).lower()}')
                    elif link.get('type') == 'size_hex':
                        link_name = link.get('link')
                        config_line.append(f'{link_name}={hex(region.size).lower()}')
                    elif link.get('type') == 'start_address_offset':
                        offset = int(link.get('offset'), 16)
                        link_name = link.get('link')
                        config_line.append(f'{link_name}={hex(region.base + offset).lower()}')
                    elif link.get('type') == 'end_address_offset':
                        offset = int(link.get('offset'), 16)
                        link_name = link.get('link')
                        config_line.append(f'{link_name}={hex(region.base + region.size - offset).lower()}')
                    else:
                        print(f"Unsupported type {link.get('type')}")
        return config_line

    def get_update_reserved_memory_layout_kernel_link_config(self, v1):
        if v1.get('kernel_config_link'):
            return self.get_update_reserved_memory_layout_link_config(v1.get('kernel_config_link'))
        return None

    def get_update_reserved_memory_layout_rtos_link_config(self, v1):
        if v1.get('rtos_config_link'):
            return self.get_update_reserved_memory_layout_link_config(v1.get('rtos_config_link'))
        return None
