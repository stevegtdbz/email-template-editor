# Email Template Batch Update Tool

A desktop app for managing, editing, and sending HTML email templates.  
Built with Python + PyQt6.

---

## Features

- **Browse & preview** a folder of `.html` email templates
- **Edit Mode** — inline text editing, element deletion, font/colour formatting
- **Code Mode** — raw HTML editor with syntax highlighting and line numbers
- **Merge** — apply a guide template's header/footer structure to any template
- **Send** — dispatch via SMTP or Outlook COM (Windows)

---

## Requirements

- Python **3.10** or newer
- Internet access for the initial `pip install` (packages ~250 MB total)

---

## Installation

### Linux

```bash
# 1. Clone the repo
git clone <repo-url>
cd email-templates

# 2. Create a virtual environment
python3 -m venv .venv

# 3. Activate it
source .venv/bin/activate

# 4. Install dependencies
pip install PyQt6 PyQt6-WebEngine
```

### Windows

```bat
REM 1. Clone the repo
git clone <repo-url>
cd email-templates

REM 2. Create a virtual environment
python -m venv .venv

REM 3. Activate it
.venv\Scripts\activate

REM 4. Install dependencies
pip install PyQt6 PyQt6-WebEngine

REM 5. (Optional) Outlook COM support
pip install pywin32
```

> **Windows note:** `pywin32` is only needed if you want to send emails via Outlook.  
> Without it, SMTP is available on all platforms.

---

## Running

```bash
# Linux / macOS
.venv/bin/python main.py

# Windows
.venv\Scripts\python main.py
```

---

## SMTP Setup

Credentials are configured inside the app:

1. Open a template → click **Send Email**
2. Click **Configure SMTP…**
3. Enter your SMTP host, port, username, and password → **Test Connection** → **Save**

Settings are saved to `~/.config/email-templates-tool/smtp.json`  
(outside the repo — never committed).

Common provider settings:

| Provider | Host | Port | TLS |
|---|---|---|---|
| Gmail | `smtp.gmail.com` | 587 | ✅ STARTTLS |
| Outlook / Office 365 | `smtp.office365.com` | 587 | ✅ STARTTLS |
| SendGrid | `smtp.sendgrid.net` | 587 | ✅ STARTTLS |
| Mailgun | `smtp.mailgun.org` | 587 | ✅ STARTTLS |

> **Gmail users:** generate an [App Password](https://myaccount.google.com/apppasswords) instead of your account password.

---

## Guide Template & Merge

`guide-template.html` is the master layout.  
It uses `<!-- SECTION:X -->` markers to define regions:

| Marker | Purpose |
|---|---|
| `SECTION:HEADER` | Logo, title, banner |
| `SECTION:CONTENT` | Body — replaced during merge |
| `SECTION:PREFOOTER` | Legal / preference link row |
| `SECTION:FOOTER` | Links, address, unsubscribe |

To use the merge workflow:

1. Click **Load Guide…** in the toolbar → select `guide-template.html`
2. Open any template from the sidebar
3. Click **Merge with Guide**
4. Click rows in the source template to select content to keep (green outline)
5. Preview updates live on the right → **Merge & Save**

---

## Project Structure

```
email-templates/
├── main.py                         # Entry point
├── guide-template.html             # Master layout template
├── demo/                           # Example HTML templates
│   ├── welcome.html
│   ├── password-reset.html
│   ├── order-confirmation.html
│   ├── newsletter.html
│   └── subscription-expiry.html
└── app/
    ├── styles.py                   # Shared colour constants
    ├── merger.py                   # Guide template merge logic
    ├── email_sender.py             # SMTP + Outlook COM backend
    ├── window.py                   # Main window
    └── widgets/
        ├── topbar.py               # Path bar + Load Guide button
        ├── sidebar.py              # File list
        ├── preview.py              # Preview / Edit / Code pane
        ├── code_editor.py          # Syntax-highlighted HTML editor
        ├── merge_dialog.py         # Two-panel merge UI
        ├── send_dialog.py          # Email compose dialog
        └── smtp_settings_dialog.py # SMTP configuration form
```

---

## Security Notes

- SMTP credentials are stored in plain text at `~/.config/email-templates-tool/smtp.json`.  
  This file is user-local and outside the repository.
- The `.gitignore` blocks `smtp.json` and other credential patterns from being committed.
- No credentials are ever written inside the project directory.
