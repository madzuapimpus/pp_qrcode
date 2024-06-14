#!/usr/bin/env python3

import argparse
import json

# Alphanumeric character set for QR code. It contains 45 characters.
ALPHANUMERIC_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"

BLANK_FIELD = '░░'
ZIGZAG_FIELD = '▓▓'
WHITE_BLOCK = '  '
BLACK_BLOCK = '██'

VERBOSITY = 0

class data_encoder:
    def __init__(self):
        self.bit_string = ''

    def encode(self, data, mode):
        if mode == 'numeric':
            return self.encode_numeric(data)
        elif mode == 'alphanumeric':
            return self.encode_alphanumeric(data)
        elif mode == 'byte':
            return self.encode_byte(data)
        elif mode == 'kanji':
            return self.encode_kanji(data)
        else:
            raise ValueError(f'Invalid mode: {mode}')

    def encode_alphanumeric(self, data):
        i = 0
        while i < len(data):
            if i + 2 <= len(data):
                group = data[i:i+2]
                i += 2
                value1 = ALPHANUMERIC_CHARS.index(group[0])
                value2 = ALPHANUMERIC_CHARS.index(group[1])
                self.bit_string += format(value1 * 45 + value2, '011b')
            else:
                group = data[i]
                i += 1
                self.bit_string += format(ALPHANUMERIC_CHARS.index(group), '06b')

        return self.bit_string

    def encode_byte(self, data):
        for char in data:
            byte = ord(char)
            self.bit_string += format(byte, '08b')

        return self.bit_string

    def encode_kanji(self, data):
        for char in data:
            sjis_bytes = char.encode('shift_jis')
            byte1, byte2 = sjis_bytes

            if byte1 <= 0x9F:
                adjusted = ((byte1 - 0x81) * 0xC0) + (byte2 - 0x40)
            else:
                adjusted = ((byte1 - 0xC1) * 0xC0) + (byte2 - 0x40)

            self.bit_string += format(adjusted, '013b')

        return self.bit_string

    def encode_numeric(self, data):
        i = 0
        while i < len(data):
            if i + 3 <= len(data):
                group = data[i:i+3]
                i += 3
                self.bit_string += format(int(group), '010b')
            elif i + 2 <= len(data):
                group = data[i:i+2]
                i += 2
                self.bit_string += format(int(group), '07b')
            else:
                group = data[i]
                i += 1
                self.bit_string += format(int(group), '04b')

        return self.bit_string

def find_mode(data):
    mode = {
        'numeric': True,
        'alphanumeric': True,
        'kanji': True,
        'byte': True
    }

    charno = 0
    vprint(f'Character codes for input data:', 2)

    for char in data:
        charcode = ord(char)
        charmode = {
            'numeric': True,
            'alphanumeric': True,
            'kanji': True,
            'byte': True
        }

        if not char.isdigit():
            charmode['numeric'] = mode['numeric'] = False

        if char not in ALPHANUMERIC_CHARS:
            charmode['alphanumeric'] = mode['alphanumeric'] = False

        sjis_bytes = char.encode('shift_jis')
        if len(sjis_bytes) != 2:
            charmode['kanji'] = mode['kanji'] = False
        else:
            byte1, byte2 = sjis_bytes
            sjis_value = (byte1 << 8) | byte2

            if not ((0x8140 <= sjis_value <= 0x9FFC) or
                    (0xE040 <= sjis_value <= 0xEBBF)):
                charmode['kanji'] = mode['kanji'] = False

        for key, value in charmode.items():
            if value:
                vprint(f'{charno}. {char}: U+{charcode:04X} ({key})', 2)
                break

        charno += 1

    for key, value in mode.items():
        if value:
            return key

def main():
    data = input('Please enter a string: ')
    ecc = input('Please enter the error correction level (L, M, Q, H): ')
    if ecc not in {'L', 'M', 'Q', 'H'}:
        raise ValueError('Invalid error correction level')

    # Step 0: Determine the mode of the input data
    # As in https://www.thonky.com/qr-code-tutorial/data-encoding (Step 3: Add the Mode Indicator)
    mode = find_mode(data)
    if mode == 'numeric':
        mode_indicator = '0001'
    elif mode == 'alphanumeric':
        mode_indicator = '0010'
    elif mode == 'byte':
        mode_indicator = '0100'
    elif mode == 'kanji':
        mode_indicator = '1000'
    else:
        raise ValueError(f'Invalid mode: {mode}')

    vprint(f'Mode: {mode} ({mode_indicator})')

    # Step 1: Encode the data
    encoded_data = data_encoder().encode(data, mode)
    vprint(f'Encoded data: {encoded_data}')

    bit_size = len(encoded_data)
    vprint(f'Number of bits: {bit_size}')
    data_size = len(data)
    vprint(f'Data size: {data_size}')

    # Step 2: Determine the version number
    version = 1
    version_bits = None

    with open('thonky_qr_version.json', 'r') as json_file:
        thonky_qr_version = json.load(json_file)

    for version, capacity in thonky_qr_version.items():
        if capacity[ecc][mode] >= data_size:
            break
    vprint(f'Version: {version}')

    # Step 3: Determine the character count indicator and making codewords
    with open('thonky_qr_bit_modes.json', 'r') as json_file:
        thonky_qr_bit_modes = json.load(json_file)

    for version_range in thonky_qr_bit_modes:
        min_version, max_version = version_range.split('-')
        if min_version <= version <= max_version:
            version_bits = thonky_qr_bit_modes[version_range][mode]
            break

    if version_bits is None:
        raise ValueError(f'Version bits not found for version {version}')

    vprint(f'Version bits: {version_bits}')

    char_count_indicator = bin(data_size)[2:].zfill(version_bits)
    vprint(f'Character count indicator: {char_count_indicator}')

    with open('thonky_qr_ec_codewords.json', 'r') as json_file:
        thonky_qr_ec_codewords = json.load(json_file)

    data_codewords = mode_indicator + char_count_indicator + encoded_data
    vprint(f'Current codewords bits count: {len(data_codewords)}')

    required_codewords_size = thonky_qr_ec_codewords[version][ecc]['data_codewords'] * 8
    vprint(f'Required codewords bits count: {required_codewords_size}')

    terminator = ''
    if required_codewords_size > len(data_codewords):
        if required_codewords_size - len(data_codewords) >= 4:
            terminator = '0000'
        else:
            terminator = '0' * (required_codewords_size - len(data_codewords))

    if terminator:
        data_codewords = data_codewords + terminator
        vprint(f'Terminator: {terminator}')
        vprint(f'Current codewords bits with terminator count: {len(data_codewords)}')

    pad_bits = ''
    filling_bits = 0b11101100

    if len(data_codewords) % 8:
        pad_bits = '0' * (8 - len(data_codewords) % 8)
        data_codewords = data_codewords + pad_bits

    while required_codewords_size > len(data_codewords):
        pad_bits = pad_bits + format(filling_bits, '08b')
        data_codewords = data_codewords + format(filling_bits, '08b')
        filling_bits = filling_bits ^ 0b11111101

    if pad_bits:
        vprint(f'Pad bits: {pad_bits}')
        vprint(f'Current codewords bits with padding count: {len(data_codewords)}')

    vprint(f'Current codewords: {data_codewords}')
    vprint(f'Current codewords as hex: {" ".join(format(int(data_codewords[i:i + 8], 2), "02X") for i in range(0, len(data_codewords), 8))}')
    def reed_solomon_generator_poly(nsym):
        g = [1]
        for i in range(nsym):
            g = gf_poly_mul(g, [1, gf_pow(2, i)])
        return g

    def gf_poly_mul(p, q):
        r = [0] * (len(p) + len(q) - 1)
        for j in range(len(q)):
            for i in range(len(p)):
                r[i + j] ^= gf_mul(p[i], q[j])
        return r

    def gf_mul(x, y):
        if x == 0 or y == 0:
            return 0
        return GF_EXP[(GF_LOG[x] + GF_LOG[y]) % 255]

    def gf_pow(x, power):
        return GF_EXP[(GF_LOG[x] * power) % 255]

    def gf_poly_div(dividend, divisor):
        result = list(dividend)
        for i in range(len(dividend) - len(divisor) + 1):
            coef = result[i]
            if coef != 0:
                for j in range(1, len(divisor)):
                    if divisor[j] != 0:
                        result[i + j] ^= gf_mul(divisor[j], coef)
        separator = -(len(divisor) - 1)
        return result[:separator], result[separator:]

    GF_EXP = [1] * 512
    GF_LOG = [0] * 256
    x = 1
    for i in range(1, 256):
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
        GF_EXP[i] = x
        GF_LOG[x] = i
    for i in range(256, 512):
        GF_EXP[i] = GF_EXP[i - 255]

    def calculate_rs_codewords(data_codewords, nsym):
        gen = reed_solomon_generator_poly(nsym)
        _, remainder = gf_poly_div(data_codewords + [0] * nsym, gen)
        return remainder

    data_codewords_int = [int(data_codewords[i:i+8], 2) for i in range(0, len(data_codewords), 8)]
    nsym = thonky_qr_ec_codewords[version][ecc]['ec_codewords_per_block']
    rs_codewords = calculate_rs_codewords(data_codewords_int, nsym)
    vprint(f'Reed-Solomon error correction codewords: {rs_codewords}')
    vprint(f'Reed-Solomon error correction codewords as hex: {" ".join(format(byte, "02X") for byte in rs_codewords)}')

    final_codewords = data_codewords_int + rs_codewords
    binary_output = ''.join(format(byte, '08b') for byte in final_codewords)
    vprint(f'Final codewords: {binary_output}')
    vprint(f'Final codewords length: {len(binary_output)}')

    qr_code_size = 21 + (int(version) - 1) * 4
    vprint(f'QR code size: {qr_code_size}x{qr_code_size}')

    qr_code = [[ BLANK_FIELD for _ in range(qr_code_size)] for _ in range(qr_code_size)]

    # Fixed patterns
    # Draw the horizontal and vertical timing patterns (on both row 6 and column 6, counting from 0 starting at the top left corner)
    for i in range(qr_code_size):
        qr_code[6][i] = WHITE_BLOCK if i % 2 else BLACK_BLOCK
        qr_code[i][6] = WHITE_BLOCK if i % 2 else BLACK_BLOCK

    vprint('\nFixed patterns:', 2)
    for row in qr_code:
        vprint(''.join(row), 2)

    # Add finder patterns
    finder_pattern = [
        [BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, WHITE_BLOCK],
        [BLACK_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, BLACK_BLOCK, WHITE_BLOCK],
        [BLACK_BLOCK, WHITE_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, WHITE_BLOCK, BLACK_BLOCK, WHITE_BLOCK],
        [BLACK_BLOCK, WHITE_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, WHITE_BLOCK, BLACK_BLOCK, WHITE_BLOCK],
        [BLACK_BLOCK, WHITE_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, WHITE_BLOCK, BLACK_BLOCK, WHITE_BLOCK],
        [BLACK_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, BLACK_BLOCK, WHITE_BLOCK],
        [BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, WHITE_BLOCK],
        [WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK]
    ]

    for i in range(8):
        for j in range(8):
            qr_code[i][j] = finder_pattern[i][j]
            qr_code[i][qr_code_size - 8 + j] = finder_pattern[i][7-j]
            qr_code[qr_code_size - 8 + i][j] = finder_pattern[7-i][j]

    vprint('\nAdded finder patterns:', 2)
    for row in qr_code:
        vprint(''.join(row), 2)

    # Add aligment patterns
    with open('thonky_qr_aligment_pattern_locations.json', 'r') as json_file:
        thonky_qr_aligment_pattern_locations = json.load(json_file)

    aligment_pattern_location = thonky_qr_aligment_pattern_locations[version]
    alignment_pattern = [
        [BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK],
        [BLACK_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, BLACK_BLOCK],
        [BLACK_BLOCK, WHITE_BLOCK, BLACK_BLOCK, WHITE_BLOCK, BLACK_BLOCK],
        [BLACK_BLOCK, WHITE_BLOCK, WHITE_BLOCK, WHITE_BLOCK, BLACK_BLOCK],
        [BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK, BLACK_BLOCK]
    ]

    for x in aligment_pattern_location:
        for y in aligment_pattern_location:
            if (x == 6 and y == 6) or (x == 6 and y == qr_code_size - 7) or (x == qr_code_size - 7 and y == 6):
                continue
            for i in range(5):
                for j in range(5):
                    qr_code[x - 2 + i][y - 2 + j] = alignment_pattern[i][j]

    vprint('\nAdded aligment patterns:', 2)
    for row in qr_code:
        vprint(''.join(row), 2)

    # Add temporary dummy format bits
    for i in range(9):
        if i != 6:
            qr_code[8][i] = WHITE_BLOCK
            qr_code[i][8] = WHITE_BLOCK

    for i in range(8):
        qr_code[qr_code_size - 8 + i][8] = WHITE_BLOCK if i else BLACK_BLOCK
        qr_code[8][qr_code_size - 8 + i] = WHITE_BLOCK

    vprint('\nAdded temporary dummy format bits:', 2)
    for row in qr_code:
        vprint(''.join(row), 2)

    # Count the number of writeable fields
    qr_data_fields = 0
    for row in qr_code:
        qr_data_fields += row.count(BLANK_FIELD)

    vprint('\n', 2)
    vprint(f'Number of writeable fields: {qr_data_fields}')

    # Compute zigzag bit pattern
    # It should start from the bottom right corner and consider only unmodified fields with BLANK_FIELD.
    # First it should try the field to the left, then the field diagonally to the upper right.
    # If there is no more diagonally upper-right field, it should go up one row to the left and try the zigzagging down, first trying the field to the left, then diagonally to the lower right.
    writeable_columns = [i for i in range(qr_code_size) if i != 6]
    writeable_column_pairs = []
    for i in range(len(writeable_columns) - 1, 0, -2):
        writeable_column_pairs.append((writeable_columns[i-1], writeable_columns[i]))

    vprint(f'Writeable column pairs: {writeable_column_pairs}', 2)

    zigzag_sequence = []

    goup = True
    for columns in writeable_column_pairs:
        pair_column = 1

        if goup:
            y = qr_code_size - 1
            while y >= 0:
                x = columns[pair_column]
                if qr_code[y][x] == BLANK_FIELD:
                    zigzag_sequence.append((y, x))
                    qr_code[y][x] = ZIGZAG_FIELD
                    # vprint(f'Coordinates: {x}, {y}', 2)
                    # for row in qr_code:
                    #     vprint(''.join(row), 2)
                    # vprint('\n', 2)

                if pair_column:
                    pair_column = 0
                else:
                    pair_column = 1
                    y -= 1
        else:
            y = 0
            while y < qr_code_size:
                x = columns[pair_column]
                if qr_code[y][x] == BLANK_FIELD:
                    zigzag_sequence.append((y, x))
                    qr_code[y][x] = ZIGZAG_FIELD
                    # vprint(f'Coordinates: {x}, {y}', 2)
                    # for row in qr_code:
                    #     vprint(''.join(row), 2)
                    # vprint('\n', 2)

                if pair_column:
                    pair_column = 0
                else:
                    pair_column = 1
                    y += 1

        goup = not goup

    vprint(f'Zigzag sequence: {zigzag_sequence}', 2)

    # Write the data codewords to the zigzag sequence
    for i, (y, x) in enumerate(zigzag_sequence):
        if i <= len(binary_output) - 1:
            qr_code[y][x] = BLACK_BLOCK if binary_output[i] == '1' else WHITE_BLOCK
        else:
            qr_code[y][x] = WHITE_BLOCK

    vprint('\nAdded data codewords:', 2)
    for row in qr_code:
        vprint(''.join(row), 2)

    # Apply mask 0 pattern
    
    for i, (x, y) in enumerate(zigzag_sequence):
        if (x + y) % 2 == 0:
            qr_code[x][y] = WHITE_BLOCK if qr_code[x][y] == BLACK_BLOCK else BLACK_BLOCK

    vprint('\nApplied mask pattern:', 2)
    for row in qr_code:
        vprint(''.join(row), 2)

    # Draw the actual format bits (adjacent to the finders)
    format_bits = 0b00000

    if ecc == 'L':
        format_bits = 0b01000
    elif ecc == 'M':
        format_bits = 0b00000
    elif ecc == 'Q':
        format_bits = 0b11000
    elif ecc == 'H':
        format_bits = 0b10000

    format_info = format_bits << 10
    generator = 0b10100110111

    while format_info.bit_length() > 10:
        shift = format_info.bit_length() - 11
        format_info ^= generator << shift

    format_bits = format_bits << 10 | format_info
    format_bits ^= 0b101010000010010

    format_bits_str = bin(format_bits)[2:].zfill(15)

    vprint(f'Format bits: {format_bits_str}')

    

    format_positions = [
        [(0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (7, 8), (8, 8), (8, 7), (8, 5), (8, 4), (8, 3), (8, 2), (8, 1), (8, 0)],
        [(8, qr_code_size - 1), (8, qr_code_size - 2), (8, qr_code_size - 3), (8, qr_code_size - 4), (8, qr_code_size - 5), (8, qr_code_size - 6), (8, qr_code_size - 7), (qr_code_size - 9, 8), (qr_code_size - 8, 8), (qr_code_size - 7, 8), (qr_code_size - 6, 8), (qr_code_size - 5, 8), (qr_code_size - 4, 8), (qr_code_size - 3, 8), (qr_code_size - 2, 8), (qr_code_size - 1, 8)]
    ]

    pos = 0
    for pos1, pos2 in zip(format_positions[0], format_positions[1]):
        qr_code[pos1[1]][pos1[0]] = BLACK_BLOCK if format_bits_str[pos] == '1' else WHITE_BLOCK
        qr_code[pos2[1]][pos2[0]] = BLACK_BLOCK if format_bits_str[pos] == '1' else WHITE_BLOCK
        pos += 1

    vprint('\n')
    for row in qr_code:
        print(''.join(row))

def vprint(message, verbosity_level=1):
    if VERBOSITY >= verbosity_level:
        print(message)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate a QR code in the terminal.')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Increase output verbosity')
    args = parser.parse_args()

    VERBOSITY = args.verbose

    main()
