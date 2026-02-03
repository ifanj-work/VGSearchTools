$ReleaseName = "VG_Photo_Finder_v1.0"
$Dest = "dist\$ReleaseName"
$ZipFile = "dist\$ReleaseName.zip"

Write-Host "Creating release package: $ReleaseName"

# 1. Clean up old build
if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
if (Test-Path $ZipFile) { Remove-Item -Force $ZipFile }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
New-Item -ItemType Directory -Force -Path "dist" | Out-Null

# 2. Files to Include
$Files = @(
    "start_server.bat",
    "app.py",
    "catalog.py",
    "config.py",
    "run_server.py",
    "requirements.txt",
    "README.txt"
)

$Folders = @(
    "templates",
    "static",
    "scripts"
)

# 3. Copy Files
foreach ($f in $Files) {
    if (Test-Path $f) {
        Copy-Item $f $Dest
    } else {
        Write-Warning "Missing file: $f"
    }
}

# 4. Copy Folders
foreach ($d in $Folders) {
    if (Test-Path $d) {
        Copy-Item -Recurse $d "$Dest\$d"
    }
}

# 5. Zip it up
Write-Host "Zipping files..."
Compress-Archive -Path "$Dest\*" -DestinationPath $ZipFile -Force

# 6. Open folder
Invoke-Item "dist"

Write-Host "Done! Zip file created at: $ZipFile"
