import threading
import time
from scapy.all import sniff, TCP, IP, Raw
from core.packet_parser import parse_iqb_packet, parse_jbo_packet, parse_jcg_packet, read_varint
from core.game_data import game_data
from core.anomaly_filter import AnomalyFilter
from utils.config import config_manager

class SnifferService(threading.Thread):
    def __init__(self, callback=None, on_error=None, on_unknown_item=None):
        super().__init__()
        self.callback = callback
        self.on_error = on_error
        self.on_unknown_item = on_unknown_item
        self.running = False
        self.dump_packets = False # Enable packet dumping for debug
        self.filter = AnomalyFilter(
            min_price=config_manager.get("min_price_threshold", 0),
            max_price=config_manager.get("max_price_threshold", 1000000000)
        )
        self.daemon = True # Kill thread when main app closes

    def run(self):
        self.running = True
        print("Sniffer thread started.")
        try:
            # Load game data if not loaded
            if not game_data.loaded:
                game_data.load()
                
            sniff(prn=self.packet_callback, store=0, stop_filter=lambda x: not self.running)
        except Exception as e:
            error_msg = f"Sniffer error: {e}"
            print(error_msg)
            self.running = False
            if self.on_error:
                self.on_error(str(e))

    def stop(self):
        self.running = False

    def packet_callback(self, packet):
        if not self.running:
            return

        if not packet.haslayer(TCP):
            return
            
        src_port = packet[TCP].sport
        
        # Only process server traffic (5555)
        if src_port == 5555 and packet.haslayer(Raw):
            payload = packet[Raw].load
            
            if self.dump_packets:
                with open("packet_dump.bin", "ab") as f:
                    f.write(payload)
            
            # Search for 'type.ankama.com/'
            prefix = b'type.ankama.com/'
            idx = payload.find(prefix)
            
            if idx != -1:
                try:
                    # Determine type suffix
                    # Heuristic: Scan for 0x12 (Tag for field 2) within reasonable distance
                    type_end = -1
                    for i in range(10):
                        check_pos = idx + len(prefix) + i
                        if check_pos < len(payload) and payload[check_pos] == 0x12:
                            type_end = check_pos
                            break
                    
                    if type_end != -1:
                        type_suffix = payload[idx + len(prefix) : type_end]
                        # print(f"[Sniffer] Detected type: {type_suffix}")
                        
                        curr = type_end + 1 # Skip Tag 0x12
                        msg_len, curr = read_varint(payload, curr)
                        
                        msg_payload = payload[curr : curr + msg_len]
                        
                        gid = 0
                        prices = []
                        
                        if type_suffix == b'iqb':
                            gid, prices = parse_iqb_packet(msg_payload)
                        elif type_suffix == b'jbo':
                            gid, prices = parse_jbo_packet(msg_payload)
                        elif type_suffix == b'jcg':
                            gid, prices = parse_jcg_packet(msg_payload)
                        else:
                            # Try all just in case
                            gid, prices = parse_jcg_packet(msg_payload)
                            if not gid or not prices:
                                gid, prices = parse_jbo_packet(msg_payload)
                            if not gid or not prices:
                                gid, prices = parse_iqb_packet(msg_payload)
                        
                        if gid and prices:
                            name = game_data.get_item_name(gid)
                            if not name:
                                if self.on_unknown_item:
                                    # Ask UI to resolve name (blocking call ideally)
                                    name = self.on_unknown_item(gid)
                                
                                if not name:
                                    print(f"[Sniffer] Item {gid} ignored (no name provided).")
                                    return
                                
                            # Filter anomalies
                            filtered_prices, average = self.filter.filter_prices(prices)
                            
                            if average > 0:
                                category = game_data.get_item_category(gid)
                                if not category:
                                    category = "Catégorie Inconnue"

                                observation = {
                                    "gid": gid,
                                    "name": name,
                                    "category": category,
                                    "prices": prices, # Keep original prices for debug/upload?
                                    "average_price": average,
                                    "timestamp": int(time.time() * 1000)
                                }
                                
                                if self.callback:
                                    self.callback(observation)
                                    
                except Exception as e:
                    print(f"Error processing packet: {e}")
