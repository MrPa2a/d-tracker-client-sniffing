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

def get_field_data(data, field_num):
    """Helper to extract the raw bytes of a specific field (Wire 2 only)."""
    pos = 0
    while pos < len(data):
        try:
            tag, pos = read_varint(data, pos)
            f = tag >> 3
            w = tag & 7
            
            if w == 2:
                length, pos = read_varint(data, pos)
                if f == field_num:
                    return data[pos : pos + length]
                pos += length
            elif w == 0:
                _, pos = read_varint(data, pos)
            elif w == 1:
                pos += 8
            elif w == 5:
                pos += 4
            else:
                break
        except:
            break
    return None

def get_field_value(data, field_num):
    """Helper to extract the integer value of a specific field (Wire 0 only)."""
    pos = 0
    while pos < len(data):
        try:
            tag, pos = read_varint(data, pos)
            f = tag >> 3
            w = tag & 7
            
            if w == 0:
                val, pos = read_varint(data, pos)
                if f == field_num:
                    return val
            elif w == 2:
                length, pos = read_varint(data, pos)
                pos += length
            elif w == 1:
                pos += 8
            elif w == 5:
                pos += 4
            else:
                break
        except:
            break
    return None

def get_all_field_data(data, field_num):
    """Helper to extract ALL occurrences of a specific field (Wire 2 only)."""
    results = []
    pos = 0
    while pos < len(data):
        try:
            tag, pos = read_varint(data, pos)
            f = tag >> 3
            w = tag & 7
            
            if w == 2:
                length, pos = read_varint(data, pos)
                if f == field_num:
                    results.append(data[pos : pos + length])
                pos += length
            elif w == 0:
                _, pos = read_varint(data, pos)
            elif w == 1:
                pos += 8
            elif w == 5:
                pos += 4
            else:
                break
        except:
            break
    return results

def parse_jeu_packet(payload):
    """Décode le paquet 'jeu' ou 'jet' (Item Info + Prices)."""
    gid = 0
    prices = []
    try:
        # GID is usually at root Field 4
        gid = get_field_value(payload, 4)
        
        # Prices are often in Field 1 -> Field 2 (Packed VarInts)
        f1_data = get_field_data(payload, 1)
        if f1_data:
            # Prices in Field 1 -> Field 2
            f2_data = get_field_data(f1_data, 2)
            if f2_data:
                pos = 0
                while pos < len(f2_data):
                    try:
                        price, pos = read_varint(f2_data, pos)
                        if price > 0:
                            prices.append(price)
                    except:
                        break
            
            # Sometimes GID is also in Field 1 -> Field 5
            if not gid:
                gid = get_field_value(f1_data, 5)

    except Exception as e:
        # print(f"[JEU/JET DEBUG] Error: {e}")
        pass
    
    if gid:
        # print(f"[JEU/JET DEBUG] Found GID: {gid}, Prices: {len(prices)}")
        pass
        
    return gid, prices

def parse_hyp_packet(payload):
    """Décode le paquet 'hyp' (Liste de prix HDV)."""
    prices = []
    # gid = 0 # Field 2 is NOT GID (it's 63 for everyone apparently)
    try:
        # Field 2 is repeated (Item in list)
        items_data = get_all_field_data(payload, 2)
        for item_data in items_data:
            # Inside Field 2: Field 4 contains details
            details_data = get_field_data(item_data, 4)
            if details_data:
                # Inside Field 4: 
                # Field 5 is Total Price
                # Field 3 is Quantity (default to 1 if missing)
                price = get_field_value(details_data, 5)
                quantity = get_field_value(details_data, 3)
                
                if quantity is None or quantity == 0:
                    quantity = 1
                
                if price is not None:
                    # On stocke le prix unitaire pour l'analyse
                    unit_price = int(price / quantity)
                    prices.append(unit_price)
                    
                    # Debug spécifique pour Aile de Vortex (recherche des valeurs connues)
                    # if price in [474998, 4897998]:
                    #    print(f"[HYP DEBUG] MATCH FOUND! Price: {price}, Qty: {quantity}")

    except Exception as e:
        # print(f"[HYP DEBUG] Error: {e}")
        pass
    
    if prices:
        # print(f"[HYP DEBUG] Found {len(prices)} prices. Top 5: {prices[:5]}")
        pass
    
    return 0, prices

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
