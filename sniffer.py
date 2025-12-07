from scapy.all import sniff, TCP, IP, Raw, conf
from colorama import init, Fore, Style
import sys
from game_data import game_data

# Initialisation de colorama
init()

# Chargement des données
game_data.load()

def read_varint(buffer, pos):
    """Lit un VarInt depuis une position donnée. Retourne (valeur, nouvelle_pos)."""
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

def parse_iqb_packet(payload):
    """Décode le paquet de prix (iqb)."""
    try:
        pos = 0
        gid = 0
        prices = []
        
        while pos < len(payload):
            tag, pos = read_varint(payload, pos)
            field_number = tag >> 3
            wire_type = tag & 7
            
            if field_number == 1 and wire_type == 0: # GID (VarInt)
                gid, pos = read_varint(payload, pos)
            
            elif field_number == 3 and wire_type == 2: # Details (Length Delimited)
                length, pos = read_varint(payload, pos)
                data_end = pos + length
                data = payload[pos:data_end]
                pos = data_end 
                
                # Parsing des détails
                sub_pos = 0
                while sub_pos < len(data):
                    sub_tag, sub_pos = read_varint(data, sub_pos)
                    sub_field = sub_tag >> 3
                    sub_wire = sub_tag & 7
                    
                    if sub_field == 3 and sub_wire == 2: # Liste des prix (Packed VarInts)
                        len_packed, sub_pos = read_varint(data, sub_pos)
                        packed_end = sub_pos + len_packed
                        while sub_pos < packed_end:
                            price, sub_pos = read_varint(data, sub_pos)
                            prices.append(price)
                    else:
                        # Skip unknown fields inside details
                        if sub_wire == 0:
                            _, sub_pos = read_varint(data, sub_pos)
                        elif sub_wire == 2:
                            l, sub_pos = read_varint(data, sub_pos)
                            sub_pos += l
                        else:
                            break
            else:
                # Skip unknown fields at top level
                if wire_type == 0:
                    _, pos = read_varint(payload, pos)
                elif wire_type == 2:
                    l, pos = read_varint(payload, pos)
                    pos += l
                else:
                    break
                    
        return gid, prices

    except Exception as e:
        # print(f"Erreur de décodage : {e}")
        pass
    
    return None, []

def packet_callback(packet):
    if not packet.haslayer(TCP):
        return
        
    src_port = packet[TCP].sport
    
    # On ne traite que ce qui vient du serveur (5555)
    if src_port == 5555 and packet.haslayer(Raw):
        payload = packet[Raw].load
        
        # Recherche du pattern 'type.ankama.com/iqb'
        search_pattern = b'type.ankama.com/iqb'
        idx = payload.find(search_pattern)
        
        if idx != -1:
            try:
                # On se place juste après la string
                curr = idx + len(search_pattern)
                
                # On s'attend à trouver le Tag du champ Value (0x12)
                if curr < len(payload) and payload[curr] == 0x12:
                    curr += 1 # Skip Tag
                    msg_len, curr = read_varint(payload, curr)
                    
                    msg_payload = payload[curr : curr + msg_len]
                    
                    gid, prices = parse_iqb_packet(msg_payload)
                    
                    if gid:
                        name = game_data.get_item_name(gid)
                        
                        if name is None:
                            print(f"{Fore.RED}[UNKNOWN] Item inconnu détecté (GID: {gid}){Style.RESET_ALL}")
                            print(f"Prix associés : {prices}")
                            try:
                                # On demande à l'utilisateur d'identifier l'item
                                print(f"{Fore.YELLOW}>>> Quel est le nom de cet item ? (Entrée pour ignorer){Style.RESET_ALL}")
                                user_name = input("Nom : ")
                                if user_name.strip():
                                    game_data.save_user_item(gid, user_name.strip())
                                    name = user_name.strip()
                                else:
                                    name = f"Unknown Item ({gid})"
                            except Exception as e:
                                print(f"Erreur input: {e}")
                                name = f"Unknown Item ({gid})"

                        print(f"{Fore.GREEN}[DETECTED] {name} (GID: {gid}){Style.RESET_ALL}")
                        print(f" - Prix : {prices}")
            except Exception as e:
                pass

def start_sniffer():
    print(f"{Fore.YELLOW}Démarrage du sniffer Dofus Unity...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}En attente de paquets de prix (HDV)...{Style.RESET_ALL}")
    
    try:
        sniff(prn=packet_callback, store=0)
    except Exception as e:
        print(f"{Fore.RED}Erreur :{Style.RESET_ALL}")
        print(e)

if __name__ == "__main__":
    start_sniffer()
