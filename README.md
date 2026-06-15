# Email Template Batch Update Tool

A desktop app for managing, editing, and sending HTML email templates.  
Built with Python + PyQt6.

---

## Features

- **Browse & preview** a folder of `.html` email templates
- **Edit Mode** — click any element to select it; edit inline styles, attributes, or text directly in the live preview
- **Element Editor Panel** — right-side panel with collapsible sections:
  - **Attributes** — edit any HTML attribute of the selected element
  - **Inline Style** — live CSS editor; changes push to the element in real time
  - **AI Prompt** — describe a change in plain text and let GPT-4o rewrite the element
  - **Style Sets** — apply saved inline-style presets with one click
  - **CSS Classes** — manage reusable CSS classes (with `@media` support); Outlook-safe (one class per element)
- **Code Mode** — raw HTML editor with syntax highlighting and line numbers
- **Merge** — apply a guide template's structure to any template via a two-panel visual picker
- **Send** — dispatch via SMTP (all platforms) or Outlook COM (Windows); supports multiple recipients
- **Open in Browser** — preview the current template in your default browser
- **Copy / Paste elements** — copy an element's outer HTML to the clipboard and paste it onto another element
- **Ctrl+Click** — delete any element in Edit Mode

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
cd email-templates-editor

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
cd email-templates-editor

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

## Guide Folder & Merge

The merge workflow applies the header/footer structure from a guide template to any working template.

The guide template uses `<!-- SECTION:X -->` markers to define regions:

| Marker | Purpose |
|---|---|
| `SECTION:HEADER` | Logo, title, banner |
| `SECTION:CONTENT` | Body — replaced during merge |
| `SECTION:PREFOOTER` | Legal / preference link row |
| `SECTION:FOOTER` | Links, address, unsubscribe |

To use the merge workflow:

1. Click **Guide Folder…** in the top bar → select a folder containing one or more guide templates
2. Open any working template from the sidebar
3. Click **Merge with Guide**
4. Choose a guide template from the dropdown in the merge dialog
5. Click rows in the source template to select content to keep (green outline)
6. Preview updates live on the right → **Merge & Save**

---

## AI Element Editing

Requires an OpenAI API key (uses `gpt-4o` via the Chat Completions API — no extra Python package needed).

1. Enter **Edit Mode** and click an element to select it
2. In the **AI PROMPT** section of the Element Editor, type your instruction  
   e.g. *"make this button larger with a red background"*
3. Click **⚙ API Key** to save your key (stored at `~/.email_template_openai.json`)
4. Click **Run AI** — the element is replaced in place with the AI-generated HTML

---

## Style Sets & CSS Classes

Both are saved globally (per user, not per project) and persist across sessions.

**Style Sets** are named inline-style snippets you can stamp onto any selected element with one click.  
Stored at `~/.email_template_styles.json`.

**CSS Classes** are reusable CSS rules (with optional `@media` breakpoints) that get injected as `<style>` tags when applied. Due to Outlook restrictions, only one managed class can be active on an element at a time.  
Stored at `~/.email_template_classes.json`.

---

## Project Structure

```
email-templates-editor/
├── main.py                             # Entry point
├── guide-template.html                 # Example guide template
├── demo/                               # Example HTML templates
│   ├── welcome.html
│   ├── password-reset.html
│   ├── order-confirmation.html
│   ├── newsletter.html
│   └── subscription-expiry.html
└── app/
    ├── styles.py                       # Shared colour constants
    ├── style_store.py                  # Persistent storage for style sets, classes, OpenAI key
    ├── merger.py                       # Guide template merge logic
    ├── email_sender.py                 # SMTP + Outlook COM backend
    ├── window.py                       # Main window
    └── widgets/
        ├── topbar.py                   # Path bar + Open/Guide Folder buttons
        ├── sidebar.py                  # Template file list
        ├── preview.py                  # Preview / Edit / Code pane + Element Editor
        ├── code_editor.py              # Syntax-highlighted HTML editor
        ├── merge_dialog.py             # Two-panel merge UI
        ├── send_dialog.py              # Email compose dialog
        ├── smtp_settings_dialog.py     # SMTP configuration form
        ├── multi_email_input.py        # Multi-recipient email input widget
        ├── css_class_dialog.py         # CSS class create/edit dialog
        ├── openai_settings_dialog.py   # OpenAI API key dialog
        └── style_sets_dialog.py        # Style set create/edit dialog
```

---

## Persistent Data (outside the repo)

| File | Contents |
|---|---|
| `~/.config/email-templates-tool/smtp.json` | SMTP credentials |
| `~/.config/email-templates-tool/prefs.json` | Last-used send preferences |
| `~/.email_template_styles.json` | Saved style sets |
| `~/.email_template_classes.json` | Saved CSS classes |
| `~/.email_template_openai.json` | OpenAI API key |
| `~/.email_template_panel.json` | Element Editor section collapse state |

None of these files are committed to the repository.

---

## Security Notes

- SMTP credentials are stored in plain text at `~/.config/email-templates-tool/smtp.json`.  
  This file is user-local and outside the repository.
- The `.gitignore` blocks `smtp.json` and other credential patterns from being committed.
- No credentials are ever written inside the project directory.
