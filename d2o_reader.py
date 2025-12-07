import struct
import os

class D2OReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.file = open(file_path, "rb")
        self.index = {}
        self._load_index()

    def _load_index(self):
        self.file.seek(3) # Skip "D2O"
        index_ptr = struct.unpack(">I", self.file.read(4))[0]
        
        self.file.seek(index_ptr)
        count = struct.unpack(">I", self.file.read(4))[0]
        
        for _ in range(count):
            item_id = struct.unpack(">I", self.file.read(4))[0]
            offset = struct.unpack(">I", self.file.read(4))[0]
            if item_id not in self.index:
                self.index[item_id] = []
            self.index[item_id].append(offset)

    def get_name_id(self, item_id):
        if item_id not in self.index:
            return None
        
        offsets = self.index[item_id]
        for offset in offsets:
            self.file.seek(offset)
            
            # Structure: ClassID (4), ID (4), NameID (4)
            try:
                class_id = struct.unpack(">I", self.file.read(4))[0]
                # We only care about Item class (ID 4 seems to be Item)
                # But let's be lenient and just check if NameID is non-zero
                
                # Skip ID (4)
                self.file.read(4)
                
                name_id = struct.unpack(">I", self.file.read(4))[0]
                if name_id != 0:
                    return name_id
            except struct.error:
                continue
                
        return None

    def close(self):
        self.file.close()
