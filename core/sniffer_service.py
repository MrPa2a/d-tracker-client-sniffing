import threading
import time
import json
from scapy.all import sniff, TCP, IP, Raw
from core.packet_parser import parse_iqb_packet, parse_jbo_packet, parse_jcg_packet, parse_hyp_packet, parse_jeu_packet, read_varint
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

        # State for multi-packet parsing (v3 protocol)
        self.last_gid = 0
        self.last_prices = []
        self.last_gid_time = 0
        self.last_price_time = 0
        
        # Buffer for TCP reassembly (Simple)
        self.buffer = b""
        self.buffer_time = 0

    def run(self):
        self.running = True
        self.log("Sniffer thread started.", "INFO")
        try:
            # Load game data if not loaded
            if not game_data.loaded:
                game_data.load()
                
            sniff(prn=self.packet_callback, store=0, stop_filter=lambda x: not self.running)
        except Exception as e:
            error_msg = f"Sniffer error: {e}"
            self.log(error_msg, "ERROR")
            self.running = False
            if self.on_error:
                self.on_error(str(e))

    def stop(self):
        self.running = False

    def log(self, message, level="INFO"):
        """Affiche un log si le niveau est suffisant."""
        debug_mode = config_manager.get("debug_mode", False)
        
        if level == "ERROR":
            print(f"[ERROR] {message}")
        elif level == "INFO":
            print(f"[INFO] {message}")
        elif level == "DEBUG" and debug_mode:
            print(f"[DEBUG] {message}")

    def log_protobuf_structure(self, data, indent=0):
        """Affiche la structure Protobuf d'un paquet inconnu."""
        pos = 0
        while pos < len(data):
            try:
                tag, new_pos = read_varint(data, pos)
                field_number = tag >> 3
                wire_type = tag & 7
                
                prefix = "  " * indent
                self.log(f"{prefix}Field {field_number} (Wire {wire_type})", "DEBUG")
                
                if wire_type == 0: # VarInt
                    val, new_pos = read_varint(data, new_pos)
                    self.log(f"{prefix}  Value: {val}", "DEBUG")
                    pos = new_pos
                elif wire_type == 2: # Length Delimited
                    length, new_pos = read_varint(data, new_pos)
                    self.log(f"{prefix}  Length: {length}", "DEBUG")
                    sub_data = data[new_pos : new_pos + length]
                    self.log(f"{prefix}  Data (hex): {sub_data.hex()}", "DEBUG")
                    # Recursive attempt
                    if length > 0:
                        self.log(f"{prefix}  -> Sub-message analysis:", "DEBUG")
                        self.log_protobuf_structure(sub_data, indent + 1)
                    pos = new_pos + length
                elif wire_type == 1: # 64-bit
                    pos = new_pos + 8
                elif wire_type == 5: # 32-bit
                    pos = new_pos + 4
                else:
                    self.log(f"{prefix}  Unknown wire type {wire_type}", "DEBUG")
                    break
            except Exception as e:
                self.log(f"{'  ' * indent}Error parsing: {e}", "DEBUG")
                break

    def dump_packet_structure(self, gid, data):
        """Dumps the full protobuf structure to a file for analysis."""
        filename = f"packet_structure_{gid}.txt"
        self.log(f"Dumping packet structure to {filename}...", "INFO")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Packet Structure for GID {gid}\n")
            f.write("================================\n")
            self._recursive_structure_dump(data, 0, f)

    def _recursive_structure_dump(self, data, indent, f):
        pos = 0
        while pos < len(data):
            try:
                tag, new_pos = read_varint(data, pos)
                field_number = tag >> 3
                wire_type = tag & 7
                
                prefix = "  " * indent
                f.write(f"{prefix}Field {field_number} (Wire {wire_type})")
                
                if wire_type == 0: # VarInt
                    val, new_pos = read_varint(data, new_pos)
                    f.write(f" : Value = {val}\n")
                    pos = new_pos
                elif wire_type == 2: # Length Delimited
                    length, new_pos = read_varint(data, new_pos)
                    f.write(f" : Length = {length}\n")
                    sub_data = data[new_pos : new_pos + length]
                    
                    # Heuristic: Try to recurse if it looks like a message
                    # We assume it's a sub-message if it's long enough
                    if length > 0:
                        f.write(f"{prefix}  [Hex]: {sub_data.hex()[:30]}...\n")
                        # Tentative de parsing récursif
                        try:
                            f.write(f"{prefix}  -> Decoding sub-message:\n")
                            self._recursive_structure_dump(sub_data, indent + 1, f)
                        except:
                            pass
                    
                    pos = new_pos + length
                elif wire_type == 1: # 64-bit
                    f.write(f" : 64-bit value\n")
                    pos = new_pos + 8
                elif wire_type == 5: # 32-bit
                    f.write(f" : 32-bit value\n")
                    pos = new_pos + 4
                else:
                    f.write(f" : Unknown wire type {wire_type}\n")
                    break
            except Exception as e:
                f.write(f"\n{prefix}  End of stream or error: {e}\n")
                break

    def encode_varint(self, value):
        """Encodes an integer as a VarInt (Protobuf style)."""
        out = []
        while value > 127:
            out.append((value & 0x7F) | 0x80)
            value >>= 7
        out.append(value & 0x7F)
        return bytes(out)

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
            
            # --- TCP Reassembly Logic ---
            prefix = b'type.ankama.com/'
            idx = payload.find(prefix)
            
            if idx != -1:
                # New message start found
                self.buffer = payload
                self.buffer_time = time.time()
                # self.log("New message start detected, buffering...", "DEBUG")
            else:
                # No header found
                if self.buffer:
                    # Check timeout (5s)
                    if time.time() - self.buffer_time > 5:
                        self.buffer = b""
                        self.log("Buffer timeout, clearing.", "DEBUG")
                        return
                        
                    # Append to buffer
                    self.buffer += payload
                    # self.log(f"Appended {len(payload)} bytes to buffer (Total: {len(self.buffer)})", "DEBUG")
                else:
                    # No buffer and no header -> Ignore
                    return

            # Work with the buffer
            full_data = self.buffer
            
            # Re-find prefix in full_data (it must be there if buffer is set)
            idx = full_data.find(prefix)
            
            if idx != -1:
                # self.log(f"Found Ankama prefix at index {idx}", "DEBUG")
                try:
                    # Determine type suffix
                    # Heuristic: Scan for 0x12 (Tag for field 2) within reasonable distance
                    type_end = -1
                    for i in range(10):
                        check_pos = idx + len(prefix) + i
                        if check_pos < len(full_data) and full_data[check_pos] == 0x12:
                            type_end = check_pos
                            break
                    
                    if type_end != -1:
                        type_suffix = full_data[idx + len(prefix) : type_end]
                        # self.log(f"Detected type suffix: {type_suffix}", "DEBUG")
                        
                        curr = type_end + 1 # Skip Tag 0x12
                        msg_len, curr = read_varint(full_data, curr)
                        # self.log(f"Message length: {msg_len}", "DEBUG")
                        
                        # Check if we have the full message
                        if curr + msg_len > len(full_data):
                            # self.log(f"Waiting for more data... ({len(full_data)}/{curr + msg_len})", "DEBUG")
                            return # Wait for next packet
                        
                        # We have the full message!
                        msg_payload = full_data[curr : curr + msg_len]
                        
                        # Clear buffer (we consumed the message)
                        # Note: If there are multiple messages in buffer, we lose them here. 
                        # But usually it's one large message split.
                        self.buffer = b""
                        
                        gid = 0
                        prices = []
                        
                        if type_suffix == b'iqb':
                            gid, prices = parse_iqb_packet(msg_payload)
                        elif type_suffix == b'jbo':
                            gid, prices = parse_jbo_packet(msg_payload)
                        elif type_suffix == b'jcg':
                            # Previously ignored, but seems to be the new price packet (v2)
                            gid, prices = parse_jcg_packet(msg_payload)
                        elif type_suffix == b'iqw':
                            # Chat / Social packet - Ignore
                            pass
                        elif type_suffix == b'jbl':
                            # Stats / Map info - Ignore
                            pass
                        elif type_suffix == b'jeu' or type_suffix == b'jet':
                            g, p = parse_jeu_packet(msg_payload)
                            if g:
                                if g == 104:
                                    self.log(f"Ignored GID 104 (Eliby/Noise)", "DEBUG")
                                    return

                                self.log(f"[{type_suffix.decode().upper()}] Found GID: {g}", "DEBUG")
                                
                                if p:
                                    self.log(f"[{type_suffix.decode().upper()}] Found {len(p)} prices directly in packet!", "INFO")
                                    gid = g
                                    prices = p
                                    
                                    # DEBUG: Dump structure for Dofus Ocre or specific items
                                    # if gid == 7754 or gid == 6980: # Ocre or Vulbis
                                    #    self.dump_packet_structure(gid, msg_payload)
                                else:
                                    self.last_gid = g
                                    self.last_gid_time = time.time()
                                    
                                    if self.last_prices and (time.time() - self.last_price_time < 20.0):
                                        # Check if we have multiple price lists in memory (from multiple HYP packets)
                                        # and try to find the one that matches best (heuristic?)
                                        # For now, we just take the most recent one.
                                        
                                        self.log(f"[COMBINE] Linking GID {g} with {len(self.last_prices)} prices", "INFO")
                                        gid = g
                                        prices = self.last_prices
                                        
                                        # Clear cache immediately to avoid reusing these prices for another item
                                        self.last_prices = []
                                        self.last_gid = 0
                                    else:
                                        if not self.last_prices:
                                            self.log(f"[WARNING] GID {g} found but no prices in memory. (Cache active?)", "DEBUG")
                                        else:
                                            self.log(f"[WARNING] GID {g} found but prices expired ({time.time() - self.last_price_time:.1f}s ago).", "DEBUG")

                        elif type_suffix == b'hyp':
                            # HYP packets contain unreliable prices (often averages or history, not current HDV)
                            # We ignore them to avoid polluting the data with incorrect values.
                            # _, p = parse_hyp_packet(msg_payload)
                            pass
                        else:
                            # Heuristic check for GID 15715 in raw payload to find missing packets
                            # if b'\xe3\x7a' in msg_payload:
                            #      self.log(f"[HEURISTIC] Found GID 15715 (VarInt) in packet {type_suffix}", "DEBUG")

                            # Only analyze interesting packets (likely price lists > 50 bytes)
                            if len(msg_payload) > 50:
                                pass
                                # self.log(f"[CANDIDATE] Unknown suffix {type_suffix} (len={len(msg_payload)})", "INFO")
                                # self.log("--- PROTOBUF STRUCTURE ANALYSIS ---", "INFO")
                                # self.log_protobuf_structure(msg_payload)
                                # self.log("-----------------------------------", "INFO")
                            else:
                                pass
                                # self.log(f"Ignored small unknown packet: {type_suffix} (len={len(msg_payload)})", "DEBUG")

                            # Try all just in case
                            gid, prices = parse_jcg_packet(msg_payload)
                            if not gid or not prices:
                                gid, prices = parse_jbo_packet(msg_payload)
                            if not gid or not prices:
                                gid, prices = parse_iqb_packet(msg_payload)
                            # if not gid or not prices:
                            #    gid, prices = parse_iqw_packet(msg_payload)
                            # if not gid or not prices:
                            #    gid, prices = parse_jeu_packet(msg_payload)
                        
                        if gid and prices:
                            self.log(f"Packet parsed: GID={gid}, Prices={len(prices)}", "DEBUG")
                            
                            # DEBUG: Dump packet for analysis
                            if config_manager.get("debug_mode"):
                                try:
                                    suffix_str = type_suffix.decode('utf-8', errors='ignore')
                                    filename = f"debug_packets/{gid}_{suffix_str}_{int(time.time())}.bin"
                                    with open(filename, "wb") as f:
                                        f.write(msg_payload)
                                except Exception as e:
                                    self.log(f"Error dumping packet: {e}", "ERROR")

                            name = game_data.get_item_name(gid)
                            
                            if not name:
                                self.log(f"Unknown item: {gid}", "DEBUG")
                                if self.on_unknown_item:
                                    self.on_unknown_item(gid, prices)
                                    return
                                else:
                                    return
                                
                            # Determine processing strategy based on item type
                            is_equipment = game_data.is_equipment(gid)
                            category = game_data.get_item_category(gid)
                            if not category:
                                category = "Catégorie Inconnue"

                            if is_equipment:
                                # For equipment, we only take the minimum price (cheapest)
                                # because each item is unique (stats vary)
                                min_price = min(prices)
                                self.log(f"Item {name} is Equipment ({category}). Using min price: {min_price}", "DEBUG")
                                filtered_prices = [min_price]
                                average = min_price
                            else:
                                # For resources, we filter anomalies and calculate average
                                filtered_prices, average = self.filter.filter_prices(prices)
                                self.log(f"Filtered: {len(filtered_prices)} prices, Avg={average}", "DEBUG")
                            
                            if average > 0:
                                observation = {
                                    "gid": gid,
                                    "name": name,
                                    "category": category,
                                    "prices": prices, # Keep original prices for debug/upload?
                                    "average_price": average,
                                    "timestamp": int(time.time() * 1000)
                                }

                                # DEBUG: Dump raw observation to file
                                if config_manager.get("debug_mode"):
                                    try:
                                        with open("observations.json", "a", encoding="utf-8") as f:
                                            f.write(json.dumps(observation, ensure_ascii=False) + "\n")
                                    except Exception as e:
                                        self.log(f"Error dumping observation: {e}", "ERROR")
                                
                                if self.callback:
                                    self.log(f"Sending observation for {name}", "INFO")
                                    self.callback(observation)
                            else:
                                self.log(f"Average price is 0 or less, ignoring", "DEBUG")
                        else:
                            pass
                            # self.log("Failed to parse GID or prices", "DEBUG")
                                    
                except Exception as e:
                    self.log(f"Error processing packet: {e}", "ERROR")
