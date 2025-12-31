"""
Script pour analyser la structure du paquet jcr (banque).
"""
import os
import sys

def read_varint(data, pos):
    """Lit un VarInt à partir de la position donnée."""
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result, pos

def parse_simple_proto(data):
    """Parse un message protobuf simple et retourne un dict des champs."""
    fields = {}
    pos = 0
    while pos < len(data):
        try:
            tag, new_pos = read_varint(data, pos)
            field_num = tag >> 3
            wire_type = tag & 0x07
            
            if wire_type == 0:  # VarInt
                value, new_pos = read_varint(data, new_pos)
                fields[field_num] = value
            elif wire_type == 2:  # Length-delimited
                length, new_pos = read_varint(data, new_pos)
                fields[f'{field_num}_bytes'] = data[new_pos:new_pos + length]
                new_pos += length
            elif wire_type == 1:  # 64-bit
                new_pos += 8
            elif wire_type == 5:  # 32-bit
                new_pos += 4
            else:
                new_pos = pos + 1
                
            pos = new_pos if new_pos > pos else pos + 1
        except:
            break
    return fields

def analyze_jcr_packet(filename):
    """Analyse la structure du paquet jcr."""
    with open(filename, 'rb') as f:
        data = f.read()
    
    print(f"Fichier: {filename}")
    print(f"Taille: {len(data)} bytes")
    print()
    
    # Skip le tag 0x12 et la longueur au début
    pos = 0
    if data[0] == 0x12:
        pos = 1
        length, pos = read_varint(data, pos)
        print(f"Tag 0x12, longueur: {length}")
    
    payload = data[pos:]
    
    # Analyser la structure de premier niveau
    print("=" * 60)
    print("Structure de premier niveau:")
    print("=" * 60)
    
    items = []
    pos = 0
    item_count = 0
    
    while pos < len(payload):
        try:
            tag, new_pos = read_varint(payload, pos)
            field_num = tag >> 3
            wire_type = tag & 0x07
            
            if wire_type == 2:  # Length-delimited (probablement un item)
                length, new_pos = read_varint(payload, new_pos)
                item_data = payload[new_pos:new_pos + length]
                
                if field_num == 1 and length > 5:  # Probablement un item
                    item_count += 1
                    
                    # Parser l'item
                    inner = parse_simple_proto(item_data)
                    
                    # Chercher les champs importants
                    gid = None
                    quantity = None
                    uid = None
                    
                    # Essayer différentes structures
                    for key, value in inner.items():
                        if isinstance(value, int):
                            if key == 2:
                                uid = value
                            elif key == 3:
                                quantity = value
                            elif key == 5:
                                gid = value
                    
                    # Si on a un sous-message (field 4_bytes), le parser
                    if '4_bytes' in inner:
                        sub_inner = parse_simple_proto(inner['4_bytes'])
                        for key, value in sub_inner.items():
                            if isinstance(value, int):
                                if key == 2:
                                    uid = value
                                elif key == 3:
                                    quantity = value
                                elif key == 5:
                                    gid = value
                    
                    if gid:
                        items.append({'gid': gid, 'quantity': quantity or 1, 'uid': uid})
                    
                    if item_count <= 10:
                        print(f"\nItem {item_count}:")
                        print(f"  Field: {field_num}, Length: {length}")
                        print(f"  Inner fields: {inner}")
                        if gid:
                            print(f"  -> GID: {gid}, Qty: {quantity}, UID: {uid}")
                
                new_pos += length
            elif wire_type == 0:
                value, new_pos = read_varint(payload, new_pos)
                if item_count <= 10:
                    print(f"Field {field_num} (VarInt): {value}")
            else:
                new_pos = pos + 1
            
            pos = new_pos if new_pos > pos else pos + 1
        except Exception as e:
            print(f"Erreur à pos {pos}: {e}")
            break
    
    print()
    print("=" * 60)
    print(f"Total items trouvés: {item_count}")
    print(f"Items avec GID valide: {len(items)}")
    print("=" * 60)
    
    if items:
        print("\nExemples d'items:")
        for i, item in enumerate(items[:20]):
            print(f"  {i+1}. GID: {item['gid']}, Qty: {item['quantity']}")

def main():
    # Trouver le fichier bank_packet le plus récent
    files = [f for f in os.listdir('.') if f.startswith('bank_packet_')]
    if not files:
        print("Aucun fichier bank_packet_*.bin trouvé!")
        print("Lance d'abord debug_bank_capture.py et ouvre ta banque.")
        sys.exit(1)
    
    # Prendre le plus récent (ou le plus gros)
    files.sort(key=lambda x: os.path.getsize(x), reverse=True)
    analyze_jcr_packet(files[0])

if __name__ == "__main__":
    main()
