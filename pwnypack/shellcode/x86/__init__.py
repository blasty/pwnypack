import six

from pwnypack.shellcode.base import BaseEnvironment
from pwnypack.shellcode.types import Register, Offset
from pwnypack.target import Target


__all__ = ['X86']


class X86(BaseEnvironment):
    """
    Environment that targets a generic, unrestricted X86 architecture.
    """

    target = Target(arch=Target.Arch.x86, bits=32)  #: Target architecture

    # 8-bit registers on X86
    AL = Register('al')  #: al register
    AH = Register('ah')  #: ah register
    BL = Register('bl')  #: bl register
    BH = Register('bh')  #: bh register
    CL = Register('cl')  #: cl register
    CH = Register('ch')  #: ch register
    DL = Register('dl')  #: dl register
    DH = Register('dh')  #: dh register

    # 16-bit registers on X86
    AX = Register('ax')  #: ax register
    BX = Register('bx')  #: bx register
    CX = Register('cx')  #: cx register
    DX = Register('dx')  #: dx register
    SI = Register('si')  #: si register
    DI = Register('di')  #: di register
    SP = Register('sp')  #: sp register
    BP = Register('bp')  #: bp register
    IP = Register('ip')  #: ip register

    # 32-bit registers on X86
    EAX = Register('eax')  #: eax register
    EBX = Register('ebx')  #: ebx register
    ECX = Register('ecx')  #: ecx register
    EDX = Register('edx')  #: edx register
    ESI = Register('esi')  #: esi register
    EDI = Register('edi')  #: edi register
    ESP = Register('esp')  #: esp register
    EBP = Register('ebp')  #: ebp register
    EIP = Register('eip')  #: eip register

    TEMP_REG = {
        32: EAX,
        16: AX,
        8: AL,
    }

    TEMP_PTR = TEMP_REG[32]
    PC = EIP
    OFFSET_REG = EBP
    STACK_REG = ESP

    REGISTER_WIDTH_MAP = {
        8: (AL, BL, CL, DL, AH, BH, CH, DH),
        16: (AX, BX, CX, DX, SI, DI, BP, SP),
        32: (EAX, EBX, ECX, EDX, ESI, EDI, EBP, ESP),
    }
    REGISTER_WIDTH = None  # Filled by __init__

    @property
    def PREAMBLE(self):
        return [
            'BITS %d' % self.target.bits,
            'global _start',
            '',
            'SECTION .text',
            '',
            '_start:',
        ]

    @property
    def GETPC(self):
        return [
            '\tcall __getpc0',
            '__getpc0:',
            '\tpop %s' % self.OFFSET_REG.name,
            '\tadd %s, __data - __getpc0' % self.OFFSET_REG.name,
            '__realstart:',
        ]

    def __init__(self):
        super(X86, self).__init__()
        self.REGISTER_WIDTH = dict([
            (reg_, width)
            for (width, regs) in self.REGISTER_WIDTH_MAP.items()
            for reg_ in regs
        ])

    def reg_push(self, reg):
        return ['push %s' % reg]

    def reg_add_reg(self, reg, add_reg):
        return ['add %s, %s' % (reg, add_reg)]

    def reg_add_imm(self, reg, value):
        if not value:
            return []
        elif value < 2:
            return ['inc %s' % reg] * value
        else:
            return ['add %s, %d' % (reg, value)]

    def reg_load_imm(self, reg, value):
        reg_width = self.REGISTER_WIDTH[reg]
        if value >= 2 ** reg_width:
            raise ValueError('%d does not fit %s' % (value, reg))

        if not value:
            return ['xor %s, %s' % (reg, reg)]
        else:
            return ['mov %s, %d' % (reg, value)]

    def reg_load_reg(self, dest_reg, src_reg):
        if dest_reg is not src_reg:
            return ['mov %s, %s' % (dest_reg, src_reg)]
        else:
            return []

    def reg_load_offset(self, reg, value):
        if value == 0:
            return self.reg_load_reg(reg, self.OFFSET_REG)
        else:
            return ['lea %s, [%s + %d]' % (reg, self.OFFSET_REG, value)]

    def reg_load_array(self, reg, value):
        temp_reg = self.TEMP_REG[self.REGISTER_WIDTH[reg]]

        code = []
        for item in reversed(value):
            if isinstance(item, (six.text_type, six.binary_type)):
                item = self.alloc_data(item)

            if isinstance(item, Offset) and not item:
                code.extend(self.reg_push(self.OFFSET_REG))
            else:
                code.extend(self.reg_load(temp_reg, item))
                code.extend(self.reg_push(temp_reg))

        code.extend(self.reg_load_reg(reg, self.STACK_REG))
        return code

    def finalize_data(self, data):
        if data:
            return ['__data:'] + \
                [
                    '\tdb ' + b','.join(hex(b) for b in six.iterbytes(datum)) + '  ; ' + repr(orig_datum)
                    for datum, (_, orig_datum) in six.iteritems(data)
                ]
        else:
            return []

    def finalize(self, code, data):
        return self.PREAMBLE + \
            (self.GETPC if data else []) + \
            ['\t%s' % line for line in code] + \
            self.finalize_data(data)