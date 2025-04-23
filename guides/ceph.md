# Setting up Ceph in Docker on a Linux VM

This guide outlines how to set up Ceph in Docker containers on a Linux VM, covering installation, configuration, and
administration.

## 1. Installing and Configuring Docker

1. Update package lists:
   ```bash
   sudo apt update
   ```
2. Install Docker:
   ```bash
   sudo apt install docker.io
   ```
3. Start and enable Docker:
   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```
4. Add your user to the docker group to avoid permission issues:
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```
5. Verify the installation:
   ```bash
   docker version
   ```

## 2. Installing Required Tools

1. Install docker-compose and make:
   ```bash
   sudo apt install docker-compose make
   ```
2. Verify the installations:
   ```bash
   docker-compose version
   make --version
   ```

## 3. Directory Structure Setup

Create the necessary directories:

```bash
sudo mkdir -p /data/ceph/{config,data,certs}
sudo chown -R $USER:$USER /data/ceph
```

The structure will look like:

```
/data/ceph/
├── config/
├── data/
├── certs/
├── docker-compose.yaml
└── .env
```

## 4. Environment Configuration

Create the .env file in /data/ceph:

```env
# Admin credentials
CEPH_ADMIN_USER=admin
CEPH_ADMIN_PASSWORD=your_secure_password_here

# Network configuration
CEPH_PUBLIC_NETWORK=172.20.0.0/24
CEPH_CLUSTER_NETWORK=172.20.0.0/24
MON_IP=172.20.0.2

# Certificates
CUSTOM_CA_CERT=/data/ceph/certs/ca.crt
CUSTOM_CA_KEY=/data/ceph/certs/ca.key
```

## 5. Docker Compose Configuration

Create docker-compose.yaml in /data/ceph:

```yaml
version: '3.8'

services:
  mon:
    image: ceph/daemon:latest
    environment:
      - CEPH_PUBLIC_NETWORK=${CEPH_PUBLIC_NETWORK}
      - CEPH_CLUSTER_NETWORK=${CEPH_CLUSTER_NETWORK}
      - CEPH_ADMIN_USER=${CEPH_ADMIN_USER}
      - CEPH_ADMIN_PASSWORD=${CEPH_ADMIN_PASSWORD}
      - CUSTOM_CA_CERT=${CUSTOM_CA_CERT}
      - MON_IP=${MON_IP}
    volumes:
      - /data/ceph/config:/etc/ceph
      - /data/ceph/data:/var/lib/ceph
      - /data/ceph/certs:/certs:ro
    command: mon

  osd:
    image: ceph/daemon:latest
    depends_on:
      - mon
    environment:
      - CEPH_ADMIN_USER=${CEPH_ADMIN_USER}
      - CEPH_ADMIN_PASSWORD=${CEPH_ADMIN_PASSWORD}
      - CUSTOM_CA_CERT=${CUSTOM_CA_CERT}
    volumes:
      - /data/ceph/config:/etc/ceph
      - /data/ceph/data:/var/lib/ceph
      - /data/ceph/certs:/certs:ro
    command: osd
```

## 6. Certificate Generation

Create a script to generate certificates in /data/ceph/certs:

```bash
#!/bin/bash
# generate-certs.sh

openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
    -keyout /data/ceph/certs/ca.key \
    -out /data/ceph/certs/ca.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=Ceph"
```

Save this script as `/data/ceph/certs/generate-certs.sh` and make it executable:

```bash
touch /data/ceph/certs/generate-certs.sh
chmod +x /data/ceph/certs/generate-certs.sh
```

## 7. Makefile for Common Operations

Create a Makefile in /data/ceph:

```makefile
.PHONY: start stop restart status logs generate-certs

start:
	docker-compose up -d

stop:
	docker-compose down

restart:
	docker-compose restart

status:
	docker-compose ps

logs:
	docker-compose logs -f

generate-certs:
	bash /data/ceph/certs/generate-certs.sh
```

## Common Operations

1. Generate certificates:
   ```bash
   make generate-certs
   ```

2. Start the Ceph cluster:
   ```bash
   make start
   ```

3. Check cluster status:
   ```bash
   make status
   ```

4. View logs:
   ```bash
   make logs
   ```

5. Stop the cluster:
   ```bash
   make stop
   ```

## Troubleshooting

1. If you encounter permission issues:
   ```bash
   sudo chown -R $USER:$USER /data/ceph
   ```

2. To verify Docker permissions:
   ```bash
   groups | grep docker
   ```

3. To check Ceph cluster health:
   ```bash
   docker exec ceph_mon_1 ceph health
   ```

## Security Notes

1. Always change default passwords in the .env file
2. Keep certificates secure and backup the CA private key
3. Regularly update Docker images for security patches
4. Restrict network access to Ceph ports
5. Monitor logs for suspicious activity

## Maintenance

1. Regular backups of /data/ceph/config
2. Monitor disk usage in /data/ceph/data
3. Keep Docker and docker-compose updated
4. Regularly check for Ceph updates

Remember to replace placeholder values in the .env file with secure credentials before deploying to production.
