#!/usr/bin/env python3
import struct, os, hashlib

MAGIC = b'ANDROID!'
AVB_MAGIC = b'AVBf'

def build_header(kernel_sz, kernel_addr, ramdisk_sz, ramdisk_addr,
                  second_sz, second_addr, tags_addr, page_sz, hdr_ver,
                  os_ver, os_pl, cmdline, name):
    buf = bytearray()
    buf += struct.pack('<8s9I',
        MAGIC, kernel_sz, kernel_addr, ramdisk_sz, ramdisk_addr,
        second_sz, second_addr, tags_addr, page_sz, hdr_ver)
    buf += struct.pack('<4I', os_ver, os_pl, 0, 0)
    buf += name.encode('ascii').ljust(128, b'\x00')[:128]
    buf += cmdline.encode('ascii').ljust(512, b'\x00')[:512]
    buf += struct.pack('<IQI', 0, 0, page_sz)
    buf += struct.pack('<IQ', 0, 0)
    return bytes(buf)

def build_avb_footer(original_image_size):
    buf = bytearray()
    buf += AVB_MAGIC
    buf += struct.pack('>II', 1, 0)
    buf += struct.pack('>Q', original_image_size)
    buf += struct.pack('>Q', original_image_size)
    buf += struct.pack('>Q', 0)
    buf += struct.pack('>Q', 0)
    buf += struct.pack('>I', 0)
    buf += b'\x00' * 4
    return bytes(buf)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--kernel', required=True)
    p.add_argument('--ramdisk', required=True)
    p.add_argument('--kernel_addr', default='0x40080000')
    p.add_argument('--ramdisk_addr', default='0x51b00000')
    p.add_argument('--second_addr', default='0x00000000')
    p.add_argument('--tags_addr', default='0x47880000')
    p.add_argument('--pagesize', type=int, default=2048)
    p.add_argument('--header_version', type=int, default=2)
    p.add_argument('--os_version', default='0x16000158')
    p.add_argument('--os_patch_level', default='0x00000000')
    p.add_argument('--cmdline', default='')
    p.add_argument('--name', default='')
    p.add_argument('--partition-size', type=int, default=0,
        help='Partition total size. MUST be > 64 bytes larger than boot image.')
    p.add_argument('--avb-footer', action='store_true',
        help='Append AVB footer at end of partition')
    p.add_argument('-o', '--output', required=True)
    p.add_argument('--id', action='store_true')
    args = p.parse_args()

    kernel = open(args.kernel, 'rb').read()
    ramdisk = open(args.ramdisk, 'rb').read()
    ka = int(args.kernel_addr, 16)
    ra = int(args.ramdisk_addr, 16)
    sa = int(args.second_addr, 16)
    ta = int(args.tags_addr, 16)
    ps = args.pagesize
    hv = args.header_version
    os_ver = int(args.os_version, 16)
    os_pl = int(args.os_patch_level, 16)

    hdr = build_header(len(kernel), ka, len(ramdisk), ra,
                       0, sa, ta, ps, hv,
                       os_ver, os_pl, args.cmdline, args.name)
    hdr_padded = hdr.ljust(ps, b'\x00')[:ps]

    with open(args.output, 'wb') as f:
        f.write(hdr_padded)
        f.write(kernel)
        pad = (ps - (len(kernel) % ps)) % ps
        if pad:
            f.write(b'\x00' * pad)
        f.write(ramdisk)
        pad = (ps - (len(ramdisk) % ps)) % ps
        if pad:
            f.write(b'\x00' * pad)

    boot_size = os.path.getsize(args.output)
    part_size = args.partition_size

    if args.id:
        s = hashlib.sha1()
        s.update(hdr)
        for d in (kernel, ramdisk):
            s.update(d)
            s.update(struct.pack('<I', len(d)))
        print('img_id: ' + s.hexdigest())

    if args.avb_footer:
        if part_size <= 0:
            part_size = boot_size + 64
        if part_size <= boot_size + 63:
            print(f'error: partition_size ({part_size}) too small for boot image ({boot_size}) + footer (64)',
                  file=__import__('sys').stderr)
            __import__('sys').exit(1)

        footer_off = part_size - 64
        with open(args.output, 'ab') as f:
            if f.tell() < footer_off:
                f.write(b'\x00' * (footer_off - f.tell()))
            f.write(build_avb_footer(boot_size))
        print(f'avb_footer: original_image_size={boot_size}')

    if part_size > 0:
        with open(args.output, 'ab') as f:
            if f.tell() < part_size:
                f.write(b'\x00' * (part_size - f.tell()))

if __name__ == '__main__':
    main()
