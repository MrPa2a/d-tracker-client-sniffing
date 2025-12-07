from .data.binrw import Data
import logging

logger = logging.getLogger("labot")

# Manual protocol definition for POC
types = {
    "BidExchangerObjectInfo": {
        "name": "BidExchangerObjectInfo",
        "vars": [
            {"name": "objectGID", "type": "VarUhInt"},
            {"name": "objectType", "type": "Int"}, # Try Int (4 bytes)
            {"name": "prices", "type": "Vector", "inner_type": "VarUhLong", "length_type": "UnsignedShort"}
        ]
    }
}

msg_from_id = {
    5752: {
        "name": "ExchangeTypesItemsExchangerDescriptionForUserMessage",
        "vars": [
            {"name": "itemTypeDescriptions", "type": "Vector", "inner_type": "BidExchangerObjectInfo", "length_type": "UnsignedShort"}
        ]
    }
}

def read(type_def, data: Data):
    if isinstance(type_def, str):
        # Primitive types
        if type_def == "VarUhInt":
            return data.readVarUhInt()
        elif type_def == "VarUhLong":
            return data.readVarUhLong()
        elif type_def == "Int":
            return data.readInt()
        elif type_def == "UnsignedShort":
            return data.readUnsignedShort()
        elif type_def in types:
            return read(types[type_def], data)
        else:
            raise Exception(f"Unknown type: {type_def}")
            
    ans = {}
    ans["__type__"] = type_def["name"]
    
    for var in type_def["vars"]:
        if var["type"] == "Vector":
            # Read length
            n = read(var["length_type"], data)
            # Read items
            items = []
            for _ in range(n):
                items.append(read(var["inner_type"], data))
            ans[var["name"]] = items
        else:
            ans[var["name"]] = read(var["type"], data)
            
    return ans
