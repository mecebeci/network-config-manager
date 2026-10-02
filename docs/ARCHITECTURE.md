# Architecture

This document shows how the modules fit together and what happens during a deployment. Both diagrams reflect the current code.

## 1. Component diagram

`netconfig.py` is the only entry point. It calls the classes in `src/`, and every operation that touches a device goes through `ConnectionManager`, which uses Netmiko over SSH.

```mermaid
flowchart TB
    user(["Operator"])
    cli["netconfig.py<br/>CLI: backup, deploy, rollback, list, validate"]

    subgraph app["src/ - application logic"]
        inv["InventoryLoader"]
        tpl["TemplateEngine (Jinja2)"]
        bkp["ConfigBackup"]
        dep["ConfigDeployment"]
        rbk["ConfigRollback"]
        conn["ConnectionManager"]
    end

    subgraph files["Files and settings"]
        invf[("inventory/devices.yaml")]
        tplf[("configs/templates/*.j2")]
        bkf[("configs/backups/*.cfg")]
        env[(".env<br/>DEVICE_USERNAME, DEVICE_PASSWORD")]
    end

    netmiko["Netmiko<br/>nokia_srl driver, SSH"]

    subgraph lab["Containerlab lab: srlinux-mgmt, 172.21.20.0/24"]
        spine1["spine1<br/>SR Linux"]
        spine2["spine2<br/>SR Linux"]
        leaf1["leaf1<br/>SR Linux"]
        leaf2["leaf2<br/>SR Linux"]
        spine1 --- leaf1
        spine1 --- leaf2
        spine2 --- leaf1
        spine2 --- leaf2
    end

    topo[("lab/topology.yaml")]

    user --> cli
    cli --> bkp
    cli --> dep
    cli --> rbk
    cli --> inv
    cli --> tpl

    dep --> inv
    dep --> tpl
    dep --> bkp
    dep --> conn
    rbk --> inv
    rbk --> bkp
    rbk --> conn
    bkp --> inv
    bkp --> conn

    inv -. reads .-> invf
    tpl -. reads .-> tplf
    bkp -. writes .-> bkf
    rbk -. reads .-> bkf
    env -. "credentials, resolved in ConfigBackup" .-> bkp

    conn --> netmiko
    netmiko -- "SSH" --> lab
    topo -. "containerlab deploy creates" .-> lab
```

How to read it:

- **CLI**: `netconfig.py` parses the subcommand, picks target devices, shows the plan, asks for confirmation and prints the results. The work is done by `src/`.
- **Inventory**: `InventoryLoader` reads `inventory/devices.yaml`. Credentials in that file are `${DEVICE_USERNAME}` / `${DEVICE_PASSWORD}` placeholders. `ConfigBackup` resolves them from the environment (`.env`), and `ConfigDeployment` and `ConfigRollback` reuse that through their `ConfigBackup` instance.
- **Backup**: `ConfigBackup` runs `info flat` on the device and writes the output to `configs/backups/`.
- **Deployment**: `ConfigDeployment` renders a template with `TemplateEngine`, takes a backup with `ConfigBackup`, and sends the result through `ConnectionManager`.
- **Rollback**: `ConfigRollback` reads a backup file, takes a safety backup of the current config, and replays the backup on the device.
- **Lab**: the devices are created by Containerlab from `lab/topology.yaml`. The tool does not manage the lab itself. It reaches the devices on the `srlinux-mgmt` network, either directly or from the Docker container started by the `netconfig` wrapper script.

## 2. Deploy flow

This is `netconfig.py deploy -t <template> ...`. The first part runs once in the CLI (`handle_deploy`). The second part runs once per device in `ConfigDeployment.deploy_to_device`, either sequentially or in parallel with `--parallel`.

```mermaid
flowchart TD
    start(["netconfig deploy -t template --vars ..."])

    subgraph cli["CLI: handle_deploy (once)"]
        loadinv["Load inventory<br/>inventory/devices.yaml"]
        tplcheck{"Template exists in<br/>configs/templates?"}
        loadvars["Load --vars<br/>JSON string or @file"]
        select["Select devices<br/>--device, --role or --all"]
        plan["Show deployment plan"]
        dry{"--dry-run?"}
        preview["Render template for each device<br/>and print the preview"]
        confirm{"Confirmed?<br/>(--yes skips the prompt)"}
    end

    subgraph dev["Per device: deploy_to_device"]
        vars["Merge variables<br/>inventory fields + hostname + timestamp + --vars"]
        render["Render Jinja2 template"]
        renderok{"Render OK?"}
        bkpq{"Auto backup enabled?<br/>(--no-backup disables it)"}
        backup["Backup current config<br/>info flat to configs/backups"]
        bkpwarn["Backup failed:<br/>log a warning and continue"]
        connect["Connect with ConnectionManager<br/>credentials from .env, retries"]
        lines["Drop blank lines and ! comments"]
        send["send_config in candidate mode<br/>with error_pattern"]
        rejected{"Command rejected<br/>by the device?"}
        discard["discard candidate"]
        commit["commit"]
        commitok{"Commit OK?"}
        success(["Success"])
        hasbackup{"Backup was created?"}
        rollback["rollback_on_failure<br/>reconnect, replay backup lines, commit"]
        rbok{"Rollback OK?"}
    end

    noop(["Exit: nothing sent to devices"])
    failA(["Failed: no change on device"])
    failB(["Failed: rolled back to backup"])
    failC(["Failed: rollback also failed"])
    failD(["Failed: no backup to roll back to"])
    cancel(["Cancelled by user"])
    err(["Exit with error"])

    start --> loadinv --> tplcheck
    tplcheck -- "No" --> err
    tplcheck -- "Yes" --> loadvars --> select --> plan --> dry
    dry -- "Yes" --> preview --> noop
    dry -- "No" --> confirm
    confirm -- "No" --> cancel
    confirm -- "Yes" --> vars

    vars --> render --> renderok
    renderok -- "No" --> failA
    renderok -- "Yes" --> bkpq
    bkpq -- "Yes" --> backup
    bkpq -- "No" --> connect
    backup -- "OK" --> connect
    backup -- "Error" --> bkpwarn --> connect

    connect -- "Connected" --> lines --> send --> rejected
    connect -- "Connection failed" --> hasbackup
    rejected -- "Yes" --> discard --> hasbackup
    rejected -- "No" --> commit --> commitok
    commitok -- "Yes" --> success
    commitok -- "No" --> discard

    hasbackup -- "Yes" --> rollback --> rbok
    hasbackup -- "No" --> failD
    rbok -- "Yes" --> failB
    rbok -- "No" --> failC
```

Behavior worth knowing:

- **Dry-run** only renders the templates. It does not connect to any device and does not take a backup.
- **A failed backup does not stop the deployment.** It is logged as a warning, and the rollback branch is then skipped because no backup exists.
- **`error_pattern`** matches the device output lines that start with `Parsing error` or `Error:`. A rejected command stops the deployment, and the candidate configuration is discarded before anything is committed.
- **Rollback replays the backup.** It sends the saved `set /` lines and commits. It does not delete settings that were added after the backup was taken. Multi-line quoted values (login banner, TLS certificate) are skipped with a warning.
- **A missing template variable renders as an empty string.** The Jinja2 environment is not strict, so for example a missing `ntp_server` produces `server  iburst true`, which the device then rejects.
