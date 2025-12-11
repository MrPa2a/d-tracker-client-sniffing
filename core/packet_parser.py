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

def parse_jbo_packet(payload):
    """Décode le nouveau paquet de prix (jbo) détecté en déc 2025."""
    try:
        pos = 0
        gid = 0
        prices = []
        
        while pos < len(payload):
            tag, pos = read_varint(payload, pos)
            field_number = tag >> 3
            wire_type = tag & 7
            
            if field_number == 3 and wire_type == 0: # GID at root level (Field 3)
                gid, pos = read_varint(payload, pos)
            
            elif field_number == 1 and wire_type == 2: # Item Details Submessage (Field 1)
                length, pos = read_varint(payload, pos)
                data_end = pos + length
                data = payload[pos:data_end]
                pos = data_end
                
                # Parsing du sous-message
                sub_pos = 0
                while sub_pos < len(data):
                    sub_tag, sub_pos = read_varint(data, sub_pos)
                    sub_field = sub_tag >> 3
                    sub_wire = sub_tag & 7
                    
                    if sub_field == 1 and sub_wire == 0: # GID inside (Field 1)
                         # On peut aussi récupérer le GID ici si besoin
                         val, sub_pos = read_varint(data, sub_pos)
                         if gid == 0: gid = val
                         
                    elif sub_field == 4 and sub_wire == 2: # Prices (Packed VarInts) (Field 4)
                        len_packed, sub_pos = read_varint(data, sub_pos)
                        packed_end = sub_pos + len_packed
                        while sub_pos < packed_end:
                            price, sub_pos = read_varint(data, sub_pos)
                            prices.append(price)
                    else:
                        # Skip unknown fields inside
                        if sub_wire == 0:
                            _, sub_pos = read_varint(data, sub_pos)
                        elif sub_wire == 2:
                            l, sub_pos = read_varint(data, sub_pos)
                            sub_pos += l
                        else:
                            break
            else:
                # Skip unknown root fields
                if wire_type == 0:
                    _, pos = read_varint(payload, pos)
                elif wire_type == 2:
                    l, pos = read_varint(payload, pos)
                    pos += l
                else:
                    break
                    
        return gid, prices

    except Exception as e:
        # print(f"Erreur de décodage jbo : {e}")
        pass
    
    return None, []

def parse_jcg_packet(payload):
    """Décode le nouveau paquet de prix (jcg) détecté en déc 2025 (v2)."""
    try:
        pos = 0
        gid = 0
        prices = []
        
        while pos < len(payload):
            tag, pos = read_varint(payload, pos)
            field_number = tag >> 3
            wire_type = tag & 7
            
            if field_number == 2 and wire_type == 0: # GID at root level (Field 2)
                gid, pos = read_varint(payload, pos)
            
            elif field_number == 3 and wire_type == 2: # Item Details Submessage (Field 3)
                length, pos = read_varint(payload, pos)
                data_end = pos + length
                data = payload[pos:data_end]
                pos = data_end
                
                # Parsing du sous-message
                sub_pos = 0
                while sub_pos < len(data):
                    sub_tag, sub_pos = read_varint(data, sub_pos)
                    sub_field = sub_tag >> 3
                    sub_wire = sub_tag & 7
                    
                    if sub_field == 5 and sub_wire == 0: # GID inside (Field 5) - Backup
                         val, sub_pos = read_varint(data, sub_pos)
                         if gid == 0: gid = val
                         
                    elif sub_field == 2 and sub_wire == 2: # Prices (Packed VarInts) (Field 2)
                        len_packed, sub_pos = read_varint(data, sub_pos)
                        packed_end = sub_pos + len_packed
                        while sub_pos < packed_end:
                            price, sub_pos = read_varint(data, sub_pos)
                            prices.append(price)
                    else:
                        # Skip unknown fields inside
                        if sub_wire == 0:
                            _, sub_pos = read_varint(data, sub_pos)
                        elif sub_wire == 2:
                            l, sub_pos = read_varint(data, sub_pos)
                            sub_pos += l
                        else:
                            break
            else:
                # Skip unknown root fields
                if wire_type == 0:
                    _, pos = read_varint(payload, pos)
                elif wire_type == 2:
                    l, pos = read_varint(payload, pos)
                    pos += l
                else:
                    break
                    
        return gid, prices

    except Exception as e:
        # print(f"Erreur de décodage jcg : {e}")
        pass
    
    return None, []
