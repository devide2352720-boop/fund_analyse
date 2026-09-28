"""Create a desktop shortcut for the fund analyzer.

The shortcut targets pythonw.exe (GUI subsystem), so no console window is
shown when the app is launched. Re-run this script to recreate the shortcut.

    python create_shortcut.py
"""

import os
import sys

import win32com.client

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
SHORTCUT_NAME = "基金分析系统.lnk"

desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
lnk_path = os.path.join(desktop, SHORTCUT_NAME)

shell = win32com.client.Dispatch("WScript.Shell")
sc = shell.CreateShortcut(lnk_path)
sc.TargetPath = PYTHONW
sc.Arguments = '"{}"'.format(os.path.join(PROJECT_DIR, "main.py"))
sc.WorkingDirectory = PROJECT_DIR
sc.Description = "基金选股与择时分析系统"
sc.Save()

print("Created:", lnk_path)
