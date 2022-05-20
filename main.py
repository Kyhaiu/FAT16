import math
import sys
import argparse
from typing import List

def main():
  parser = argparse.ArgumentParser(description='A simple fat16 image summary tool.')
  parser.add_argument('img',nargs='?',default='images/fat16_1sectorpercluster.img',help='path to the image file (uncompressed .img or .iso)')
  args = parser.parse_args()
  
  file_path = args.img

  try:
    file = open(file_path, "rb")
  except:
    print(f'Error: can not open file {file_path}.')
    return -1

  file_strings = []
  file_strings = file.readlines()

  file_hex: List[str] = []

  print('Reading Boot Record\n')

  for row in file_strings:
    for column in row:
      # transforma o numero em hexadecimal e remove o '0x'
      file_hex.append(format(column, '#04x')[2:])
  
  
  bytes_per_sector = int(str('0x' + file_hex[12] + file_hex[11]), 16)
  """
    ### Offset(decimal) = 11
    ---
    ### Offset(hex) = 0x0B
    ---
    The number of Bytes per sector (remember, all numbers are in the little-endian format).
  """
  sectors_per_cluster = int(str('0x' + file_hex[13]), 16)
  """
    ### Offset(decimal) = 13
    ---
    ### Offset(hex) = 0x0D
    ---
    Number of sectors per cluster.
  """
  reserved_sectors = int(str('0x' + file_hex[15] + file_hex[14]), 16)
  """
    ### Offset(decimal) = 14
    ---
    ### Offset(hex) = 0x0E
    ---
    Number of reserved sectors. The boot record sectors are included in this value.
  """
  table_count = int(str('0x' + file_hex[16]), 16)
  """
    ### Offset(decimal) = 16
    ---
    ### Offset(hex) = 0x10
    ---
    Number of File Allocation Tables (FAT's) on the storage media. Often this value is 2.
  """
  root_entry_count = int(str('0x' + file_hex[18] + file_hex[17]), 16)
  """
    ### Offset(decimal) = 17
    ---
    ### Offset(hex) = 0x11
    ---
    Number of root directory entries (must be set so that the root directory occupies entire sectors).
  """
  total_sectors_32 = int(str('0x' + file_hex[20] + file_hex[19]), 16)
  """
    ### Offset(decimal) = 19
    ---
    ### Offset(hex) = 0x13
    ---
    The total sectors in the logical volume. If this value is 0, it means there are more than 65535 sectors in the volume, and the actual count is stored in the Large Sector Count entry at 0x20.
  """
  sectors_per_fat = int(str('0x' + file_hex[22]), 16)
  """
    ### Offset(decimal) = 22
    ---
    ### Offset(hex) = 0x16
    ---
    Number of sectors per FAT. FAT12/FAT16 only.
  """
  fat_1_sector = 1
  """
    Number (sector) that indicates the sector that starts the FAT 1
  """
  fat_2_sector = (fat_1_sector + sectors_per_fat)
  print(fat_1_sector, fat_2_sector, sectors_per_fat)
  """
    Number (sector) that indicates the sector that starts the FAT 2
  """
  root_dir_sector = (root_entry_count * 32) / bytes_per_sector
  """
    Number (sector) that indicates the sector that starts the Root Dir
  """

  fat_1_address = (fat_1_sector * bytes_per_sector * sectors_per_cluster)
  """
    Address to FAT 1
  """
  fat_2_address = (fat_2_sector * bytes_per_sector * sectors_per_cluster)
  """
    Address to FAT 2
  """
  root_dir_address = (reserved_sectors + sectors_per_fat * table_count) * bytes_per_sector
  """
    Address to Root Dir
  """

  entries_left = root_entry_count
  i = root_dir_address
  root_entries = []
  """
    [0] - Índice que começa o diretório
    [1] - Nome
    [2] - Extensão
    [3] - Tipo
    [4] - Tamanho
    [5] - Primeiro Cluster
  """
  while entries_left > 0:
    entries_left -= 1

    if((file_hex[i + 11] == '10' or file_hex[i + 11] == '20') and file_hex[i] != 'e5'):
      # Obtém os bytes hexadecimal do nome
      name_hex = file_hex[i:i+8]
      name_str = ''
      # Converte os bytes hexadecimal em uma string
      for j in name_hex:
          name_str += chr(int('0x' + j, 16))

      # Obtém os bytes hexadecimal da extensão
      ext_hex = file_hex[i+8:i+11]
      ext_str = ''
      # Converte os bytes hexadecimal em uma string
      for j in ext_hex:
        ext_str += chr(int('0x' + j, 16))

      # Atributo do arquivo
      # READ_ONLY=0x01 HIDDEN=0x02 SYSTEM=0x04 VOLUME_ID=0x08 DIRECTORY=0x10 ARCHIVE=0x20 LFN=READ_ONLY|HIDDEN|SYSTEM|VOLUME_ID 
      tp = '0x' + file_hex[i+11]
      
      cluster_high16 = int('0x' + file_hex[i+21] + file_hex[i+20], 16)

      # Obtém os bytes hexadecimal do tamanho
      length_hex = file_hex[i+28: i+32]
      length_hex.reverse()
      aux = ''
      # Concatena os bytes hexadecimais em uma única string
      for j in length_hex:
        aux += j
      
      # Converte a string hexadecimal em um inteiro
      length_int = int('0x' + aux, 16)

      # Obtém o endereço do primeiro cluster (little-endian) e converte para inteiro base 10
      cluster_low16 = int('0x' + file_hex[i+27] + file_hex[i+26], 16)

      root_entries.append({
        'index':i, 
        'name':name_str, 
        'extension':ext_str,
        'type':tp,
        'size':length_int, 
        'low bits':cluster_low16,
        'high bits':cluster_high16
      })
      pass
    i += 32
    pass

  print(f'{"Reserved sectors:":<25} {reserved_sectors:>5}')
  print(f'{"Bytes per sector:":<25} {bytes_per_sector:>5}')
  print(f'{"Sectors per cluster:":<25} {sectors_per_cluster:>5}')
  print(f'{"FAT tables:":<25} {table_count:>5}')
  print(f'{"FAT table size:":<25} {sectors_per_fat:>5}')
  print(f'{"Root directory entries:":<25} {root_entry_count:>5}')
  print(f'{"Total sectors:":<25} {total_sectors_32}')

  print('\nAddresses\n')

  print('Boot Record at: 0x0')

  for i in range(0, table_count):
    temp = reserved_sectors + (i * sectors_per_fat)
    print(f'FAT {i+1} at: 0x{temp * bytes_per_sector:0>8x}, sector {temp}')

  root_sec = reserved_sectors + (table_count * sectors_per_fat)
  root_addr =  root_sec * bytes_per_sector
  print(f'Root directory at: 0x{root_addr:0>8x}, sector {root_sec}')

  data_sec = root_sec + ((root_entry_count * 32) // bytes_per_sector)
  data_addr = data_sec * bytes_per_sector
  print(f'Data at: 0x{data_addr:0>8x}, sector {data_sec}')

  print("\nRoot Directory\n")

  for e in root_entries:
    name:str = e['name']
    ext:str = e['extension']
    
    fc:int = e['low bits']
    attr:str = e['type']
    addr:int = ((fc - 2) * sectors_per_cluster + data_sec) * bytes_per_sector
    size_formatted:int = f"{e['size']} Bytes" if attr == '0x20' else ''
    name_formatted:str = f'{name.replace(" ", "")}.{ext.replace(" ", "")}' if e['type'] == '0x20' else f'{name.replace(" ", "")}/'
    out = f'[{attr}] {name_formatted: <12} at FAT[{fc:4}] (0x{addr:0>8x}) {size_formatted}'
    print(out)

  print('\nContents of a file\n')

  for e in root_entries:
    if e['type'] == '0x20':
      name = e['name']
      ext = e['extension']
      name_formatted = f'{name.replace(" ","")}.{ext.replace(" ","")}' if e['type'] == '0x20' else f'{name.replace(" ","")}/'
      print(name,'\n')
      size = e['size']
      # first cluster
      fc = e['low bits']
      total_cluster_file = math.ceil(size / bytes_per_sector)


if __name__ == '__main__':
  main()
