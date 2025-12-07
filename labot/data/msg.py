from .binrw import Data, Buffer
from .. import protocol

class Msg:
    def __init__(self, m_id, data, count=None):
        self.id = m_id
        if isinstance(data, bytearray):
            data = Data(data)
        self.data = data
        self.count = count

    def __str__(self):
        ans = str.format(
            "{}(m_id={}, data={}, count={})",
            self.__class__.__name__,
            self.id,
            self.data.data,
            self.count,
        )
        return ans

    def __repr__(self):
        ans = str.format(
            "{}(m_id={}, data={!r}, count={})",
            self.__class__.__name__,
            self.id,
            self.data.data,
            self.count,
        )
        return ans

    @staticmethod
    def fromRaw(buf: Buffer, from_client):
        """Read a message from the buffer and
        empty the beginning of the buffer.
        """
        if not buf:
            return
        try:
            if len(buf) < 2:
                return None
            header = buf.readUnsignedShort()
            if from_client:
                if len(buf) < buf.pos + 4:
                    buf.pos = 0
                    return None
                count = buf.readUnsignedInt()
            else:
                count = None
            
            len_type = header & 3
            if len(buf) < buf.pos + len_type:
                buf.pos = 0
                return None
                
            lenData = int.from_bytes(buf.read(len_type), "big")
            id = header >> 2
            
            if len(buf) < buf.pos + lenData:
                buf.pos = 0
                return None
                
            data = Data(buf.read(lenData))
        except IndexError:
            buf.pos = 0
            # logger.debug("Could not parse message: Not complete")
            return None
        else:
            # if id == 2:
            #     # NetworkDataContainerMessage handling would go here
            #     pass
            
            # logger.debug("Parsed %s", protocol.msg_from_id.get(id, {"name": str(id)})["name"])
            buf.end()
            return Msg(id, data, count)

    def lenlenData(self):
        if len(self.data) > 65535:
            return 3
        if len(self.data) > 255:
            return 2
        if len(self.data) > 0:
            return 1
        return 0

    def bytes(self):
        header = 4 * self.id + self.lenlenData()
        ans = Data()
        ans.writeShort(header)
        if self.count is not None:
            ans.writeUnsignedInt(self.count)
        ans += len(self.data).to_bytes(self.lenlenData(), "big")
        ans += self.data
        return ans.data

    @property
    def msgType(self):
        return protocol.msg_from_id.get(self.id)

    def json(self):
        if not hasattr(self, "parsed"):
            self.parsed = protocol.read(self.msgType, self.data)
        return self.parsed
