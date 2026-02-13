# 📸 VG Photo Search Tools

> A powerful, fast, and local photo & video search engine for huge archives.

**VG Photo Search Tools** is a self-hosted web application designed to index and search through massive collections of photos and videos across local drives and network shares. It provides a lightning-fast search interface, advanced filtering, and instant visual previews.

## ✨ Features

- **🚀 Blazing Fast Search**: Indexed metadata search (SQLite + FTS5) for instant results even with millions of files.
- **🖼️ Universal Format Support**:
  - **Images**: JPG, PNG, WebP, TIFF, BMP
  - **Videos**: MP4, MOV, AVI, MKV, WMV, WebM (with thumbnail previews)
  - **Design**: PSD (Adobe Photoshop) with composite previews
- **🔍 Advanced Filtering**:
  - Filter by Year and Month
  - Filter by File Type (Image, Video, PSD)
  - Sort by Date (Newest/Oldest) or Filename (A-Z/Z-A)
- **👀 Visual Browsing**:
  - **Grid View**: Responsive masonry grid for visual scanning.
  - **List View**: Detailed list with metadata (Size, Date, Path).
  - **Context Actions**: "Open in Explorer", Download, View Full Size.
- **📂 Local & Network Scanning**:
  - Add multiple source directories (Local drives, LAN shares, Google Drive mounted paths).
  - Optional subfolder filtering (e.g., only index folders containing "Selects").
- **⚡ Background Indexing**: scan process runs in the background without blocking the UI.

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.8+
- [FFmpeg](https://ffmpeg.org/download.html) (Optional, required for video thumbnail generation)

### Installation

1.  **Clone the repository**:

    ```bash
    git clone https://github.com/ifanj-work/VGSearchTools.git
    cd VGSearchTools
    ```

2.  **Create a virtual environment**:

    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**:
    - The app will automatically create a `app_config.json` on first run.
    - You can configure source directories via the UI ("Settings" button) or by editing `app_config.json`.

### Running the App

```bash
python app.py
```

_Note: For production use, it is recommended to use a WSGI server like `waitress`._

## 🐳 Docker Support

(Coming soon)

## 🖥️ Usage

1.  Open your browser to `http://localhost:5000`.
2.  Click the **⚙️ Settings** icon to add your photo folders (e.g., `D:\Photos`, `\\NAS\Share`).
3.  Click **Run Scan** to start indexing.
4.  Use the search bar and filters to find your media!

## 📜 License

Private / Internal Use.
