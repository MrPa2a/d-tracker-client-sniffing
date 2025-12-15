import os
import struct

class D2PReader:
    def __init__(self, content_path):
        self.content_path = content_path
        self.d2p_files = []
        self._scan_d2p_files()

    def _scan_d2p_files(self):
        if not os.path.exists(self.content_path):
            return
            
        for root, dirs, files in os.walk(self.content_path):
            for file in files:
                if file.endswith(".d2p"):
                    self.d2p_files.append(os.path.join(root, file))

    def get_image_data(self, icon_id):
        """
        Searches for {icon_id}.png in all d2p files and returns the binary data.
        """
        filename = f"{icon_id}.png"
        filename_bytes = filename.encode('utf-8')
        
        # Prioritize bitmap files
        sorted_files = sorted(self.d2p_files, key=lambda x: "bitmap" not in x)
        
        for d2p_path in sorted_files:
            try:
                with open(d2p_path, "rb") as f:
                    # Optimization: Read only the last 1MB where the index usually is?
                    # Or read the whole file if it's small enough.
                    # D2P files can be large (100MB+).
                    # Let's try reading the last 5% or fixed amount?
                    # But we don't know where the index starts.
                    # For now, let's read the whole file into memory? No.
                    # mmap? Yes, mmap is good.
                    
                    import mmap
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        # Search for the filename
                        # The entry structure is: [Len(2)] [Name] [Offset(4)] [Len(4)]
                        # So we look for Name.
                        
                        pos = mm.find(filename_bytes)
                        while pos != -1:
                            # Verify length prefix
                            # pos is start of filename.
                            # pos - 2 should be length.
                            if pos >= 2:
                                mm.seek(pos - 2)
                                name_len = struct.unpack(">H", mm.read(2))[0]
                                if name_len == len(filename_bytes):
                                    # Found it!
                                    # Read Offset and Length
                                    mm.seek(pos + name_len)
                                    offset = struct.unpack(">I", mm.read(4))[0]
                                    length = struct.unpack(">I", mm.read(4))[0]
                                    
                                    # Extract data
                                    # Note: Data usually has 2 bytes header (0x60 0x82) before PNG
                                    # We'll read the raw data and let the caller handle it, 
                                    # or strip it if it's consistent.
                                    # In my test, it was 2 bytes.
                                    
                                    mm.seek(offset)
                                    data = mm.read(length)
                                    
                                    # Check for PNG header
                                    # Standard PNG signature: 89 50 4E 47 0D 0A 1A 0A
                                    # Some Dofus assets have 2 bytes prefix (often 60 82)
                                    
                                    if len(data) > 8 and data[0:8] == b"\x89PNG\r\n\x1a\n":
                                        return data
                                    elif len(data) > 10 and data[2:10] == b"\x89PNG\r\n\x1a\n":
                                        return data[2:] # Strip 2 bytes header
                                    else:
                                        # Return raw data, maybe it's not PNG or header is different
                                        return data
                            
                            # Continue search if false positive
                            pos = mm.find(filename_bytes, pos + 1)
                            
            except Exception as e:
                print(f"Error scanning {d2p_path}: {e}")
                continue
                
        return None
