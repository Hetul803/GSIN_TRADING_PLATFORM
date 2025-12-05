# backend/brain/mcn_backup.py
"""
MCN Backup and Restore functionality.
PHASE 4: Backup MCN state before mutation rounds.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .mcn_adapter import get_mcn_adapter


class MCNBackupManager:
    """Manages MCN state backups."""
    
    def __init__(self, backup_dir: Optional[Path] = None):
        """
        Initialize backup manager.
        
        Args:
            backup_dir: Directory to store backups (default: backend/data/mcn_backups)
        """
        if backup_dir is None:
            backup_dir = Path(__file__).parent.parent.parent / "data" / "mcn_backups"
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, label: str = "auto") -> Optional[str]:
        """
        Create a backup of MCN state.
        
        Args:
            label: Label for the backup (e.g., "before_mutation", "auto")
        
        Returns:
            Backup file path if successful, None otherwise
        """
        try:
            mcn_adapter = get_mcn_adapter()
            if not mcn_adapter.is_available or not mcn_adapter.mcn:
                return None
            
            # Get MCN state (if available)
            # Note: This depends on MCN implementation - may need to be adapted
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"mcn_backup_{label}_{timestamp}.json"
            backup_path = self.backup_dir / backup_filename
            
            # Save MCN state
            # This is a placeholder - actual implementation depends on MCN.save_state()
            state_data = {
                "timestamp": datetime.now().isoformat(),
                "label": label,
                "mcn_available": mcn_adapter.is_available,
                # Add actual MCN state if save_state() is implemented
            }
            
            # Try to save state if method exists
            if hasattr(mcn_adapter, 'save_state'):
                try:
                    state_data["mcn_state"] = mcn_adapter.save_state()
                except:
                    pass
            
            with open(backup_path, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            return str(backup_path)
        except Exception as e:
            print(f"Warning: Failed to create MCN backup: {e}")
            return None
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        for backup_file in self.backup_dir.glob("mcn_backup_*.json"):
            try:
                with open(backup_file, 'r') as f:
                    data = json.load(f)
                    backups.append({
                        "filename": backup_file.name,
                        "path": str(backup_file),
                        "timestamp": data.get("timestamp"),
                        "label": data.get("label"),
                    })
            except:
                pass
        return sorted(backups, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore MCN state from backup.
        
        Args:
            backup_path: Path to backup file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                return False
            
            with open(backup_file, 'r') as f:
                data = json.load(f)
            
            mcn_adapter = get_mcn_adapter()
            if not mcn_adapter.is_available:
                return False
            
            # Restore state if load_state() is implemented
            if hasattr(mcn_adapter, 'load_state') and "mcn_state" in data:
                try:
                    mcn_adapter.load_state(data["mcn_state"])
                    return True
                except:
                    return False
            
            return False
        except Exception as e:
            print(f"Warning: Failed to restore MCN backup: {e}")
            return False


# Global backup manager instance
_backup_manager: Optional[MCNBackupManager] = None


def get_backup_manager() -> MCNBackupManager:
    """Get global backup manager instance."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = MCNBackupManager()
    return _backup_manager

