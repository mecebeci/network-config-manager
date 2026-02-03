# Configuration Deployment System

Production-ready deployment system with automatic backups, dry-run mode, and rollback capability.

## Quick Start

```bash
# 1. Install dependencies
pip install netmiko jinja2 pyyaml tabulate tqdm

# 2. List resources
./deploy_config.py --list-templates
./deploy_config.py --list-devices

# 3. Test with dry-run
./deploy_config.py --device spine1 --template example_ntp.j2 --var ntp_server=10.0.0.1 --dry-run

# 4. Deploy
./deploy_config.py --device spine1 --template example_ntp.j2 --var ntp_server=10.0.0.1
```

## Key Features

✓ Automatic pre-deployment backups
✓ Dry-run mode for safe testing
✓ Automatic rollback on failures
✓ Parallel execution for multiple devices
✓ Comprehensive error handling & reporting

## Common Commands

```bash
# Single device
./deploy_config.py --device NAME --template FILE --var KEY=VALUE

# Multiple devices (by role)
./deploy_config.py --role spine --template FILE --var KEY=VALUE --parallel

# All devices with report
./deploy_config.py --all --template FILE --save-report report.txt
```

## Files

- `src/deployment.py` - Core deployment module (40 KB)
- `deploy_config.py` - CLI tool (13 KB)
- `docs/DEPLOYMENT.md` - Complete documentation (18 KB)

## Documentation

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for complete documentation including:
- Full API reference
- All usage examples
- Best practices
- Troubleshooting guide

---

**Status**: ✓ Production-ready
