"""
IL-2 Settings Manager - File Handlers

Provides atomic read/write operations for JSON and YAML files.
Uses ruamel.yaml to preserve comments and formatting in YAML files.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

# Try to use ruamel.yaml for round-trip YAML (preserves comments)
try:
    from ruamel.yaml import YAML
    HAS_RUAMEL = True
except ImportError:
    import yaml
    HAS_RUAMEL = False


def load_json(filepath: Path) -> Optional[dict]:
    """
    Load JSON file with error handling.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Parsed dictionary or None if file doesn't exist
        
    Raises:
        ValueError: If file is corrupt or unreadable
    """
    if not filepath.exists():
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {filepath.name}: {e}")
    except OSError as e:
        raise ValueError(f"Error reading {filepath.name}: {e}")


def save_json_atomic(filepath: Path, data: dict, create_backup: bool = True) -> None:
    """
    Save JSON atomically: write to temp file, then replace.
    Optionally create .backup before overwriting.
    
    Args:
        filepath: Path to save to
        data: Dictionary to save
        create_backup: Whether to create backup of existing file
    """
    filepath = Path(filepath)
    
    # Create backup if file exists
    if create_backup and filepath.exists():
        backup_path = filepath.with_suffix(filepath.suffix + '.backup')
        shutil.copy2(filepath, backup_path)
    
    # Write to temporary file in same directory (for atomic rename)
    temp_fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=filepath.stem + '_',
        suffix='.tmp'
    )
    
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic replace
        temp_path_obj = Path(temp_path)
        temp_path_obj.replace(filepath)
        
    except Exception:
        # Cleanup temp file on error
        Path(temp_path).unlink(missing_ok=True)
        raise


def load_yaml(filepath: Path) -> Optional[dict]:
    """
    Load YAML file preserving comments and formatting.
    
    Args:
        filepath: Path to YAML file
        
    Returns:
        Parsed dictionary or None if file doesn't exist
        
    Raises:
        ValueError: If file is corrupt or unreadable
    """
    if not filepath.exists():
        return None
    
    try:
        if HAS_RUAMEL:
            yaml_handler = YAML()
            yaml_handler.preserve_quotes = True
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml_handler.load(f)
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Error loading {filepath.name}: {e}")


def save_yaml_atomic(filepath: Path, data: dict, create_backup: bool = True) -> None:
    """
    Save YAML atomically with ruamel.yaml to preserve formatting.
    
    Args:
        filepath: Path to save to
        data: Dictionary to save
        create_backup: Whether to create backup of existing file
    """
    filepath = Path(filepath)
    
    # Create backup if file exists
    if create_backup and filepath.exists():
        backup_path = filepath.with_suffix(filepath.suffix + '.backup')
        shutil.copy2(filepath, backup_path)
    
    # Write to temporary file
    temp_fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=filepath.stem + '_',
        suffix='.tmp'
    )
    
    try:
        if HAS_RUAMEL:
            yaml_handler = YAML()
            yaml_handler.preserve_quotes = True
            yaml_handler.indent(mapping=2, sequence=4, offset=2)
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                yaml_handler.dump(data, f)
        else:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        Path(temp_path).replace(filepath)
        
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise
