# 👻 Zighost

### Your Minecraft Server. Your PC. Your Control.

**Zighost** is a Windows desktop application that makes managing Minecraft servers easier. Create and manage servers, monitor performance, control players, manage files, install plugins and mods, and much more, all from one place.

No need to switch between multiple tools. Manage your Minecraft server through a clean and easy-to-use interface.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📊 **Dashboard** | Monitor your server status and system resources. |
| 🖥️ **Server Management** | Create, start, stop, restart and manage Minecraft servers. |
| 🌐 **Network Tunnelling** | Connect your server to the internet using Playit.gg integration. |
| 👥 **Player Management** | View connected players and manage player actions. |
| 💻 **Live Console** | View server logs and execute commands in real time. |
| 📁 **File Manager** | Browse, edit, upload, download, rename and delete server files. |
| 🧩 **Plugins & Mods** | View and manage installed plugins and mods. |
| 💾 **Backup Manager** | Create, restore, download and manage server backups. |
| ⏰ **Scheduler** | Schedule server-related tasks and automate routine operations. |
| ⚙️ **System Settings** | Configure application preferences, notifications and other settings. |
| 🖥️ **Desktop Experience** | Use Zighost as a Windows desktop application with system tray support. |

---

## 🚀 Get Started

Choose how you want to use Zighost.

## 📥 Option 1: Download and Install

**Recommended for users**

Want to use Zighost without dealing with code? Simply download the Windows installer.

1. Visit the [Latest Release](https://github.com/Shubhamkeshri433/Zighost/releases).
2. Download the **Zighost Setup.exe** file.
3. Run the downloaded installer.
4. Follow the installation instructions.
5. Launch Zighost from your Desktop shortcut or Windows Start Menu.

That's it! You're ready to manage your Minecraft server.

**Check your download (optional).** Each release has a `SHA256SUMS.txt` file. In PowerShell, run
`Get-FileHash .\Zighost-Setup-<version>.exe -Algorithm SHA256` and compare the result with the line for that file.
The installer is not code-signed yet, so Windows may show an "unknown publisher" warning.

**Updates.** When a new version is out, Zighost shows an **Update now** button. It downloads the installer from this
repository's release, checks it against `SHA256SUMS.txt`, closes, updates and opens again. Your servers and worlds are not touched.
### 💻 Option 2: Clone the Repository

<badge color="info">For developers</badge>

Want to explore the source code, modify the application or contribute to the project?

**1. Clone the repository**

```bash
git clone https://github.com/Shubhamkeshri433/Zighost.git
```

**2. Open the project directory**

```bash
cd Zighost
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Launch Zighost**

```bash
python run.py
```

You can also use the included `start.bat` or `start-window.bat` files to launch the application on Windows.

---

## 🛠️ Built With

Zighost is developed using the following technologies:

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Starlette | Local backend API |
| HTML, CSS & JavaScript | Frontend interface |
| PyWebView | Native desktop window |
| Pystray | System tray integration |
| Uvicorn | Local application server |
| PyInstaller | Application packaging |

---

## 📂 Project Structure

```text
Zighost/
│
├── .github/
│   └── workflows/       # GitHub Actions workflows
│
├── assets/              # Application assets and resources
│
├── backend/             # Backend application logic
│
├── frontend/            # User interface
│
├── installer/           # Installer-related files
│
├── tests/               # Project tests
│
├── tools/               # Development and build tools
│
├── run.py               # Application entry point
├── requirements.txt     # Python dependencies
├── start.bat            # Launch application
├── start-window.bat     # Launch desktop window
└── zighost.spec         # Application packaging configuration
```

---

## 🔒 Privacy & Security

- Zighost runs its management backend locally on your computer.
- The local API is restricted to localhost connections.
- Server management operations are handled through the local application.
- Your server files and data remain on your machine unless you choose to connect or share them through an external service.
- No ads, no tracking and no usage counting. The only thing that can reach the developer is a support report you press Send on.
- Saved secrets (Discord webhook, playit key) are encrypted with Windows DPAPI. If encryption fails they are not saved.
- Downloads (Java, server files, playit helper, updates) are checked against the publisher's checksum where one is published.

---

## 📌 Project Status

Zighost is actively being developed. New features, improvements and bug fixes may be introduced over time.

If you encounter an issue or have an idea for a new feature, feel free to open an issue on GitHub.

---

## 🐛 Report an Issue

Found a bug or facing a problem?

- [Report a Bug](https://github.com/Shubhamkeshri433/Zighost/issues)
- [Request a Feature](https://github.com/Shubhamkeshri433/Zighost/issues)

Contributions, suggestions and feedback are welcome!

---

## 👨‍💻 Developer

**Shubham Keshri**

- GitHub: [@Shubhamkeshri433](https://github.com/Shubhamkeshri433)
- LinkedIn: [Connect with me](https://www.linkedin.com/in/shubhamkeshri433/)

---

<p align="center">
  Made with ❤️ for the Minecraft community.
  <br>
  <strong>© Zighost</strong>
</p>
