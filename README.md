# Upload to Google Drive Action

A GitHub Action to upload files to Google Drive using service account credentials with built-in retry logic for handling upload failures.

## Features

- 🔄 Automatic retry logic for handling upload failures
- 🔐 Service account authentication
- 📁 Support for both regular folders and Shared Drives
- 🎯 Configurable retry attempts and delays
- 📊 Verbose logging option for debugging
- ⚡ Composite action (no Docker required)
- 🔄 Optional overwrite of existing files

## Usage

```yaml
- name: Upload to Google Drive
  uses: tealrobotco/git-action-upload-to-gdrive@main
  with:
    credentials: ${{ secrets.DRIVE_CREDENTIALS }}
    folder-id: ${{ secrets.DRIVE_FOLDER_ID }}
    filename: "my-file.zip"
    max-attempts: 3
    retry-delay: 5
```

## Inputs

| Input          | Required | Default          | Description                                     |
| -------------- | -------- | ---------------- | ----------------------------------------------- |
| `credentials`  | Yes      | -                | Base64-encoded service account credentials JSON |
| `folder-id`    | Yes      | -                | Google Drive folder ID to upload to             |
| `filename`     | Yes      | -                | Path to the local file to upload                |
| `target-name`  | No       | Same as filename | Name for the file in Google Drive               |
| `max-attempts` | No       | `3`              | Maximum number of upload attempts               |
| `retry-delay`  | No       | `5`              | Delay in seconds between retry attempts         |
| `verbose`      | No       | `false`          | Enable verbose output for debugging             |
| `overwrite`    | No       | `false`          | Overwrite existing file with same name          |

## Outputs

| Output      | Description                              |
| ----------- | ---------------------------------------- |
| `file-id`   | Google Drive file ID of the uploaded file|
| `file-name` | Name of the uploaded file in Google Drive|

## Google Drive Setup

### 1. Create a Service Account

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"
4. Create a Service Account:
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Fill in the service account details
   - Click "Create and Continue"
   - Skip optional steps (no roles needed for basic Drive access)
   - Click "Done"

### 2. Generate Service Account Key

1. Click on the newly created service account
2. Go to the "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose "JSON" format
5. Click "Create" - this downloads a JSON file

The JSON file will look like this:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "123456789...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/..."
}
```

### 3. Base64 Encode the Credentials

You need to base64-encode the JSON credentials file before adding it to GitHub Secrets:

**Linux/Mac:**

```bash
cat service-account-key.json | base64 -w 0 > encoded-credentials.txt
```

**Windows PowerShell:**

```powershell
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((Get-Content service-account-key.json -Raw))) | Out-File -Encoding ASCII encoded-credentials.txt
```

**Online Tool:**

- Use [base64encode.org](https://www.base64encode.org/) (ensure you trust the site with your credentials)

### 4. Share Your Google Drive Folder

The service account needs access to the Google Drive folder via a shared drive.

Important: Google doesn't allow service accounts to access regular folders, only shared drives:

1. Create a new Shared Drive in Google Drive
2. Click the Shared Drive name's dropdown > "Manage members"
3. Click "Add members"
4. Add the service account email
5. Set role to "Content Manager" or "Manager" (needs write access)
6. Click "Send"

### 5. Get the Folder ID

1. Create a new folder in the Shared Drive if you don't have one yet
2. Click into the folder and copy the folder ID from the URL

The folder ID is found in the Google Drive URL:

```
https://drive.google.com/drive/folders/1A2B3C4D5E6F7G8H9I0J
                                          ^^^^^^^^^^^^^^^^^^^^
                                          This is your folder ID
```

### 6. Add Secrets to GitHub

1. Go to your GitHub repository
2. Navigate to "Settings" > "Secrets and variables" > "Actions"
3. Click "New repository secret"
4. Add two secrets:
   - **Name:** `DRIVE_CREDENTIALS`  
     **Value:** The base64-encoded credentials from step 3
   - **Name:** `DRIVE_FOLDER_ID`  
     **Value:** The folder ID from step 5

## Example Workflow

```yaml
name: Build and Upload

on:
  push:
    branches: [main]

jobs:
  build-and-upload:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Build Project
        run: |
          # Your build steps here
          zip -r build-v1.0.0.zip build/

      - name: Upload Build to Google Drive
        id: upload
        uses: tealrobotco/git-action-upload-to-gdrive@main
        with:
          credentials: ${{ secrets.DRIVE_CREDENTIALS }}
          folder-id: ${{ secrets.DRIVE_FOLDER_ID }}
          filename: "build-v1.0.0.zip"
          target-name: "Build-${{ github.sha }}.zip"
          max-attempts: 3
          retry-delay: 5
          verbose: true
          overwrite: false

      - name: Output File Info
        run: |
          echo "Uploaded file ID: ${{ steps.upload.outputs.file-id }}"
          echo "Uploaded file name: ${{ steps.upload.outputs.file-name }}"
```

## Retry Logic

This action includes built-in retry logic to handle transient upload failures. The action will:

1. Attempt to upload the file
2. If the upload fails, wait for the specified `retry-delay` seconds
3. Retry up to `max-attempts` times
4. On success, verify the file exists in Google Drive
5. On failure, exit with an error

This is particularly useful for handling network issues or temporary Google Drive API errors.

## Overwrite Behavior

By default, the action will fail if a file with the same name already exists in the target folder. To overwrite existing files, set `overwrite: true`:

```yaml
- name: Upload to Google Drive
  uses: tealrobotco/git-action-upload-to-gdrive@main
  with:
    credentials: ${{ secrets.DRIVE_CREDENTIALS }}
    folder-id: ${{ secrets.DRIVE_FOLDER_ID }}
    filename: "build.zip"
    overwrite: true  # Will replace existing file
```

## Troubleshooting

### Permission Denied

- Verify the service account has write access to the folder (needs "Content Manager" or "Manager" role)
- Verify the folder ID is correct
- Ensure the service account is added to the Shared Drive with appropriate permissions

### File Already Exists

- If you see "File already exists" error, either:
  - Set `overwrite: true` to replace the existing file
  - Use a different `target-name` to avoid conflicts
  - Manually delete the existing file from Google Drive

### Authentication Errors

- Verify the credentials are correctly base64-encoded
- Ensure the Google Drive API is enabled in your Google Cloud project
- Check that the service account key hasn't been deleted or revoked
- Verify the secret is named correctly in GitHub

### Upload Failures

- Check your internet connectivity and GitHub Actions network status
- Increase `max-attempts` and `retry-delay` for large files
- Enable `verbose: true` to see detailed error messages
- Verify the file exists at the specified path before upload

### Shared Drive Issues

- Ensure the service account is added as a member of the Shared Drive
- Verify you're using the folder ID from within the Shared Drive, not the Shared Drive ID itself
- The service account needs at least "Content Manager" role for uploads

## License

This action is available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
