#!/usr/bin/env python3

import sys
import argparse
from construct import (
	Struct, BitStruct,
	Byte, Bytes,
	Int16ul, Int32ul, Int8ul,
	Flag, Const)

# FAT16 Boot Sector struct
fat16_bs_s = Struct(
	'boot_jmp' / Bytes(3),
	'oem_id' / Bytes(8),
	'bytes_per_sector' / Int16ul,
	'sectors_per_cluster' / Byte,
	'reserved_sectors' / Int16ul,
	'table_count' / Byte,
	'root_entry_count' / Int16ul,
	'total_sectors_16' / Int16ul,
	'media_type' / Byte,
	'table_size16'/ Int16ul,
	'sectors_per_track' / Int16ul,
	'head_side_count' / Int16ul,
	'hidden_sector_count' / Int32ul,
	'total_sectors_32' / Int32ul,
	'extended' / Bytes(54))

# 8.3 format entry struct
standart83_s = Struct(
	'name' / Bytes(8),
	'ext' / Bytes(3),
	'attributes' / Byte,
	'reservedNT' / Byte,
	'creation_tenths' / Int8ul,
	'creation_time' / Bytes(2),
	'creation_date' / Bytes(2),
	'last_accessed' / Bytes(2),
	'cluster_high16' / Int16ul,# zeros
	'modification_time' / Bytes(2),
	'modification_date' / Bytes(2),
	'cluster_low16' / Int16ul,
	'file_size' / Int32ul)

# 8.3 attribute bit struct
s83_attr_s = BitStruct(
	'unused' / Flag,
	'device' / Flag,
	'archive' / Flag,
	'subDir' / Flag,
	'volumeLabel' / Flag,
	'system' / Flag,
	'hidden' / Flag,
	'readonly' / Flag)

# Long File Name struct
lfn_s = Struct(
	'seq' / Byte,
	'name1' / Bytes(10),
	'attributes' / Byte,
	'type' / Byte,# 0x00
	'checksum' / Byte,
	'name2' / Bytes(12),
	'first_cluster' / Bytes(2),#0x0000
	'name3' / Bytes(4))

def main():
	parser = argparse.ArgumentParser(description='A simple fat16 image summary tool.')
	parser.add_argument('img',nargs='?',default='images/fat16_1sectorpercluster.img',help='path to the image file (uncompressed .img or .iso)')
	args = parser.parse_args()
  
	file_path = args.img

	try:
		file =  open(file_path,'rb')
	except:
		print(f'Error: can not open file {file_path}.')
		return -1
	
	# reading boot sector
	print('Reading Boot Record\n')
	bs = fat16_bs_s.parse(file.read(90))

	print(f'{"Reserved sectors:":<25} {bs.reserved_sectors:>5}')
	print(f'{"Bytes per sector:":<25} {bs.bytes_per_sector:>5}')
	print(f'{"Sectors per cluster:":<25} {bs.sectors_per_cluster:>5}')
	print(f'{"FAT tables:":<25} {bs.table_count:>5}')
	print(f'{"FAT table size:":<25} {bs.table_size16:>5}')
	print(f'{"Root directory entries:":<25} {bs.root_entry_count:>5}')
	temp = bs.total_sectors_16 + (bs.total_sectors_32 << 16)
	print(f'{"Total sectors:":<20} {temp:>10}')

	# addresses
	print('\nAddresses\n')

	print('Boot Record at: 0x0')

	for i in range(0,bs.table_count):
		temp = bs.reserved_sectors + (i * bs.table_size16)
		print(f'FAT {i+1} at: 0x{temp * bs.bytes_per_sector:0>8x}, sector {temp}')

	root_sec = bs.reserved_sectors + (bs.table_count * bs.table_size16)
	root_addr =  root_sec * bs.bytes_per_sector
	print(f'Root directory at: 0x{root_addr:0>8x}, sector {root_sec}')

	data_sec = root_sec + (bs.root_entry_count * 32 // bs.bytes_per_sector)
	data_addr = data_sec * bs.bytes_per_sector
	print(f'Data at: 0x{data_addr:0>8x}, sector {data_sec}')

	tables_sec = bs.reserved_sectors
	tables_addr = tables_sec * bs.bytes_per_sector
	### load tables
	file.seek(tables_addr)
	fat_tables = []
	fat_entries = bs.table_size16 * bs.bytes_per_sector // 2
	for i in range(0,bs.table_count):
		table = []
		for e in range(0,fat_entries):
			table.append(int.from_bytes(file.read(2),'little'))
		fat_tables.append(table)
		pass

	if fat_tables.count(fat_tables[0]) != len(fat_tables): # dont do shit like this
		print('Warning: FAT tables are not equal')

	# ls root
	file.seek(root_addr)
	entries_left = bs.root_entry_count
	root_entries = []
	while entries_left > 0:
		entries_left -= 1
		buf = file.read(32)
		# if its a file or a directory, and not deleted
		if (buf[11] == 0x20 or buf[11] == 0x10) and buf[0] != 0xe5:
			root_entries.append(standart83_s.parse(buf))
			pass
		pass
	
	print("\nRoot Directory\n")
	
	for e in root_entries:# or this
		name = f'{e.name.decode().replace(" ","")}.{e.ext.decode().replace(" ","")}' if e.attributes == 0x20 else f'{e.name.decode().replace(" ","")}/'
		attr = f'0x{e.attributes:0>2x}'
		fc = e.cluster_low16
		addr = ((fc - 2) * bs.sectors_per_cluster + data_sec) * bs.bytes_per_sector
		size = f'{e.file_size} Bytes' if e.attributes == 0x20 else ''
		out = f'[{attr}] {name: <12} at FAT[{fc:4}] (0x{addr:0>8x}) {size}'
		print(out)
		pass

	# cat file

	print('\nContents of a file\n')
	for e in root_entries:
		if e.attributes == 0x20:
			name = f'{e.name.decode().replace(" ","")}.{e.ext.decode().replace(" ","")}' if e.attributes == 0x20 else f'{e.name.decode().replace(" ","")}/'
			print(name,'\n')
			size = e.file_size
			fc = e.cluster_low16
			
			# cluster chain
			chain = []
			chain.append(fc)
			next_cluster = fat_tables[0][fc]
			while next_cluster != 0xffff:
				chain.append(next_cluster)
				next_cluster = fat_tables[0][next_cluster]

			# reading and printing whole clustesrs
			while len(chain) > 1:
				# calc addr
				addr = ((chain[0] - 2) * bs.sectors_per_cluster + data_sec) * bs.bytes_per_sector
				file.seek(addr)
				buf = file.read(bs.bytes_per_sector)
				
				chunks = [buf[i:i+16] for i in range(0,len(buf),16)]
				# display every chunk as a line
				for c in chunks:
					out = f'0x{addr:0>8x}: '
					for b in c:
						out += f'{b:0>2x} '
					out += f'| {c}'
					print(out)
					addr += 16
					pass
				chain.pop(0)
				pass
			# reading and printing last chunk
			addr = ((chain[0] - 2) * bs.sectors_per_cluster + data_sec) * bs.bytes_per_sector
			file.seek(addr)
			left = size % bs.bytes_per_sector if (size % bs.bytes_per_sector) else bs.bytes_per_sector
			while left > 16:
				buf = file.read(16)
				out = f'0x{addr:0>8x}: '
				for b in buf:
					out += f'{b:0>2x} '
				out += f'| {buf}'
				print(out)
				addr += 16
				left -= 16
				pass
			# reading and printing what is left (and not multiple of 16)
			buf = file.read(left)
			out = ''
			for b in buf:
				out += f'{b:0>2x} '
			out = f'0x{addr:0>8x}: {out: <48}| {buf}'
			print(out)
			break
		pass
	pass

if __name__=='__main__':
	sys.exit(main())
