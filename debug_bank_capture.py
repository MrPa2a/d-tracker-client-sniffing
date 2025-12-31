"""
Script de debug pour capturer et analyser les paquets de la banque.
Lance ce script, puis ouvre ta banque dans le jeu.
"""
import sys
import time
from scapy.all import sniff, TCP, Raw

# Buffer pour reassembler les paquets TCP
buffer = b""
buffer_time = 0

def analyze_packet(packet):
    global buffer, buffer_time
    
    if not packet.haslayer(TCP) or not packet.haslayer(Raw):
        return
    
    src_port = packet[TCP].sport
    
    # Seulement les paquets du serveur Dofus (port 5555)
    if src_port != 5555:
        return
    
    payload = packet[Raw].load
    prefix = b'type.ankama.com/'
    
    idx = payload.find(prefix)
    
    if idx != -1:
        # Nouveau message détecté
        buffer = payload
        buffer_time = time.time()
    else:
        if buffer:
            if time.time() - buffer_time > 5:
                buffer = b""
                return
            buffer += payload
        else:
            return
    
    full_data = buffer
    idx = full_data.find(prefix)
    
    if idx == -1:
        return
    
    # Extraire le suffix du type
    type_end = -1
    for i in range(20):  # Chercher un peu plus loin
        check_pos = idx + len(prefix) + i
        if check_pos < len(full_data) and full_data[check_pos] == 0x12:
            type_end = check_pos
            break
    
    if type_end != -1:
        type_suffix = full_data[idx + len(prefix) : type_end]
        msg_size = len(full_data) - type_end
        
        # Afficher tous les suffixes détectés
        try:
            suffix_str = type_suffix.decode('utf-8', errors='replace')
        except:
            suffix_str = str(type_suffix)
        
        # Filtrer les paquets intéressants (gros paquets = probablement banque)
        if msg_size > 1000:
            print(f"[GROS PAQUET] Suffix: '{suffix_str}' | Taille: {msg_size} bytes")
            
            # Sauvegarder si c'est potentiellement la banque
            if msg_size > 5000:
                filename = f"bank_packet_{suffix_str}_{int(time.time())}.bin"
                with open(filename, 'wb') as f:
                    f.write(full_data[type_end:])
                print(f"  -> Sauvegardé dans {filename}")
        
        # Toujours afficher hzm ou tout ce qui ressemble à "bank"/"storage"
        if b'hzm' in type_suffix or b'bank' in type_suffix.lower() or b'storage' in type_suffix.lower():
            print(f"[BANK CANDIDATE] Suffix: '{suffix_str}' | Taille: {msg_size} bytes")
        
        # Afficher aussi les suffixes peu communs pour debug
        known_suffixes = [b'iqb', b'jbo', b'jcg', b'hyp', b'jeu', b'jet', b'iqw', b'jbl']
        if type_suffix not in known_suffixes and len(type_suffix) <= 5:
            print(f"[NOUVEAU] Suffix: '{suffix_str}' | Taille: {msg_size} bytes")

def main():
    print("=" * 60)
    print("DEBUG: Capture des paquets Dofus")
    print("=" * 60)
    print("Instructions:")
    print("1. Lance Dofus et connecte-toi")
    print("2. Ouvre ta banque dans le jeu")
    print("3. Observe les suffixes détectés ci-dessous")
    print("=" * 60)
    print("Écoute sur le port 5555...")
    print()
    
    try:
        sniff(filter="tcp port 5555", prn=analyze_packet, store=0)
    except PermissionError:
        print("ERREUR: Exécute ce script en tant qu'administrateur!")
        sys.exit(1)
    except Exception as e:
        print(f"ERREUR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
