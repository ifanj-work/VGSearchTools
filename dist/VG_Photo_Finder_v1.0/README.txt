Vivagoal Photo Finder - Setup Guide (Windows)

Overview
- LAN-based photo finder with fast search and previews.
- Scans one or more folders (UNC or drive letters) and builds a local catalog and thumbnail cache.
- Serves a web UI to your team over your local network.

What is included
- App: Flask + Waitress server (app.py / start_server.bat)
- Index and cache: photo_catalog.json, photo_catalog.db, thumbs/ (created at runtime)
- Logs: logs/ and server_start.log (created at runtime)
- Config: app_config.json (created when you save settings in the UI)

Requirements
- Windows 10/11 PC with access to your photo sources (UNC paths recommended)
- Python 3.12 (recommended) or Python 3.14 (supported)
  - 3.12 enables cached thumbnails (faster). 3.14 works but serves originals in the grid (higher bandwidth).

Quick Start (recommended)
1) Open Command Prompt and go to the project folder:
   cd /d "C:\VG Photo Search Tools"  (use your actual path)
2) Run the launcher (auto-creates venv, installs deps, starts server, opens browser):
   start_server.bat 5000
3) The browser opens at http://localhost:5000

Manual Run (alternative)
1) Create/activate venv and install dependencies:
   py -3.12 -m venv .venv   (or py -3.14 if you prefer)
   .venv\Scripts\activate.bat
   python -m pip install -U pip setuptools wheel
   pip install -r requirements.txt
2) Run the app:
   python app.py
3) Open http://localhost:5000

Configure Sources (the folders to scan)
- In the UI (home page), find "Sources" and paste one or more paths separated by semicolons, for example:
  \\172.16.0.25\data\MULTIMEDIA ARCHIVE\VIVAGOAL\LIPUTAN
  Z:\; G:\; \\SERVER\Share\Photos
- Click "Save Sources & Rescan". The status at the top shows scan progress. Search when scan finishes.
- Recommended: Use UNC paths for scheduled tasks/services. Mapped drives (Z:, G:) may not exist for service accounts.

Incremental Rescans
- The first scan builds photo_catalog.json and photo_catalog.db.
- Subsequent rescans re-use existing entries and only rebuild items whose size/modified time changed.

Share With Your Team
- Find the host PC's IP (ipconfig). Others connect to: http://<HOST_IP>:5000
- Optional: Ask IT to create a DNS alias (photo.vivagoal.local -> host IP).

Production Service (auto-start at logon)
- Open PowerShell in the project folder and run:
  powershell -ExecutionPolicy Bypass -File scripts/create_tasks.ps1 -Port 5000 -CreateFirewall
- This creates:
  - Scheduled Task "Vivagoal Photo Finder": runs the server at user logon using Waitress
  - Scheduled Task "Vivagoal Photo Finder Weekly Rescan": triggers a weekly rescan (defaults Sunday 03:00)
- Start immediately:
  Start-ScheduledTask -TaskName "Vivagoal Photo Finder"

Firewall
- Allow inbound TCP 5000 (one-time, Admin PowerShell):
  New-NetFirewallRule -DisplayName "Vivagoal Photo Finder" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5000 -Profile Domain

Logo and Title (optional)
- Place your logo in static/img/, e.g. static/img/my_logo.png
- Update via API (PowerShell example):
  Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://localhost:5000/config -ContentType 'application/json' -Body '{"ui_logo_url":"/static/img/my_logo.png","ui_title":"Vivagoal Photo Finder","persist":true}'
- Refresh the page to see the logo next to the title.

Health and Maintenance
- Health endpoint: http://localhost:5000/health (source availability, counts, scan state)
- Rescan manually: POST http://localhost:5000/rescan (or click Rescan in the UI)
- Back up: photo_catalog.json and thumbs/ (optional; they can be rebuilt)

Notes on Python versions
- Python 3.12: Uses Pillow for 512px cached thumbnails (fast, low bandwidth)
- Python 3.14: Pillow wheels are not available yet; the grid serves originals. EXIF dates read using pure-Python exifread.

Troubleshooting
- start_server.bat not recognized in PowerShell -> prefix with .\
  .\start_server.bat 5000
- Browser does not open automatically -> navigate to http://localhost:5000
- No results after start -> Click Rescan, wait until status shows "done"
- Sources missing in /health -> Ensure the UNC paths are correct and accessible by the current user (and the Task Scheduler user if running as a task)
- "Open in Explorer" runs on the host PC (not client browsers) by design

Uninstall / Update
- Stop the scheduled task (if used):
  Unregister-ScheduledTask -TaskName "Vivagoal Photo Finder" -Confirm:$false
  Unregister-ScheduledTask -TaskName "Vivagoal Photo Finder Weekly Rescan" -Confirm:$false
- Delete the project folder. To update, replace files and run start_server.bat again.

Docker (portable, reproducible)
- Build the image (from project root):
  docker build -t vivagoal-photo-finder:latest .
- Run the container, mounting a persistent data dir for catalog and thumbs:
  docker run -d ^
    -p 5000:5000 ^
    -v /host/path/catalog:/app ^
    -v /host/path/thumbs:/app/thumbs ^
    --name vivagoal-photo-finder ^
    vivagoal-photo-finder:latest

