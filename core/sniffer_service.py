import threading
import time
from scapy.all import sniff, TCP, IP, Raw
from core.packet_parser import parse_iqb_packet, read_varint
from core.game_data import game_data
from core.anomaly_filter import AnomalyFilter
from utils.config import config_manager

class SnifferService(threading.Thread):
    def __init__(self, callback=None, on_error=None):
        super().__init__()
        self.callback = callback
        self.on_error = on_error
        self.running = False
        self.filter = AnomalyFilter(
            min_price=config_manager.get("min_price_threshold", 10),
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
            
            # Search for 'type.ankama.com/iqb'
            search_pattern = b'type.ankama.com/iqb'
            idx = payload.find(search_pattern)
            
            if idx != -1:
                try:
                    curr = idx + len(search_pattern)
                    
                    if curr < len(payload) and payload[curr] == 0x12:
                        curr += 1 # Skip Tag
                        msg_len, curr = read_varint(payload, curr)
                        
                        msg_payload = payload[curr : curr + msg_len]
                        
                        gid, prices = parse_iqb_packet(msg_payload)
                        
                        if gid and prices:
                            name = game_data.get_item_name(gid)
                            if not name:
                                name = f"Unknown Item ({gid})"
                                
                            # Filter anomalies
                            filtered_prices, average = self.filter.filter_prices(prices)
                            
                            if average > 0:
                                observation = {
                                    "gid": gid,
                                    "name": name,
                                    "prices": prices, # Keep original prices for debug/upload?
                                    "average_price": average,
                                    "timestamp": int(time.time() * 1000)
                                }
                                
                                if self.callback:
                                    self.callback(observation)
                                    
                except Exception as e:
                    print(f"Error processing packet: {e}")
