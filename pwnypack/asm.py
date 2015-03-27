from __future__ import print_function
import argparse
import subprocess
import sys
import capstone
import pwnypack.target
import pwnypack.main
import pwnypack.codec
import tempfile
import os


__all__ = [
    'asm',
    'disasm',
]


def asm(code, addr=0, target=None):
    if target is None:
        target = pwnypack.target.target

    if target.arch is not pwnypack.target.Target.Arch.x86:
        raise NotImplementedError('Only x86 is currently supported.')

    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(('bits %d\norg %d\n%s' % (target.bits.value, addr, code)).encode('utf-8'))
    tmp.close()

    try:
        p = subprocess.Popen(
            [
                'nasm',
                '-o',
                '/dev/stdout',
                '-f',
                'bin',
                tmp.name,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = p.communicate()
        if p.returncode:
            raise SyntaxError(stderr.decode('utf-8'))
        return stdout
    finally:
        os.unlink(tmp.name)


def disasm(code, addr=0, target=None):
    if target is None:
        target = pwnypack.target.target

    if target.arch == pwnypack.target.Target.Arch.x86:
        if target.bits is pwnypack.target.Target.Bits.bits_32:
            md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        else:
            md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    else:
        raise NotImplementedError('Only x86 and x86_64 architectures are currently supported')

    statements = []
    total_size = 0
    for (_, size, mnemonic, op_str) in md.disasm_lite(code, addr):
        statements.append((mnemonic + ' ' + op_str).strip())
        total_size += size

    if total_size != len(code):
        raise SyntaxError('Failed to disassemble.')

    return statements


@pwnypack.main.register('asm')
def asm_app(parser, cmd, args):  # pragma: no cover
    """
    Assemble code from commandline or stdin.

    Please not that all semi-colons are replaced with carriage returns
    unless source is read from stdin.
    """

    parser.add_argument('source', help='the code to assemble, read from stdin if omitted', nargs='?')
    pwnypack.main.add_target_arguments(parser)
    parser.add_argument(
        '--address', '-o',
        type=lambda v: int(v, 0),
        default=0,
        help='the address where the code is expected to run',
    )

    args = parser.parse_args(args)
    target = pwnypack.main.target_from_arguments(args)
    if args.source is None:
        args.source = sys.stdin.read()
    else:
        args.source = args.source.replace(';', '\n')

    return asm(
        args.source,
        target=target,
    )


@pwnypack.main.register('disasm')
def asm_app(_parser, cmd, args):  # pragma: no cover
    """
    Disassemble code from commandline or stdin.
    """

    parser = argparse.ArgumentParser(
        prog=_parser.prog,
        description=_parser.description,
    )
    parser.add_argument('code', help='the code to disassemble, read from stdin if omitted', nargs='?')
    pwnypack.main.add_target_arguments(parser)
    parser.add_argument(
        '--address', '-o',
        type=lambda v: int(v, 0),
        default=0,
        help='the address of the disassembled code',
    )
    parser.add_argument(
        '--format', '-f',
        choices=['hex', 'bin'],
        help='the input format (defaults to hex for commandline, bin for stdin)',
    )

    args = parser.parse_args(args)
    target = pwnypack.main.target_from_arguments(args)

    if args.format is None:
        if args.code is None:
            args.format = 'bin'
        else:
            args.format = 'hex'

    if args.format == 'hex':
        code = pwnypack.codec.dehex(pwnypack.main.string_value_or_stdin(args.code))
    else:
        code = pwnypack.main.binary_value_or_stdin(args.code)

    try:
        statements = disasm(code, args.address, target=target)
    except SyntaxError:
        print('Failed to disassemble.', file=sys.stderr)
        sys.exit(1)

    print('\n'.join(statements))
