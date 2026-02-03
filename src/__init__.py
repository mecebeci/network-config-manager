__version__ = "1.0.0"

# Import main classes for easier access
from .backup import ConfigBackup
from .connection_manager import ConnectionManager
from .inventory_loader import InventoryLoader

__all__ = [
    'ConfigBackup',
    'ConnectionManager',
    'InventoryLoader',
]
