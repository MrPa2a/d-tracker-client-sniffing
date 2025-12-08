# 🕵️ Dofus Tracker Client V3 (Sniffer)

The advanced data collection client for Dofus Tracker. It uses packet sniffing (Scapy) to intercept market data directly from the game network traffic, ensuring 100% accuracy without OCR.

## ⚖️ Disclaimer

**This project is developed strictly for educational purposes.**

It is designed to explore network traffic analysis and data visualization. It is **not a bot** and does not automate any actions in the game.

**Usage Warning:**
The use of third-party tools to analyze game data may be against the Terms of Service of Ankama Games.
*   **I strongly advise against using this tool on official servers.**
*   I am not responsible for any consequences resulting from the use of this software.
*   Please respect the game and its community. Use this project only to learn new things.

*Dofus is a registered trademark of Ankama Games. This project is not affiliated with Ankama Games.*

## ✨ Features

*   **Packet Sniffing**: Intercepts `ExchangeTypesItemsExchangerDescriptionForUserMessage` packets to read market prices.
*   **No OCR**: Eliminates errors associated with screen reading.
*   **Background Operation**: Can run minimized while you browse the market.
*   **Automatic Upload**: Sends data to the Dofus Tracker Backend API.
*   **Modern UI**: Built with `CustomTkinter` for a sleek look.

## ⚠️ Prerequisites

*   **Npcap**: Required for packet capture on Windows.
    *   Download: [https://npcap.com/](https://npcap.com/)
    *   **Important**: Check **"Install Npcap in WinPcap API-compatible Mode"** during installation.

## 🚀 Installation

1.  **Create Virtual Environment**:
    ```powershell
    python -m venv venv
    .\venv\Scripts\Activate
    ```

2.  **Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    Edit `config.json`:
    ```json
    {
        "api_url": "https://your-backend-url.vercel.app/api/ingest",
        "api_token": "your_secret_token",
        "interface": "Ethernet" 
    }
    ```
    *   `interface`: The network interface name (e.g., "Ethernet", "Wi-Fi").

## 🎮 Usage

1.  **Start the Client**:
    ```powershell
    python main.py
    ```
    *Note: You might need to run as Administrator depending on network permissions.*

2.  **In Game**:
    *   Open the Auction House (HDV).
    *   Search for items.
    *   The client will automatically detect and log the prices.

## 🏗️ Build Executable

To create a standalone `.exe` file:
```powershell
pyinstaller DofusTracker.spec
```
The output will be in the `dist/` folder.
