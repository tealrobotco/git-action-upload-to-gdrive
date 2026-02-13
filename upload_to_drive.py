#!/usr/bin/env python3
"""
Upload files to Google Drive with retry logic.

This script authenticates with Google Drive using a service account and uploads
a specified file to a folder, with built-in retry logic for handling failures.
"""

import os
import base64
import json
import time
import argparse
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Upload files to Google Drive using service account credentials.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload using environment variables
  python upload_to_drive.py --filename "Build-StandaloneWindows64-v0.1.8.zip"
  
  # Upload with explicit credentials
  python upload_to_drive.py --filename "Build-StandaloneWindows64-v0.1.8.zip" \\
    --credentials-base64 "base64_encoded_creds" \\
    --folder-id "1234567890abcdef"
  
  # Upload with custom retry settings and overwrite
  python upload_to_drive.py --filename "Build-StandaloneWindows64-v0.1.8.zip" \\
    --max-attempts 15 --retry-delay 45 --overwrite
        """
    )
    
    parser.add_argument(
        '--filename',
        required=True,
        help='Path to the local file to upload to Google Drive'
    )
    
    parser.add_argument(
        '--credentials-base64',
        help='Base64-encoded service account credentials JSON (default: from DRIVE_CREDENTIALS env var)'
    )
    
    parser.add_argument(
        '--folder-id',
        help='Google Drive folder ID to upload to (default: from DRIVE_FOLDER_ID env var)'
    )
    
    parser.add_argument(
        '--target-name',
        help='Name for the file in Google Drive (default: same as local filename)'
    )
    
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=3,
        help='Maximum number of attempts (default: 3)'
    )
    
    parser.add_argument(
        '--retry-delay',
        type=int,
        default=5,
        help='Delay in seconds between attempts (default: 5)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing file with same name'
    )
    
    return parser.parse_args()


def get_credentials(credentials_base64):
    """Decode and load service account credentials."""
    try:
        creds_json = base64.b64decode(credentials_base64).decode('utf-8')
        creds_dict = json.loads(creds_json)
        
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        
        return credentials
    except Exception as e:
        print(f"Error decoding credentials: {e}", file=sys.stderr)
        sys.exit(1)


def list_folder_files(service, folder_id, verbose=False):
    """List all files in the specified folder for debugging."""
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, createdTime, size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            print(f"Found {len(files)} file(s) in folder:")
            for f in files:
                size = f.get('size', 'unknown')
                created = f.get('createdTime', 'unknown')
                if verbose:
                    print(f"  - {f['name']} (ID: {f['id']}, Size: {size} bytes, Created: {created})")
                else:
                    print(f"  - {f['name']} (created: {created})")
        else:
            print("No files found in folder")
            
        return files
    except Exception as e:
        print(f"Error listing folder files: {e}", file=sys.stderr)
        return []


def find_existing_file(service, folder_id, filename):
    """Find an existing file with the same name in the folder."""
    try:
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        return files[0] if files else None
    except Exception as e:
        print(f"Error searching for existing file: {e}", file=sys.stderr)
        return None


def upload_file(service, file_path, target_name, folder_id, overwrite=False, verbose=False):
    """Upload a file to Google Drive."""
    try:
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            return None
        
        file_size = os.path.getsize(file_path)
        print(f"Uploading {file_path} ({file_size} bytes) as '{target_name}'...")
        
        # Check if file already exists
        existing_file = find_existing_file(service, folder_id, target_name)
        
        if existing_file:
            if overwrite:
                print(f"File '{target_name}' already exists (ID: {existing_file['id']}). Overwriting...")
                file_metadata = {'name': target_name}
                media = MediaFileUpload(file_path, resumable=True)
                
                file = service.files().update(
                    fileId=existing_file['id'],
                    media_body=media,
                    supportsAllDrives=True
                ).execute()
                
                print(f"Successfully updated file '{target_name}' (ID: {file.get('id')})")
                return file.get('id')
            else:
                print(f"Error: File '{target_name}' already exists (ID: {existing_file['id']})", file=sys.stderr)
                print("Use --overwrite flag to replace the existing file", file=sys.stderr)
                return None
        
        # Upload new file
        file_metadata = {
            'name': target_name,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, resumable=True)
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,size',
            supportsAllDrives=True
        ).execute()
        
        print(f"Successfully uploaded '{target_name}' (ID: {file.get('id')})")
        if verbose:
            print(f"  Size: {file.get('size', 'unknown')} bytes")
        
        return file.get('id')
    except HttpError as e:
        print(f"HTTP error during upload: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error uploading file: {e}", file=sys.stderr)
        return None


def upload_with_retry(service, file_path, target_name, folder_id, max_attempts, retry_delay, overwrite, verbose):
    """Upload a file to Google Drive with retry logic."""
    print(f"Uploading file: {file_path}")
    print(f"To folder ID: {folder_id}")
    
    for attempt in range(max_attempts):
        print(f"\nAttempt {attempt + 1}/{max_attempts}")
        
        try:
            file_id = upload_file(service, file_path, target_name, folder_id, overwrite, verbose)
            
            if file_id:
                # Verify the upload by checking if file exists
                try:
                    file_info = service.files().get(
                        fileId=file_id,
                        fields='id,name,size',
                        supportsAllDrives=True
                    ).execute()
                    
                    print(f"\nUpload verified successfully!")
                    if verbose:
                        print(f"  File ID: {file_info['id']}")
                        print(f"  File name: {file_info['name']}")
                        print(f"  File size: {file_info.get('size', 'unknown')} bytes")
                    
                    # Output file ID for GitHub Actions
                    with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
                        f.write(f"file-id={file_id}\n")
                    
                    return True
                except Exception as e:
                    print(f"Warning: Upload succeeded but verification failed: {e}", file=sys.stderr)
                    return True
            else:
                print("Upload failed.")
                if not overwrite and attempt == 0:
                    # If it failed due to existing file, don't retry
                    print("Not retrying due to existing file conflict.")
                    return False
                
                if attempt < max_attempts - 1:
                    print(f"Waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
        except Exception as e:
            print(f"Error during upload: {e}", file=sys.stderr)
            if attempt < max_attempts - 1:
                print(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
    
    print(f"\nFailed to upload {file_path} after {max_attempts} attempts", file=sys.stderr)
    return False


def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Get credentials from argument or environment variable
    credentials_base64 = args.credentials_base64 or os.environ.get('DRIVE_CREDENTIALS')
    if not credentials_base64:
        print("Error: Credentials not provided. Use --credentials-base64 or set DRIVE_CREDENTIALS env var",
              file=sys.stderr)
        sys.exit(1)
    
    # Get folder ID from argument or environment variable
    folder_id = args.folder_id or os.environ.get('DRIVE_FOLDER_ID')
    if not folder_id:
        print("Error: Folder ID not provided. Use --folder-id or set DRIVE_FOLDER_ID env var",
              file=sys.stderr)
        sys.exit(1)
    
    # Determine target name
    target_name = args.target_name or os.path.basename(args.filename)
    
    # Authenticate and build service
    credentials = get_credentials(credentials_base64)
    service = build('drive', 'v3', credentials=credentials)
    
    # Upload the file
    success = upload_with_retry(
        service=service,
        file_path=args.filename,
        target_name=target_name,
        folder_id=folder_id,
        max_attempts=args.max_attempts,
        retry_delay=args.retry_delay,
        overwrite=args.overwrite,
        verbose=args.verbose
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
