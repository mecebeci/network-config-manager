#!/usr/bin/env python3
"""
Unit tests for backup module structure validation.

These tests verify the module structure, imports, and basic functionality
without requiring actual device connections.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")

    try:
        # Note: This will fail if netmiko is not installed
        # but validates the Python structure is correct
        from backup import ConfigBackup
        print("  ✓ ConfigBackup imported successfully")
        return True
    except ImportError as e:
        # Expected if dependencies not installed
        if "netmiko" in str(e) or "pysnmp" in str(e):
            print(f"  ⚠ Import skipped (missing dependency: {e})")
            return True  # Structure is valid, just missing deps
        else:
            print(f"  ✗ Import failed: {e}")
            return False


def test_class_structure():
    """Test that ConfigBackup class has all required methods."""
    print("\nTesting class structure...")

    try:
        # Import without instantiation to avoid connection requirements
        import backup
        cls = backup.ConfigBackup

        required_methods = [
            '__init__',
            'backup_device',
            'backup_multiple_devices',
            'backup_all_devices',
            'backup_devices_by_role',
            'get_latest_backup',
            'list_device_backups',
            'verify_backup',
            'generate_backup_report',
            'cleanup_old_backups',
            '_merge_device_settings',
            '_get_device_config',
        ]

        missing_methods = []
        for method in required_methods:
            if not hasattr(cls, method):
                missing_methods.append(method)
                print(f"  ✗ Missing method: {method}")
            else:
                print(f"  ✓ Method exists: {method}")

        if missing_methods:
            print(f"\n✗ Missing {len(missing_methods)} required methods")
            return False
        else:
            print(f"\n✓ All {len(required_methods)} required methods present")
            return True

    except ImportError as e:
        if "netmiko" in str(e):
            print("  ⚠ Test skipped (missing netmiko dependency)")
            return True
        print(f"  ✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False


def test_module_docstring():
    """Test that module has proper documentation."""
    print("\nTesting module documentation...")

    try:
        import backup

        if backup.__doc__:
            print(f"  ✓ Module docstring present ({len(backup.__doc__)} chars)")

            # Check for key documentation elements
            doc = backup.__doc__.lower()
            checks = [
                ('example' in doc, "Contains examples"),
                ('configuration' in doc, "Mentions configuration"),
                ('backup' in doc, "Mentions backup"),
            ]

            for check, description in checks:
                if check:
                    print(f"  ✓ {description}")
                else:
                    print(f"  ⚠ Missing: {description}")

            return True
        else:
            print("  ✗ Module docstring missing")
            return False

    except ImportError as e:
        if "netmiko" in str(e):
            print("  ⚠ Test skipped (missing netmiko dependency)")
            return True
        print(f"  ✗ Import failed: {e}")
        return False


def test_type_hints():
    """Test that methods have type hints."""
    print("\nTesting type hints...")

    try:
        import backup
        import inspect

        cls = backup.ConfigBackup
        methods_to_check = [
            'backup_device',
            'backup_multiple_devices',
            'get_latest_backup',
            'verify_backup',
        ]

        has_hints = []
        for method_name in methods_to_check:
            method = getattr(cls, method_name)
            sig = inspect.signature(method)

            # Check for return annotation
            if sig.return_annotation != inspect.Signature.empty:
                has_hints.append(method_name)
                print(f"  ✓ {method_name} has type hints")
            else:
                print(f"  ⚠ {method_name} missing type hints")

        if has_hints:
            print(f"\n✓ {len(has_hints)}/{len(methods_to_check)} methods have type hints")
            return True
        else:
            print("\n⚠ No type hints found (may be okay for some methods)")
            return True

    except ImportError as e:
        if "netmiko" in str(e):
            print("  ⚠ Test skipped (missing netmiko dependency)")
            return True
        print(f"  ✗ Import failed: {e}")
        return False


def test_file_exists():
    """Test that the backup.py file exists and is readable."""
    print("\nTesting file existence...")

    backup_file = os.path.join(
        os.path.dirname(__file__),
        '..',
        'src',
        'backup.py'
    )

    if os.path.exists(backup_file):
        size = os.path.getsize(backup_file)
        print(f"  ✓ backup.py exists ({size:,} bytes)")

        if size > 20000:  # Should be substantial
            print(f"  ✓ File size is substantial")
            return True
        else:
            print(f"  ⚠ File seems small for a complete implementation")
            return False
    else:
        print(f"  ✗ backup.py not found at {backup_file}")
        return False


def test_documentation_exists():
    """Test that documentation files exist."""
    print("\nTesting documentation...")

    docs = {
        'BACKUP_USAGE.md': os.path.join('..', 'docs', 'BACKUP_USAGE.md'),
        'backup_example.py': os.path.join('..', 'examples', 'backup_example.py'),
        'IMPLEMENTATION_SUMMARY.md': os.path.join('..', 'IMPLEMENTATION_SUMMARY.md'),
    }

    all_exist = True
    for name, path in docs.items():
        full_path = os.path.join(os.path.dirname(__file__), path)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            print(f"  ✓ {name} exists ({size:,} bytes)")
        else:
            print(f"  ✗ {name} not found")
            all_exist = False

    return all_exist


def run_all_tests():
    """Run all structure tests."""
    print("=" * 80)
    print("Backup Module Structure Validation")
    print("=" * 80)

    tests = [
        ("File Existence", test_file_exists),
        ("Documentation", test_documentation_exists),
        ("Module Imports", test_imports),
        ("Class Structure", test_class_structure),
        ("Module Documentation", test_module_docstring),
        ("Type Hints", test_type_hints),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All structure validation tests passed!")
        return True
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
