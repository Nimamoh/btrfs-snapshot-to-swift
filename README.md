# ❄ BTRFS snapshots to OpenShift container ❄

Tool for synchronizing btrfs snapshots to a [swift compliant object store](https://docs.openstack.org/swift/latest/).

Given a subvolume, this script detects its local snapshots. Each local snapshot is then synchronized with swift container. The snapshots are backup'd in an incremental fashion.   

Synchronization process consists of:

 - Giving an unique name for each local snapshot. See [naming convention](#naming-convention-of-snapshots)
 - Check which snapshot is already in swift container (solely based on name)
 - For each snapshot *only present on local filesystem*, compute the difference with previous snapshot (based on creation date) and upload it to swift.

> Content is first computed/stored locally before being sent to swift. Computation/storage process is also called "preparation phase".   
> Preparation phase is performed with wrapping `btrfs-send` command (optionally report progress with `pv`). Upload is done with [swiftclient](https://docs.openstack.org/python-swiftclient/latest/service-api.html#upload)

## Gotchas, how to use correctly

 - It only works with local readonly snapshots. Also, since it identifies snapshots using a naming convention, don't update / replace snapshot content. Prefer "immutable" snapshot with name based on date.

 - It performs incremental backups, this means that content stored in swift container form a "chain" which should not be broken. Don't manually delete archived content.

 - Incremental changes is computed with local snapshots, if you delete local snapshots, make sure to keep the *last archived one* locally to conserve incremental behavior. Otherwise, the whole snapshot will be archived.

 - Content is first computed and store locally in "working directory", it is then uploaded in swift. For large subvolumes (especially in initial archiving of the whole content), make sure you have enough space in working directory.

 - Last but not least, as a good practice advice, you should regularly check that your backups can successfully be restored.

### Naming convention of snapshots

Each snapshot is identified by a name which is computed from its relative path such as, for a relative path `<relative_path>`:

- We prefix the UUID of the root filesystem of the snapshot `<UUIDFS>/`
- We escape each `/` folder separator character with a literal `\x2f`

- For a snapshot with relative path `snapshots/subolume-1`. Its name would be `<UUIDFS>\x2fsnapshtos\x2fsubvolume-1`

**We do not accept snapshot which relative path contains literal `\x2f`**

## How to install

Tool is not available through PyPI. You can install the script with [pipx](https://github.com/pypa/pipx).

```fish
pipx install --system-site-packages --editable (pwd)
```

>
> It is important to use `--system-site-packages` since script relies on [libbtrfsutil](https://github.com/kdave/btrfs-progs/tree/master/libbtrfsutil) python bindings to work.
>

## How to use

Script is available through `btrfs-snapshot-to-swift` command.

```
usage: btrfs-snapshots-to-swift [-h] --container-name CONTAINER_NAME [--work-dir WORK_DIR] [--dry-run] [--age-recipient AGE_RECIPIENT]
                                [--syslog [SYSLOG]] [-v]
                                path

List snapshots of subvolume

positional arguments:
  path                  Path of subvolume.

optional arguments:
  -h, --help            show this help message and exit
  --container-name CONTAINER_NAME
                        Container name of your swift service.
  --work-dir WORK_DIR   Directory in which the script will store snapshots before sending.
  --dry-run             Dry run mode. Do everything except upload.
  --age-recipient AGE_RECIPIENT
                        Enable encryption through age, using provided recipient. see https://github.com/FiloSottile/age.
  --syslog [SYSLOG]     Log to local syslogd socket '/dev/log'.
  -v                    Enable debug messages
```

## Troubleshooting

### ModuleNotFoundError: No module named 'btrfsutil'

Ensure that your python environment from which you launch the script have libbtrfsutil python bindings available.   
For Ubuntu, these bindings are available with `python3-btrfsutil` package.   

### swiftclient.exceptions.ClientException: No tenant specified

You need to have swift credentials available as environment variable during the script execution.

See [API documentation](https://docs.openstack.org/python-swiftclient/xena/service-api.html#authentication) for more information.

## Dev notes

### OpenShift credentials

Retrieve credentials from your openstack interface, then create an .env file containing credentials as varenv:

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

In order to enable it in venv. Create a `.venv/lib/<python_version>/site-packages/.pth` file containing the path containing the btrfsutil C extension.

Example:

`./.venv/lib/python3.9/site-packages/.pth` containing:
```text
/usr/lib/python3/dist-packages
```

### Create a local btrfs filesystem for testing

Embedding a btrfs filesystem in a file for testing, for example:

```fish
dd if=/dev/zero of=loopbackfile.img bs=512K count=1K # loopbackfile of 512M 
sudo losetup -fP loopbackfile.img
sudo mkfs.btrfs /dev/loop0 # assuming your loopbackfile is assigned loop0
sudo mount -t btrfs -o noatime /dev/loop0 ./fs
```

## Optional improvements

- [] Other ways to authenticate with swift than env var
