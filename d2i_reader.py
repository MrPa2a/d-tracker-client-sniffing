import struct
import os

class D2IReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.file = open(file_path, "rb")
        self.index = {}
        self._load_index()

    def _load_index(self):
        self.file.seek(0)
        # Header: IndexPtr (4 bytes BE)
        index_ptr = struct.unpack(">I", self.file.read(4))[0]
        
        self.file.seek(index_ptr)
        index_size = struct.unpack(">I", self.file.read(4))[0]
        
        start_pos = self.file.tell()
        end_pos = start_pos + index_size
        
        while self.file.tell() < end_pos:
            try:
                key = struct.unpack(">I", self.file.read(4))[0]
                has_diacritical = self.file.read(1)[0] != 0
                pointer = struct.unpack(">I", self.file.read(4))[0]
                
                diacritical_pointer = None
                if has_diacritical:
                    diacritical_pointer = struct.unpack(">I", self.file.read(4))[0]
                
                self.index[key] = pointer
                # We could store diacritical_pointer too if needed
            except struct.error:
                break

    def get_text(self, key):
        if key not in self.index:
            return None
        
        pointer = self.index[key]
        self.file.seek(pointer)
        length = struct.unpack(">H", self.file.read(2))[0]
        return self.file.read(length).decode("utf-8")

    def close(self):
        self.file.close()
