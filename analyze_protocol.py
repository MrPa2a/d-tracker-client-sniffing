from scapy.all import sniff, TCP, Raw
import sys

def read_varint(buffer, pos):
    value = 0
    shift = 0
    while True:
        if pos >= len(buffer):
            raise IndexError("Buffer too short")
        byte = buffer[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, pos
        shift += 7
        if shift >= 64:
            raise ValueError("VarInt too large")

def print_protobuf_structure(data, indent=0):
    pos = 0
    while pos < len(data):
        try:
            tag, new_pos = read_varint(data, pos)
            field_number = tag >> 3
            wire_type = tag & 7
            
            prefix = "  " * indent
            print(f"{prefix}Field {field_number} (Wire {wire_type})")
            
            if wire_type == 0: # VarInt
                val, new_pos = read_varint(data, new_pos)
                print(f"{prefix}  Value: {val}")
                pos = new_pos
            elif wire_type == 2: # Length Delimited
                length, new_pos = read_varint(data, new_pos)
                print(f"{prefix}  Length: {length}")
                sub_data = data[new_pos : new_pos + length]
                print(f"{prefix}  Data (hex): {sub_data.hex()}")
                # Recursive attempt
                if length > 0:
                    print(f"{prefix}  -> Sub-message analysis:")
                    print_protobuf_structure(sub_data, indent + 1)
                pos = new_pos + length
            elif wire_type == 1: # 64-bit
                pos = new_pos + 8
            elif wire_type == 5: # 32-bit
                pos = new_pos + 4
            else:
                print(f"{prefix}  Unknown wire type {wire_type}")
                break
        except Exception as e:
            print(f"{'  ' * indent}Error parsing: {e}")
            break

def packet_callback(packet):
    if packet.haslayer(TCP) and packet.haslayer(Raw):
        payload = packet[Raw].load
        if b'type.ankama.com/' in payload:
            idx = payload.find(b'type.ankama.com/')
            # Find end of type string (0x12 tag)
            type_end = -1
            for i in range(20):
                p = idx + 16 + i
                if p < len(payload) and payload[p] == 0x12:
                    type_end = p
                    break
            
            if type_end != -1:
                type_name = payload[idx+16 : type_end]
                print(f"\n--- Found Packet Type: {type_name} ---")
                
                # Parse body
                curr = type_end + 1
                try:
                    msg_len, curr = read_varint(payload, curr)
                    body = payload[curr : curr + msg_len]
                    print_protobuf_structure(body)
                except Exception as e:
                    print(f"Error reading body: {e}")

print("Listening for Ankama packets (Ctrl+C to stop)...")
sniff(filter="tcp port 5555", prn=packet_callback, store=0)
