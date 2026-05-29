@echo off
REM Build script for Email Template Batch Update Tool
REM Run this on a Windows machine with Python 3.12 installed.

echo === Installing dependencies ===
pip install -r requirements.txt
pip install pyinstaller

echo.
echo === Building executable ===
pyinstaller email_template_editor.spec --clean

echo.
echo === Done ===
echo Output folder: dist\EmailTemplateEditor\
echo Launch with:   dist\EmailTemplateEditor\EmailTemplateEditor.exe
pause
