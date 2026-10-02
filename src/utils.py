import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Iterator, Any
from tabulate import tabulate


def split_config_commands(config_text: str) -> tuple:
    """
    Split saved config text into single-line commands for line-by-line sending.

    Drops blank lines and '#' comment lines. Statements whose quoted value spans
    several lines (login banner, TLS certificate/key) cannot be sent one line at
    a time, so they are skipped and counted.

    Returns:
        (commands, skipped_count)
    """
    commands = []
    skipped = 0
    pending = []

    for raw in config_text.splitlines():
        line = raw.strip()
        if pending:
            pending.append(line)
            if line.count('"') % 2 == 1:
                pending = []
            continue
        if not line or line.startswith('#'):
            continue
        if line.count('"') % 2 == 1:
            pending = [line]
            skipped += 1
            continue
        commands.append(line)

    return commands, skipped


# A token is a quoted string, a bracketed leaf-list value, or a bare word
_CONFIG_TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\[[^\]]*\]|\S+')


def _set_path_tokens(line: str) -> Optional[tuple]:
    """Tokenize the part after 'set / ' of a flat SR Linux config line."""
    if not line.startswith('set / '):
        return None
    return tuple(_CONFIG_TOKEN_RE.findall(line[len('set / '):]))


def _multiline_statement_paths(config_text: str) -> List[tuple]:
    """Paths of statements skipped by split_config_commands (banner, TLS keys)."""
    paths = []
    in_statement = False
    for raw in config_text.splitlines():
        line = raw.strip()
        if in_statement:
            if line.count('"') % 2 == 1:
                in_statement = False
            continue
        if line.count('"') % 2 == 1:
            in_statement = True
            tokens = _set_path_tokens(line) or ()
            path = []
            for token in tokens:
                if token.startswith('"'):
                    break
                path.append(token)
            if path:
                paths.append(tuple(path))
    return paths


def config_delete_commands(current_config: str, target_config: str) -> tuple:
    """
    Compute the 'delete' commands that turn current_config into target_config.

    Both inputs are flat SR Linux configs ('set / ...' lines, as 'info flat'
    prints them). Replaying target_config's set commands only adds or
    overwrites, so anything present on the device but absent from the target
    must be deleted first. Each extra line is deleted at the shortest path the
    target does not share; if only the last token differs (a changed leaf
    value), the leaf itself is deleted. Sending the deletes and then the full
    target set commands in one commit yields exactly the target config.

    Deletes that would remove a multi-line statement (banner, TLS key) are
    withheld, because those statements cannot be replayed from the target.

    Returns:
        (delete_commands, withheld_commands)
    """
    target_commands, _ = split_config_commands(target_config)
    current_commands, _ = split_config_commands(current_config)
    target_multiline = _multiline_statement_paths(target_config)

    target_lines = set()
    target_prefixes = set()
    for command in target_commands:
        tokens = _set_path_tokens(command)
        if tokens is None:
            continue
        target_lines.add(tokens)
        for i in range(1, len(tokens) + 1):
            target_prefixes.add(tokens[:i])
    for path in target_multiline:
        for i in range(1, len(path) + 1):
            target_prefixes.add(path[:i])

    candidates = []
    for command in current_commands:
        tokens = _set_path_tokens(command)
        if tokens is None or tokens in target_lines:
            continue
        diverge = next(
            (i for i in range(1, len(tokens) + 1) if tokens[:i] not in target_prefixes),
            None
        )
        if diverge is None:
            continue  # Current line is a prefix of a target line
        path = tokens[:diverge] if diverge < len(tokens) else tokens[:-1]
        if path and path not in candidates:
            candidates.append(path)

    # Drop paths already covered by deleting one of their ancestors
    paths = [
        path for path in candidates
        if not any(other != path and path[:len(other)] == other for other in candidates)
    ]

    protected = _multiline_statement_paths(current_config) + target_multiline
    deletes = []
    withheld = []
    for path in paths:
        command = 'delete / ' + ' '.join(path)
        if any(p[:len(path)] == path for p in protected):
            withheld.append(command)
        else:
            deletes.append(command)

    return deletes, withheld


# ============================================================================
# A. LOGGING UTILITIES
# ============================================================================

def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/network_automation.log"
) -> logging.Logger:
    """
    Configure logging with both file and console handlers.

    Creates a root logger with two handlers:
    - File handler: logs everything to file with timestamps
    - Console handler: logs INFO and above to console

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (directory will be created if needed)

    Returns:
        Configured logger instance

    Example:
        logger = setup_logging(log_level="DEBUG")
        logger.info("Application started")
        logger.debug("Debug information")
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    ensure_directory(str(log_path.parent))

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all levels

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    simple_formatter = logging.Formatter(
        "%(levelname)s - %(message)s"
    )

    # File handler - logs everything
    try:
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file handler: {e}", file=sys.stderr)

    # Console handler - logs INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # Paramiko logs every SSH handshake at INFO, including the device login banner
    logging.getLogger("paramiko").setLevel(logging.WARNING)

    logger.info(f"Logging initialized - Level: {log_level}, File: {log_file}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create logger with specific name.

    Use this for module-specific logging to identify log sources.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Module-specific log message")
    """
    return logging.getLogger(name)


# ============================================================================
# B. TIMESTAMP UTILITIES
# ============================================================================

def get_timestamp(format: str = "%Y%m%d_%H%M%S") -> str:
    """
    Generate timestamp string for filenames.

    Args:
        format: strftime format string (default: YYYYMMDD_HHMMSS)

    Returns:
        Formatted timestamp string

    Example:
        timestamp = get_timestamp()
        # Returns: "20250203_143022"

        # Custom format
        timestamp = get_timestamp("%Y-%m-%d")
        # Returns: "2025-02-03"
    """
    return datetime.now().strftime(format)


def get_human_timestamp(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Generate human-readable timestamp.

    Args:
        format: strftime format string (default: YYYY-MM-DD HH:MM:SS)

    Returns:
        Formatted timestamp string

    Example:
        timestamp = get_human_timestamp()
        # Returns: "2025-02-03 14:30:22"
    """
    return datetime.now().strftime(format)


# ============================================================================
# C. FILE OPERATIONS
# ============================================================================

def ensure_directory(path: str) -> bool:
    """
    Create directory if it doesn't exist.

    Creates parent directories as needed (equivalent to mkdir -p).

    Args:
        path: Directory path to create

    Returns:
        True on success, False on failure

    Example:
        ensure_directory("configs/backups/2025")
        # Returns: True
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        logger = get_logger(__name__)
        logger.debug(f"Directory ensured: {path}")
        return True
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to create directory {path}: {e}")
        return False


def safe_write_file(filepath: str, content: str, mode: str = "w") -> bool:
    """
    Write content to file safely.

    Creates directory if needed and handles encoding automatically.

    Args:
        filepath: Path to file
        content: Content to write
        mode: File mode ('w' for write, 'a' for append)

    Returns:
        True on success, False on failure

    Example:
        config = "hostname router1\\ninterface eth0\\n"
        safe_write_file("configs/router1.cfg", config)
        # Returns: True
    """
    logger = get_logger(__name__)

    try:
        # Ensure directory exists
        file_path = Path(filepath)
        ensure_directory(str(file_path.parent))

        # Write file
        with open(filepath, mode, encoding='utf-8') as f:
            f.write(content)

        logger.debug(f"File written successfully: {filepath}")
        return True

    except Exception as e:
        logger.error(f"Failed to write file {filepath}: {e}")
        return False


def safe_read_file(filepath: str) -> Optional[str]:
    """
    Read file content safely.

    Args:
        filepath: Path to file

    Returns:
        File content as string, or None if file doesn't exist or error occurs

    Example:
        content = safe_read_file("configs/router1.cfg")
        if content:
            print(content)
    """
    logger = get_logger(__name__)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        logger.debug(f"File read successfully: {filepath}")
        return content

    except FileNotFoundError:
        logger.warning(f"File not found: {filepath}")
        return None

    except Exception as e:
        logger.error(f"Failed to read file {filepath}: {e}")
        return None


def list_files(
    directory: str,
    extension: Optional[str] = None,
    sort_by_date: bool = False
) -> List[str]:
    """
    List files in directory with optional filtering and sorting.

    Args:
        directory: Directory path to list
        extension: Optional file extension filter (e.g., ".cfg", ".txt")
        sort_by_date: If True, sort by modification date (newest first)

    Returns:
        List of full file paths

    Example:
        # List all files
        files = list_files("configs/backups")

        # List only .cfg files
        cfg_files = list_files("configs", extension=".cfg")

        # List files sorted by date
        recent_files = list_files("configs", sort_by_date=True)
    """
    logger = get_logger(__name__)

    try:
        dir_path = Path(directory)

        if not dir_path.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return []

        if not dir_path.is_dir():
            logger.warning(f"Path is not a directory: {directory}")
            return []

        # Get all files
        files = [str(f) for f in dir_path.iterdir() if f.is_file()]

        # Filter by extension
        if extension:
            if not extension.startswith('.'):
                extension = f".{extension}"
            files = [f for f in files if f.endswith(extension)]

        # Sort by modification date if requested
        if sort_by_date:
            files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        logger.debug(f"Listed {len(files)} files from {directory}")
        return files

    except Exception as e:
        logger.error(f"Failed to list files in {directory}: {e}")
        return []


# ============================================================================
# D. FORMATTING UTILITIES
# ============================================================================

def format_device_list(devices: List[dict]) -> str:
    """
    Format list of devices for display as a table.

    Args:
        devices: List of device dictionaries with keys: name, ip, role, device_type

    Returns:
        Formatted table string

    Example:
        devices = [
            {"name": "spine1", "ip": "192.168.1.1", "role": "spine", "device_type": "sr_linux"},
            {"name": "leaf1", "ip": "192.168.1.11", "role": "leaf", "device_type": "sr_linux"}
        ]
        print(format_device_list(devices))
    """
    if not devices:
        return "No devices to display"

    # Extract data for table
    headers = ["Name", "IP Address", "Role", "Device Type"]
    table_data = []

    for device in devices:
        row = [
            device.get("name", "N/A"),
            device.get("ip", "N/A"),
            device.get("role", "N/A"),
            device.get("device_type", "N/A")
        ]
        table_data.append(row)

    return tabulate(table_data, headers=headers, tablefmt="grid")


def print_separator(char: str = "=", length: int = 80) -> None:
    """
    Print visual separator line.

    Args:
        char: Character to use for separator
        length: Length of separator line

    Example:
        print_separator()
        # Prints: ================================================================================

        print_separator(char="-", length=40)
        # Prints: ----------------------------------------
    """
    print(char * length)


def print_success(message: str) -> None:
    """
    Print success message in green with checkmark.

    Args:
        message: Success message to display

    Example:
        print_success("Configuration backup completed")
        # Output: ✓ Configuration backup completed
    """
    # ANSI color codes
    GREEN = "\033[92m"
    RESET = "\033[0m"

    # Check if terminal supports colors
    if sys.stdout.isatty():
        print(f"{GREEN}✓ {message}{RESET}")
    else:
        print(f"[SUCCESS] {message}")


def print_error(message: str) -> None:
    """
    Print error message in red with X mark.

    Args:
        message: Error message to display

    Example:
        print_error("Failed to connect to device")
        # Output: ✗ Failed to connect to device
    """
    # ANSI color codes
    RED = "\033[91m"
    RESET = "\033[0m"

    # Check if terminal supports colors
    if sys.stdout.isatty():
        print(f"{RED}✗ {message}{RESET}")
    else:
        print(f"[ERROR] {message}")


def print_info(message: str) -> None:
    """
    Print info message in blue with info icon.

    Args:
        message: Info message to display

    Example:
        print_info("Starting device configuration")
        # Output: ℹ Starting device configuration
    """
    # ANSI color codes
    BLUE = "\033[94m"
    RESET = "\033[0m"

    # Check if terminal supports colors
    if sys.stdout.isatty():
        print(f"{BLUE}ℹ {message}{RESET}")
    else:
        print(f"[INFO] {message}")


# ============================================================================
# E. PROGRESS INDICATORS
# ============================================================================

def create_progress_bar(
    iterable: Any,
    description: str = "Processing",
    total: Optional[int] = None
) -> Iterator:
    """
    Create a simple text-based progress indicator.

    Wraps an iterable to show progress as items are processed.
    Tries to use tqdm if available, falls back to simple counter.

    Args:
        iterable: Iterable to wrap
        description: Description of the task
        total: Total number of items (optional, will be inferred if possible)

    Yields:
        Items from the iterable

    Example:
        devices = ["router1", "router2", "router3"]
        for device in create_progress_bar(devices, description="Backing up"):
            backup_device(device)
        # Output:
        # Backing up: router1 (1/3)
        # Backing up: router2 (2/3)
        # Backing up: router3 (3/3)
    """
    try:
        # Try to import tqdm for fancy progress bars
        from tqdm import tqdm

        if total is None:
            try:
                total = len(iterable)
            except TypeError:
                pass

        yield from tqdm(iterable, desc=description, total=total, unit="item")

    except ImportError:
        # Fallback to simple progress indicator
        logger = get_logger(__name__)
        logger.debug("tqdm not available, using simple progress indicator")

        # Try to get total count
        if total is None:
            try:
                total = len(iterable)
            except TypeError:
                total = None

        # Iterate with counter
        for idx, item in enumerate(iterable, start=1):
            if total:
                print(f"{description}: {idx}/{total}", end="\r")
            else:
                print(f"{description}: {idx}", end="\r")

            yield item

        # Clear progress line and print completion
        if total:
            print(f"{description}: {total}/{total} - Complete!")
        else:
            print(f"{description}: Complete!")


# ============================================================================
# MODULE INITIALIZATION
# ============================================================================

# Create a default logger for this module
_module_logger = get_logger(__name__)


if __name__ == "__main__":
    # Demo/test code
    print("=" * 80)
    print("Network Automation Utilities - Demo")
    print("=" * 80)

    # Test logging
    logger = setup_logging(log_level="DEBUG", log_file="logs/test.log")
    logger.info("Testing logging functionality")
    logger.debug("This is a debug message")

    # Test timestamps
    print(f"\nFilename timestamp: {get_timestamp()}")
    print(f"Human timestamp: {get_human_timestamp()}")

    # Test file operations
    test_dir = "test_output"
    test_file = f"{test_dir}/test.txt"

    print(f"\nTesting file operations...")
    ensure_directory(test_dir)
    safe_write_file(test_file, "Hello, World!\n")
    content = safe_read_file(test_file)
    print(f"File content: {content}")

    # Test formatting
    print_separator()
    print_success("This is a success message")
    print_error("This is an error message")
    print_info("This is an info message")
    print_separator()

    # Test device list formatting
    devices = [
        {"name": "spine1", "ip": "192.168.1.1", "role": "spine", "device_type": "sr_linux"},
        {"name": "leaf1", "ip": "192.168.1.11", "role": "leaf", "device_type": "sr_linux"},
        {"name": "leaf2", "ip": "192.168.1.12", "role": "leaf", "device_type": "sr_linux"}
    ]
    print("\nDevice List:")
    print(format_device_list(devices))

    # Test progress bar
    print("\nTesting progress indicator:")
    import time
    for i in create_progress_bar(range(5), description="Processing items"):
        time.sleep(0.2)

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80)
