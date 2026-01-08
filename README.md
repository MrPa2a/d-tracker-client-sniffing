# 🕵️ Dofus Tracker Client V3 (Network Sniffer)

> A Python-based network packet sniffer for real-time market data extraction from the MMORPG Dofus. Features protocol reverse-engineering, binary file parsing, and a modern GUI with overlay mode.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python)
![Scapy](https://img.shields.io/badge/Scapy-2.5-00A98F?style=flat-square)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.x-1F6FEB?style=flat-square)
![Version](https://img.shields.io/badge/Version-3.2.0-green?style=flat-square)

---

## 🎯 Project Overview

**Dofus Tracker Client V3** is a desktop application that captures and decodes network packets from the Dofus game client to extract real-time market (Auction House) data with 100% accuracy.

This project demonstrates proficiency in:
- **Network programming** with raw packet capture and TCP reassembly
- **Protocol reverse-engineering** (Protobuf-like binary protocol)
- **Binary file format parsing** (custom game data formats: D2O, D2I, D2P)
- **Multi-threaded architecture** for concurrent sniffing and uploading
- **Desktop GUI development** with modern dark-themed UI and overlay mode
- **Data quality algorithms** (anomaly detection, statistical filtering)

---

## ⚖️ Disclaimer

**This project is developed strictly for educational purposes.**

It is designed to explore network traffic analysis, binary protocol reverse-engineering, and data visualization. It is **not a bot** and does not automate any in-game actions.

> ⚠️ **Warning**: The use of third-party tools may violate the Terms of Service of Ankama Games. I strongly advise against using this tool on official servers. Use this project only for learning purposes.

*Dofus is a registered trademark of Ankama Games. This project is not affiliated with Ankama.*

---

## ✨ Key Features

### 🔍 Network Packet Sniffing
- Real-time capture of Dofus network traffic on port 5555
- TCP stream reassembly for fragmented packets
- BPF filtering for optimized capture performance

### 📦 Protocol Reverse-Engineering
- Custom Protobuf-like parser (VarInt, Wire Types)
- Decoding of multiple packet types:
  - `ExchangeTypesItemsExchangerDescriptionForUserMessage` (market prices)
  - Bank content packets
  - Item metadata packets

### 📁 Binary Game Data Parsing
- **D2O Reader**: Parses game object definitions (Items, Types)
- **D2I Reader**: Parses internationalization strings (item names)
- **D2P Reader**: Extracts assets from game archives (icons)

### 📊 Data Quality & Anomaly Detection
- Statistical outlier filtering (median-based)
- Price normalization across lot sizes (x1, x10, x100, x1000)
- Configurable min/max thresholds

### 🖥️ Modern Desktop GUI
- Dark-themed UI with CustomTkinter
- **Floating overlay mode** for in-game monitoring
- Real-time console output with logging
- Server and profile selection

### ☁️ Backend Integration
- Batch uploading with configurable intervals
- Automatic retry on network failures
- Bearer token authentication
- Auto-update system via GitHub releases

---

## 🏗️ Architecture & Technical Highlights

### Project Structure
```
dofus-tracker-client-v3/
├── main.py                 # Application entry point
├── config.json             # User configuration
├── core/                   # Core business logic
│   ├── sniffer_service.py  # Packet capture (Scapy) with TCP reassembly
│   ├── packet_parser.py    # Protobuf-like protocol decoder
│   ├── game_data.py        # Item name resolution & caching
│   ├── anomaly_filter.py   # Statistical outlier detection
│   ├── d2o_reader.py       # Binary D2O format parser
│   ├── d2i_reader.py       # Binary D2I format parser (i18n)
│   ├── d2p_reader.py       # Binary D2P archive reader
│   └── updater.py          # Auto-update via GitHub
├── network/                # Network layer
│   ├── uploader.py         # Batch HTTP uploader (threaded)
│   └── profiles_client.py  # Profile management API
├── ui/                     # User interface
│   ├── main_window.py      # Main application window
│   └── overlay.py          # Floating overlay widget
├── labot/                  # Protocol utilities (adapted from LaBot)
│   └── data/               # Binary stream readers
├── pydofus/                # Dofus file format library
│   ├── d2o.py, d2i.py, d2p.py  # Format implementations
│   └── _binarystream.py    # Low-level binary reading
└── scripts/                # Utility scripts
    ├── ingest_static_data.py   # Database seeding
    └── update_recipes_from_dofusdb.py  # Recipe sync
```

### Key Technical Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Packet Capture** | Scapy | Cross-platform, powerful filtering, raw access |
| **Protocol Parsing** | Custom VarInt/Protobuf | Game uses proprietary format, no .proto files available |
| **GUI Framework** | CustomTkinter | Modern look, native performance, no Electron overhead |
| **Threading Model** | Daemon threads | Sniffer & uploader run concurrently, clean shutdown |
| **Binary Parsing** | struct module | Direct memory layout control for game formats |
| **Distribution** | PyInstaller | Single .exe for easy end-user deployment |

### Protocol Parsing Example

The game uses a Protobuf-like binary protocol. Here's how we decode VarInt fields:

```python
def read_varint(buffer, pos):
    """Reads a VarInt from the buffer at the given position."""
    value = 0
    shift = 0
    while True:
        byte = buffer[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, pos
        shift += 7
```

### Anomaly Detection

Prices are filtered using statistical methods to remove outliers:

```python
# Median-based filtering
if len(valid_prices) >= 3:
    median = statistics.median(valid_prices)
    upper_bound = median * 5
    lower_bound = median / 5
    final_prices = [p for p in valid_prices if lower_bound <= p <= upper_bound]
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Npcap** (Windows) — Required for packet capture
  - Download: [https://npcap.com/](https://npcap.com/)
  - ✅ Check **"Install Npcap in WinPcap API-compatible Mode"**

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/dofus-tracker.git
cd dofus-tracker/dofus-tracker-client-v3

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate  # Windows
# source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure the client
cp config.example.json config.json
# Edit config.json with your API URL and token
```

### Configuration

Edit `config.json`:

```json
{
  "api_url": "https://your-backend.vercel.app/api/ingest",
  "api_token": "your_secret_token",
  "server": "Draconiros",
  "interface": "Ethernet",
  "debug_mode": false
}
```

| Option | Description |
|--------|-------------|
| `api_url` | Backend API endpoint for data ingestion |
| `api_token` | Bearer token for authentication |
| `server` | Dofus server name (e.g., "Draconiros", "Imagiro") |
| `interface` | Network interface (e.g., "Ethernet", "Wi-Fi") |
| `debug_mode` | Enable verbose logging |

### Usage

```bash
# Run the application (may require Administrator for packet capture)
python main.py
```

**In-game workflow:**
1. Start the sniffer from the application
2. Open the Auction House (HDV) in Dofus
3. Browse items — prices are automatically captured
4. Data is batched and uploaded to the backend

### Build Standalone Executable

```bash
pyinstaller DofusTracker.spec
# Output: dist/DofusTracker.exe
```

---

## 📁 Dependencies

| Package | Purpose |
|---------|---------|
| `scapy` | Raw packet capture and filtering |
| `customtkinter` | Modern dark-themed GUI |
| `Pillow` | Image processing (icons) |
| `requests` | HTTP client for API calls |
| `colorama` | Colored terminal output |
| `pyinstaller` | Executable packaging |

---

## 🔗 Related Projects

This client is part of the **Dofus Tracker** ecosystem:

- **[Web Dashboard](https://github.com/MrPa2a/d-tracker-web)** — React frontend for data visualization
- **[Backend API](https://github.com/MrPa2a/d-tracker-backend)** — Serverless API (Node.js, TypeScript, Vercel, Supabase)

---

## 📄 License

This project is for educational and portfolio purposes. Dofus is a registered trademark of Ankama Games.
