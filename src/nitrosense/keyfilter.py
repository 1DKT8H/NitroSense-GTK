"""Kernel-side filter: ordinary key presses/scancodes never reach this reader."""
import ctypes
import fcntl
import struct

APPLICATION_KEYS = (148, 149, 202, 203, 183, 425)
EVIOCSMASK = 0x40104593  # _IOW('E', 0x93, struct input_mask), Linux UAPI


def mask_for(codes):
    result = bytearray(96)  # KEY_CNT == 768
    for code in codes:
        result[code // 8] |= 1 << (code % 8)
    return bytes(result)


def restrict(fd):
    for event_type in range(32):
        codes = APPLICATION_KEYS if event_type == 1 else ((0,) if event_type == 0 else ())
        memory = ctypes.create_string_buffer(mask_for(codes))
        argument = struct.pack("=IIQ", event_type, 96, ctypes.addressof(memory))
        fcntl.ioctl(fd, EVIOCSMASK, argument)
