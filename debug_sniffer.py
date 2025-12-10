from scapy.all import sniff, TCP, IP, Raw
import sys

def packet_callback(packet):
    if not packet.haslayer(TCP):
        return
        
    src_port = packet[TCP].sport
    
    if src_port == 5555 and packet.haslayer(Raw):
        payload = packet[Raw].load
        print(f"Packet from 5555, len: {len(payload)}")
        
        search_pattern = b'type.ankama.com/iqb'
        idx = payload.find(search_pattern)
        
        if idx != -1:
            print(f"FOUND MAGIC STRING at index {idx}")
            # Print some bytes around it
            start = max(0, idx - 20)
            end = min(len(payload), idx + len(search_pattern) + 50)
            print(f"Context: {payload[start:end]}")
        else:
            # Check for other potential patterns or just print a sample
            if b'type.ankama.com' in payload:
                 print(f"Found 'type.ankama.com' but not full string. Payload: {payload[:100]}...")

print("Starting debug sniffer on port 5555...")
sniff(filter="tcp port 5555", prn=packet_callback, store=0, count=50)
print("Finished.")
