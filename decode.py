def convert_string_to_utf32_chars(input_string):
    # Step 1: Convert each character to an 8-bit binary representation
    binary_string = ''.join(f'{ord(char):08b}' for char in input_string)
    
    # Step 2: Split binary string into 32-bit chunks, padding with zeros if necessary
    chunks = [binary_string[i:i+32] for i in range(0, len(binary_string), 32)]
    if len(chunks[-1]) < 32:
        chunks[-1] = chunks[-1].ljust(32, '0')
    
    # Step 3: Convert each 32-bit chunk to decimal and then to a Unicode character (handle out-of-range values)
    utf32_chars = []
    for chunk in chunks:
        decimal_value = int(chunk, 2)
        if decimal_value <= 0x10FFFF:
            utf32_chars.append(chr(decimal_value))
        else:
            utf32_chars.append('\uFFFD')  # Use replacement character for out-of-range values
    
    # Join the characters into a final string
    result_string = ''.join(utf32_chars)
    return result_string

# Example usage
input_string = "AgAD1wgAAteaUFQ"
output = convert_string_to_utf32_chars(input_string)
print(output)
