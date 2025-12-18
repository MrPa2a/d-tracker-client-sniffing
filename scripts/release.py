import os
import re
import sys
import argparse
import subprocess
import json
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Manually load .env if python-dotenv is not installed
    env_path = Path(".env")
    if env_path.exists():
        print("ℹ️  Loading .env manually (python-dotenv not installed)")
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value.strip()

# Configuration
CONSTANTS_FILE = Path("core/constants.py")
BUILD_SCRIPT = "build_exe.bat"
GIST_ID = "8dc2264afcc7fc0bdcd38dbd484ebf21"  # From core/constants.py
DROPBOX_TARGET_PATH = "/DofusTracker.zip"
DIST_ZIP_PATH = Path("dist/DofusTracker.zip")

def get_current_version():
    """Reads the current version from core/constants.py"""
    if not CONSTANTS_FILE.exists():
        print(f"❌ Error: {CONSTANTS_FILE} not found.")
        sys.exit(1)
        
    content = CONSTANTS_FILE.read_text(encoding="utf-8")
    match = re.search(r'VERSION = "(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("❌ Error: Could not find VERSION in constants.py")
        sys.exit(1)
        
    return match.groups()

def bump_version(major, minor, patch, bump_type):
    """Calculates the new version based on the bump type."""
    major, minor, patch = int(major), int(minor), int(patch)
    
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        print(f"❌ Error: Unknown bump type '{bump_type}'")
        sys.exit(1)
        
    return f"{major}.{minor}.{patch}"

def update_constants_file(new_version):
    """Updates core/constants.py with the new version."""
    content = CONSTANTS_FILE.read_text(encoding="utf-8")
    new_content = re.sub(
        r'VERSION = "\d+\.\d+\.\d+"',
        f'VERSION = "{new_version}"',
        content
    )
    CONSTANTS_FILE.write_text(new_content, encoding="utf-8")
    print(f"✅ Updated {CONSTANTS_FILE} to version {new_version}")

def run_build():
    """Runs the build script."""
    print("🔨 Building executable...")
    try:
        subprocess.run([BUILD_SCRIPT, "--no-pause"], check=True, shell=True)
        print("✅ Build successful.")
    except subprocess.CalledProcessError:
        print("❌ Build failed.")
        sys.exit(1)

def upload_to_dropbox(file_path, target_path):
    """Uploads the file to Dropbox and returns a shared link."""
    try:
        import dropbox
        from dropbox.files import WriteMode
    except ImportError:
        print("❌ Error: 'dropbox' library not installed. Run 'pip install dropbox'")
        return None

    # Check for Refresh Token (Preferred)
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")
    app_key = os.environ.get("DROPBOX_APP_KEY")
    app_secret = os.environ.get("DROPBOX_APP_SECRET")
    
    # Check for Access Token (Legacy/Short-lived)
    access_token = os.environ.get("DROPBOX_TOKEN")

    if refresh_token and app_key and app_secret:
        print("🔑 Using Dropbox Refresh Token authentication...")
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )
    elif access_token:
        print("🔑 Using Dropbox Access Token authentication...")
        dbx = dropbox.Dropbox(access_token)
    else:
        print("❌ Error: No valid Dropbox credentials found in environment variables.")
        return None

    print(f"☁️ Uploading {file_path} to Dropbox...")
    
    with open(file_path, "rb") as f:
        dbx.files_upload(f.read(), target_path, mode=WriteMode("overwrite"))
        
    print("✅ Upload complete.")
    
    # Create or get shared link
    try:
        shared_link_metadata = dbx.sharing_create_shared_link_with_settings(target_path)
        url = shared_link_metadata.url
    except dropbox.exceptions.ApiError as e:
        # Link might already exist
        if e.error.is_shared_link_already_exists():
            links = dbx.sharing_list_shared_links(path=target_path).links
            url = links[0].url
        else:
            raise e
            
    # Change dl=0 to dl=1 for direct download
    direct_url = url.replace("?dl=0", "?dl=1")
    print(f"🔗 Direct Download URL: {direct_url}")
    return direct_url

def update_gist(gist_id, version, url, token):
    """Updates the Gist with the new version info."""
    print(f"📝 Updating Gist {gist_id}...")
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "files": {
            "version.json": {
                "content": json.dumps({
                    "version": version,
                    "url": url
                }, indent=2)
            }
        }
    }
    
    response = requests.patch(f"https://api.github.com/gists/{gist_id}", headers=headers, json=data)
    
    if response.status_code == 200:
        print("✅ Gist updated successfully.")
    else:
        print(f"❌ Failed to update Gist: {response.status_code} {response.text}")

def main():
    parser = argparse.ArgumentParser(description="Release automation script for Dofus Tracker")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], required=True, help="Version bump type")
    parser.add_argument("--skip-upload", action="store_true", help="Skip upload and Gist update")
    
    args = parser.parse_args()
    
    # 1. Check Environment Variables
    github_token = os.environ.get("GITHUB_TOKEN")
    
    # Check Dropbox Auth (Either Token or Refresh Token flow)
    has_dropbox_auth = os.environ.get("DROPBOX_TOKEN") or (
        os.environ.get("DROPBOX_REFRESH_TOKEN") and 
        os.environ.get("DROPBOX_APP_KEY") and 
        os.environ.get("DROPBOX_APP_SECRET")
    )
    
    if not args.skip_upload:
        if not has_dropbox_auth:
            print("⚠️ Warning: Dropbox credentials not found (Need DROPBOX_TOKEN or Refresh Token vars).")
        if not github_token:
            print("⚠️ Warning: GITHUB_TOKEN not found in environment variables.")
            
        if not has_dropbox_auth or not github_token:
            print("ℹ️  You can use --skip-upload to only build locally.")
            response = input("Do you want to continue without uploading? (y/n): ")
            if response.lower() != 'y':
                sys.exit(1)
            args.skip_upload = True

    # 2. Bump Version
    current_major, current_minor, current_patch = get_current_version()
    print(f"ℹ️  Current version: {current_major}.{current_minor}.{current_patch}")
    
    new_version = bump_version(current_major, current_minor, current_patch, args.bump)
    print(f"🚀 Starting release process for v{new_version}")
    
    update_constants_file(new_version)
    
    # 3. Build
    run_build()
    
    # 4. Upload & Update Gist
    if not args.skip_upload:
        if not DIST_ZIP_PATH.exists():
            print(f"❌ Error: {DIST_ZIP_PATH} not found after build.")
            sys.exit(1)
            
        download_url = upload_to_dropbox(DIST_ZIP_PATH, DROPBOX_TARGET_PATH)
        
        if download_url:
            update_gist(GIST_ID, new_version, download_url, github_token)
        else:
            print("❌ Upload failed, skipping Gist update.")
    else:
        print("⏩ Skipping upload and Gist update.")
        
    print(f"✨ Release v{new_version} completed!")

if __name__ == "__main__":
    main()
