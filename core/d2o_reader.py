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
        details = self.get_details(item_id)
        if details:
            return details["name_id"]
        return None

    def get_details(self, item_id):
        if item_id not in self.index:
            return None
        
        offsets = self.index[item_id]
        for offset in offsets:
            self.file.seek(offset)
            
            try:
                # Read first 6 ints: ClassID, ID, NameID, TypeID, DescriptionID, IconID
                data = []
                for _ in range(6):
                    data.append(struct.unpack(">I", self.file.read(4))[0])
                
                class_id = data[0]
                obj_id = data[1]
                name_id = data[2]
                type_id = data[3]
                description_id = data[4]
                icon_id = data[5]
                
                return {
                    "class_id": class_id,
                    "id": obj_id,
                    "name_id": name_id,
                    "type_id": type_id,
                    "description_id": description_id,
                    "icon_id": icon_id
                }
            except struct.error:
                continue
                
        return None

    def close(self):
        self.file.close()
