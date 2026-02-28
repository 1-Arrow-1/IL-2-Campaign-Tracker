"""
Entry point for Career Service Record (Career_Service_Record.exe).

Sets CSR_APP_MODE=career before any other import so that Config reads it
correctly.  Everything else delegates to the shared app.py / main().
"""

import os
os.environ.setdefault('CSR_APP_MODE', 'career')

from campaign_service_record.app import main  # noqa: E402

if __name__ == '__main__':
    main()
