# ❄ BTRFS snapshots to cloud archive ❄

Tools for automating pushing btrfs snapshot to [cloud archive cold storage service](https://www.ovhcloud.com/fr/public-cloud/cloud-archive/)

## Dev notes

### OpenShift credentials

Retrieve credentials from your openstack interface, then create an .env file containing credentials as varenv. See [OVH connection guide](https://docs.ovh.com/fr/storage/pca/cyberduck/) as an inspiration

Example of env file:
```.env
# Cloud archive creds
ST_AUTH_VERSION=3
OS_USERNAME=user-xxxx
OS_PASSWORD=passwordc
OS_PROJECT_NAME=02103924177
OS_AUTH_URL=https://auth.cloud.ovh.net/v3
OS_REGION_NAME=GRA
```

### btrfsutil python bindings

Using btrfsutil python bindings. While it's provided with btrfs-progs on arch. For ubuntu: `apt install python3-btrfsutil`

### Create a local btrfs filesystem for testing

Embedding a btrfs filesystem in a file for testing, for example:
```fish
dd if=/dev/zero of=loopbackfile.img bs=512K count=1K # loopbackfile of 512M 
sudo losetup -fP loopbackfile.img
sudo mkfs.btrfs /dev/loop0 # assuming your loopbackfile is assigned loop0
sudo mount -t btrfs -o noatime /dev/loop0 ./fs
```
