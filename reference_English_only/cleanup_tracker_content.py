#!/usr/bin/env python3
r"""
IL-2 Campaign Tracker - Content Cleanup Utility

Removes tracker-generated content (Events, Debriefings) from info.locale=*.txt files.
Used by the uninstaller to clean up campaign files.

Usage:
    cleanup_tracker_content.exe --uninstall --il2-path "C:\Path\To\IL2"
    cleanup_tracker_content.exe --uninstall  (auto-detect from registry)
    
Exit codes:
    0 = Success (or nothing to clean)
    1 = Error
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Tuple, Optional

# Import from utils
from utils.info_locale import (
    find_all_info_locale_files,
    detect_info_locale_encoding,
    decode_and_clean_info_locale,
    TRACKER_SECTION_HEADER_PATTERN,
)

# Try to import regex (used by info_locale)
try:
    import regex
    REGEX_MODULE = regex
except ImportError:
    import re
    REGEX_MODULE = re


def get_il2_path_from_registry() -> Optional[str]:
    r"""
    Try to get IL-2 path from Windows registry.
    The installer stores it at: HKLM\Software\IL-2 Great Battles SP Campaign Tracker\IL2Path
    """
    try:
        import winreg
        
        # Try 64-bit registry first
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\IL-2 Great Battles SP Campaign Tracker",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )
            value, _ = winreg.QueryValueEx(key, "IL2Path")
            winreg.CloseKey(key)
            if value and os.path.isdir(value):
                return value
        except (WindowsError, FileNotFoundError):
            pass
        
        # Try 32-bit registry (WOW6432Node)
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\IL-2 Great Battles SP Campaign Tracker",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_32KEY
            )
            value, _ = winreg.QueryValueEx(key, "IL2Path")
            winreg.CloseKey(key)
            if value and os.path.isdir(value):
                return value
        except (WindowsError, FileNotFoundError):
            pass
            
    except ImportError:
        # Not on Windows
        pass
    
    return None


def has_tracker_content(content: str) -> bool:
    """Check if content contains tracker-generated sections."""
    return bool(REGEX_MODULE.search(TRACKER_SECTION_HEADER_PATTERN, content, flags=REGEX_MODULE.IGNORECASE))


def process_campaign_folder(campaign_path: Path, verbose: bool = False) -> int:
    """
    Process a single campaign folder and remove tracker content from all locale files.
    
    Returns:
        Number of files modified
    """
    modified_count = 0
    locale_files = find_all_info_locale_files(campaign_path)
    
    for locale_file in locale_files:
        try:
            # Read file
            raw = locale_file.read_bytes()
            
            # Use utils function to decode and clean
            cleaned, encoding, original = decode_and_clean_info_locale(raw)
            
            # Check if content was modified
            if cleaned != original:
                # Write back with original encoding
                if encoding == "utf-16":
                    locale_file.write_bytes(cleaned.encode("utf-16"))
                elif encoding == "utf-8-sig":
                    locale_file.write_bytes(cleaned.encode("utf-8-sig"))
                else:
                    locale_file.write_bytes(cleaned.encode("utf-8"))
                
                modified_count += 1
                if verbose:
                    print(f"  ✓ Cleaned: {locale_file.name}")
                    
        except Exception as e:
            if verbose:
                print(f"  ⚠ Error processing {locale_file}: {e}")
    
    return modified_count


def cleanup_all_campaigns(il2_path: str, verbose: bool = False) -> Tuple[int, int]:
    """
    Remove tracker content from all campaign info.locale files.
    
    Args:
        il2_path: Path to IL-2 installation directory
        verbose: Print detailed progress
        
    Returns:
        Tuple of (campaigns_processed, files_modified)
    """
    campaigns_path = Path(il2_path) / "data" / "Campaigns"
    
    if not campaigns_path.exists():
        if verbose:
            print(f"Campaigns folder not found: {campaigns_path}")
        return 0, 0
    
    campaigns_processed = 0
    total_files_modified = 0
    
    # Process each campaign folder
    for campaign_folder in campaigns_path.iterdir():
        if not campaign_folder.is_dir():
            continue
        
        # Skip folders that don't look like campaigns
        if campaign_folder.name.startswith('.'):
            continue
        
        files_modified = process_campaign_folder(campaign_folder, verbose)
        
        if files_modified > 0:
            campaigns_processed += 1
            total_files_modified += files_modified
            if verbose:
                print(f"Cleaned campaign: {campaign_folder.name} ({files_modified} file(s))")
    
    return campaigns_processed, total_files_modified


def main():
    parser = argparse.ArgumentParser(
        description='Remove IL-2 Campaign Tracker content from campaign files'
    )
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help='Run in uninstall mode (cleanup all tracker content)'
    )
    parser.add_argument(
        '--il2-path',
        type=str,
        default=None,
        help='Path to IL-2 installation directory (auto-detect if not specified)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print detailed progress'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all output'
    )
    
    args = parser.parse_args()
    
    # Determine IL-2 path
    il2_path = args.il2_path
    
    if not il2_path:
        il2_path = get_il2_path_from_registry()
        if not il2_path:
            if not args.quiet:
                print("Error: Could not find IL-2 path. Please specify with --il2-path")
            sys.exit(1)
    
    # Validate path
    if not os.path.isdir(il2_path):
        if not args.quiet:
            print(f"Error: IL-2 path does not exist: {il2_path}")
        sys.exit(1)
    
    campaigns_path = Path(il2_path) / "data" / "Campaigns"
    if not campaigns_path.exists():
        if not args.quiet:
            print(f"Error: Campaigns folder not found: {campaigns_path}")
        sys.exit(1)
    
    # Run cleanup
    if not args.quiet:
        print("IL-2 Campaign Tracker - Content Cleanup")
        print("=" * 40)
        print(f"IL-2 Path: {il2_path}")
        print()
    
    try:
        campaigns_processed, files_modified = cleanup_all_campaigns(
            il2_path, 
            verbose=args.verbose and not args.quiet
        )
        
        if not args.quiet:
            print()
            print(f"Cleanup complete!")
            print(f"  Campaigns processed: {campaigns_processed}")
            print(f"  Files modified: {files_modified}")
        
        sys.exit(0)
        
    except Exception as e:
        if not args.quiet:
            print(f"Error during cleanup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
