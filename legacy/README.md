# Legacy CLI Scripts

These are the original individual CLI scripts, kept for backward compatibility.

**DEPRECATED**: Use the unified CLI instead:
```bash
python3 netconfig.py <command>
```

See [../docs/NETCONFIG_USAGE.md](../docs/NETCONFIG_USAGE.md) for the unified CLI documentation.

## Legacy Scripts

- **backup_devices.py** - Standalone backup CLI
- **deploy_config.py** - Standalone deployment CLI
- **rollback_config.py** - Standalone rollback CLI

## Why Deprecated?

The unified CLI (`netconfig.py`) provides:
- ✓ Single entry point for all operations
- ✓ Consistent command structure
- ✓ Better documentation and help text
- ✓ Additional commands (list, validate)
- ✓ Professional interface like git, docker, aws-cli

## Still Work?

Yes, these scripts still work and can be run:

```bash
# From legacy directory
cd legacy
python3 backup_devices.py --all
python3 deploy_config.py -t template.j2 --all
python3 rollback_config.py --device spine1 --latest

# Or with full path
python3 legacy/backup_devices.py --all
```

However, they are **no longer actively maintained**. New features and improvements will only be added to `netconfig.py`.
