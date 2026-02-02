# SR Linux Spine-Leaf Lab Topology

## Overview

This Containerlab topology implements a realistic spine-leaf data center network using the Nokia SR Linux network operating system. The topology consists of 2 spine switches and 4 leaf switches, providing redundant connectivity suitable for testing network automation, SNMP monitoring, and modern data center networking protocols.

## Topology Diagram

```text
                    ┌──────────┐         ┌──────────┐
                    │  spine1  │         │  spine2  │
                    │172.21.20.11│       │172.21.20.12│
                    └─────┬────┘         └─────┬────┘
                          │                    │
           ┌──────────────┼────────────────────┼──────────────┐
           │              │                    │              │
           │              │                    │              │
      ┌────┴────┐    ┌────┴────┐         ┌────┴────┐    ┌────┴────┐
      │  leaf1  │    │  leaf2  │         │  leaf3  │    │  leaf4  │
      │172.21   │    │172.21   │         │172.21   │    │172.21   │
      │  .20.13 │    │  .20.14 │         │  .20.15 │    │  .20.16 │
      └─────────┘    └─────────┘         └─────────┘    └─────────┘

```

### Connectivity Matrix

Each leaf switch is dual-homed to both spine switches for redundancy:

| Leaf Switch | Interface | Connected To | Remote Interface |
| --- | --- | --- | --- |
| leaf1 | e1-1 | spine1 | e1-1 |
| leaf1 | e1-2 | spine2 | e1-1 |
| leaf2 | e1-1 | spine1 | e1-2 |
| leaf2 | e1-2 | spine2 | e1-2 |
| leaf3 | e1-1 | spine1 | e1-3 |
| leaf3 | e1-2 | spine2 | e1-3 |
| leaf4 | e1-1 | spine1 | e1-4 |
| leaf4 | e1-2 | spine2 | e1-4 |

## Device Inventory

| Hostname | Management IP | Role | Type | Purpose |
| --- | --- | --- | --- | --- |
| spine1 | 172.21.20.11 | Spine | ixr-d3l | Core aggregation switch |
| spine2 | 172.21.20.12 | Spine | ixr-d3l | Core aggregation switch |
| leaf1 | 172.21.20.13 | Leaf | ixr-d3l | Top-of-Rack access switch |
| leaf2 | 172.21.20.14 | Leaf | ixr-d3l | Top-of-Rack access switch |
| leaf3 | 172.21.20.15 | Leaf | ixr-d3l | Top-of-Rack access switch |
| leaf4 | 172.21.20.16 | Leaf | ixr-d3l | Top-of-Rack access switch |

**Management Network:** 172.21.20.0/24

## Prerequisites

### Required Software

**Docker** (version 20.10 or later)

Check Docker version:
```bash
docker --version
```


Install Docker (Ubuntu/Debian):
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```


**Containerlab** (version 0.48 or later)
Install Containerlab:
```bash
bash -c "$(curl -sL https://get.containerlab.dev)"
```


Verify installation:
```bash
containerlab version
```

**System Resources**
   * Minimum: 8GB RAM, 4 CPU cores
   * Recommended: 16GB RAM, 8 CPU cores
   * Disk space: ~10GB for images and containers

### Pull SR Linux Image

Pull the Nokia SR Linux container image (one-time):

```bash
docker pull ghcr.io/nokia/srlinux:latest
```

## Lab Operations

### Deploy the Lab

Deploy the entire topology. Make sure you are in the correct directory:

```bash
# Navigate to the lab directory
cd lab

# Deploy the topology
sudo containerlab deploy -t topology.yaml
```

Expected output:

```
INFO[0000] Containerlab v0.xx.x started
INFO[0000] Parsing & checking topology file: topology.yaml
INFO[0001] Creating lab directory: .../clab-srlinux-spine-leaf
INFO[0001] Creating container: "spine1"
...
+---+-------------------------+--------------+---------------------------+-------+---------+----------------+
| # |          Name           | Container ID |           Image           | Kind  |  State  |  IPv4 Address  |
+---+-------------------------+--------------+---------------------------+-------+---------+----------------+
| 1 | clab-srlinux-spine1     | xxxxx        | ghcr.io/nokia/srlinux     | nokia | running | 172.21.20.11   |
...
```

### Access Devices

#### SSH Access

SSH to any device using the management IP:

```bash
ssh admin@172.21.20.11  # spine1
ssh admin@172.21.20.12  # spine2
ssh admin@172.21.20.13  # leaf1
ssh admin@172.21.20.14  # leaf2
ssh admin@172.21.20.15  # leaf3
ssh admin@172.21.20.16  # leaf4
```

**Default Credentials:**

* Username: `admin`
* Password: `NokiaSrl1!`

#### Docker Exec Access

Access the device directly via container:

```bash
sudo docker exec -it clab-srlinux-spine-leaf-spine1 sr_cli
sudo docker exec -it clab-srlinux-spine-leaf-leaf1 sr_cli
```

### Verify Lab Status

Check if all containers are running:

```bash
# View topology status
sudo containerlab inspect -t topology.yaml

# Check container status
sudo docker ps | grep clab-srlinux

# View container logs
sudo docker logs clab-srlinux-spine-leaf-spine1
```

### Destroy the Lab

Stop and remove all containers:

```bash
# From the lab directory
sudo containerlab destroy -t topology.yaml

# Confirm cleanup
sudo containerlab inspect -t topology.yaml
```

> **Note:** This will delete all containers and runtime configurations but preserve the topology file.

## Device Configuration

### Basic SR Linux Commands

Once logged into a device:

```bash
# Enter CLI mode (if not already in it)
sr_cli

# Show running configuration
info

# Show interfaces
show interface brief

# Show network instances
show network-instance summary

# Show system information
show system information

# Show LLDP neighbors
show system lldp neighbor

# Enter configuration mode
enter candidate

# Commit configuration changes
commit now
```

### Verify Connectivity

After lab deployment, verify the topology:

**From spine1, check LLDP neighbors (should see all 4 leaves):**
```bash
ssh admin@172.21.20.11
show system lldp neighbor
```

**From leaf1, check LLDP neighbors (should see both spines):**
```bash
ssh admin@172.21.20.13
show system lldp neighbor
```

## Troubleshooting

### Common Issues

#### 1. Containers Not Starting

```bash
# Check Docker service
sudo systemctl status docker

# Check available resources
docker stats

# View container logs
sudo docker logs clab-srlinux-spine-leaf-<device-name>
```

#### 2. Cannot SSH to Devices

```bash
# Verify container is running
sudo docker ps | grep <device-name>

# Check if SSH service is ready (may take 60-90 seconds)
ssh -v admin@172.21.20.11

# Access via docker exec instead
sudo docker exec -it clab-srlinux-spine-leaf-spine1 sr_cli
```

#### 3. Management IP Not Reachable

```bash
# Verify management network
sudo docker network inspect clab-srlinux-spine-leaf

# Check container IP assignments
sudo containerlab inspect -t topology.yaml

# Ping from host
ping 172.21.20.11
```

#### 4. Config Files Not Found

The topology references config files in the `../configs/` directory. If these don't exist yet:

**Temporary fix: Comment out startup-config lines in topology.yaml or create placeholder config files:**
```bash
mkdir -p ../configs
touch ../configs/{spine1,spine2,leaf1,leaf2,leaf3,leaf4}.cfg
```

#### 5. Port Conflicts

If you get port binding errors:

```bash
# Check what's using the ports
sudo netstat -tulpn | grep :443

# Stop conflicting containers
sudo docker stop <container-id>
```

### Performance Optimization

For better performance on resource-constrained systems:

1. Use `ixr-d2l` type instead of `ixr-d3l` in `topology.yaml` (fewer resources).
2. Deploy spine switches first, then leaf switches sequentially.
3. Increase Docker resource limits in Docker Desktop settings.

### Logs and Diagnostics

```bash
# Containerlab logs
sudo containerlab --log-level debug deploy -t topology.yaml

# Individual container logs
sudo docker logs -f clab-srlinux-spine-leaf-spine1

# System resource usage
sudo docker stats
```

## Network Automation Integration

This lab is designed for integration with:

* **SNMP Monitoring**: All devices support SNMPv2c and SNMPv3
* **Python Automation**: Use `pygnmi`, `netmiko`, or `paramiko` for automation
* **Ansible**: SR Linux devices support standard network modules
* **REST API**: SR Linux provides JSON-RPC management interface

Example Python connection:

```python
from netmiko import ConnectHandler

device = {
    'device_type': 'nokia_sros',
    'host': '172.21.20.11',
    'username': 'admin',
    'password': 'NokiaSrl1!',
}

connection = ConnectHandler(**device)
output = connection.send_command('show version')
print(output)
```

## Next Steps

1. **Configure SNMP**: Enable SNMP on all devices for monitoring.
2. **Add IP Addressing**: Configure management and data plane IP addresses.
3. **Enable Routing**: Configure BGP/OSPF for inter-switch routing.
4. **Test Automation**: Run Python scripts against the lab devices.
5. **Collect Metrics**: Set up SNMP polling and data collection.

## References

* [Containerlab Documentation](https://containerlab.dev/)
* [Nokia SR Linux Documentation](https://documentation.nokia.com/srlinux/)
* [SR Linux Containerlab Guide](https://learn.srlinux.dev/tutorials/infrastructure/containerlab/)

## Lab Topology File

The main topology file is located at [topology.yaml](topology.yaml) in this directory.
