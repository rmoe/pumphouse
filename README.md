Pumphouse
=========

Pumphouse provides a tool for forklift upgrade of OpenStack clouds. This type of
upgrade combines migration of workloads (i.e. tenants and their resources) with
management of bare-metal hosts. It allows to update cloud on the same set of
hardware.

Migration of resources allows to release hosts from original cloud. Those hosts
could be upgraded then to latest version of OpenStack. Pumphouse uses Fuel,
open-source deployment automation engine, to install the platform component onto
hosts.

## Requirements and constraints

Following OpenStack releases can be upgraded with Pumphouse:

- Havana (2013.2)
- Icehouse (2014.1)
- Juno (2014.2)

Following network managers are suitable for upgrade:

- `nova-network` in FlatDHCP and VLAN modes
- `neutron` in OVS+GRE mode

Every hypervisor host in original cloud must have at least 2 NICs for:

- Admin/PXE boot network
- Management/Public/Private networks

Usage
=====

Pumphouse package includes server binary that provides REST HTTP-based API, and
two scripts that can work standalone. Scripts allow for more granularity than
API. Scripts could be used to implement more sophisticated migration strategies.

## Installation

To install the pumphouse package use the command:

```sh
$ pip install --allow-external mysql-connector-python .
```

Alternatively, if you want to install in Python virtual environment, you could
use `tox` with `apitest` env:

```sh
$ tox -e apitest
```

## `pumphouse-api` - Pumphouse API Server

This script provides API server for Pumphouse with UI. To run the server use
the following command:

```sh
$ pumphouse-api [config]
```

The config file is an YAML file with the following structure:

```
DEBUG: true
CLOUDS:
    source: # a role name of the cloud, source or destination
        environment: source-env # a name of the environment in FUEL
        endpoint: # OpenStack APIs admin access credentials
            auth_url: http://172.18.18.157:5000/v2.0 # URL of the Keystone service
            username: admin # name of the user with administrative access
            password: secrete # password
            tenant_name: admin # name of the administrative tenant
        identity: # Identity store access credentials, for passwords retrieval
            connection: mysql+mysqlconnector://root:stackdb@172.18.18.157/keystone
    destination:
        environment: destination-env # a name of the environment in FUEL
        endpoint:
            auth_url: http://172.18.18.132:5000/v2.0
            username: admin
            password: secrete
            tenant_name: admin
        identity:
            connection: mysql+mysqlconnector://keystone:secrete@172.18.18.132/keystone
    fuel:
        endpoint: # FUEL admin access credentials
            host: 172.18.167.155
            port: 8000
            username: admin
            password: admin
```

The `environment` and `fuel` sections are optional and necessary only for
the reassigning of hosts functionality.

See example in [`doc/samples/api-config.yaml`](doc/samples/api-config.yaml)
file.

## CLI Scripts

The pumphouse package provides CLI tool with migration, evacuation and
reassigning features. You could look up a list of commands supported by this
script using the following command:

```sh
$ pumphouse --help
```

There are major subcommands: `migrate`, `evacuate` and `reassign`.

### Migration of resources (`pumphouse migrate`)

This command migrates resources from one instance of OpenStack to another using
APIs of OpenStack services

To migrate resources from one cloud to another, add configuration of endpoints
of source and destination clouds to configuration file `config.yaml`. See
example in [`doc/samples/config.yaml`](doc/samples/config.yaml) file.


### Evacuation instances from a hypervisor (`pumphouse evacuate`)

This command evacuates instances from the the hypervisor with a given host
within the source cloud.

```sh
$ pumphouse config evacuate [-h] hostname
```

### Reassigning (`pumphouse reassign`)

This command reassignes the hypervisor host from one environment to another.

## Quick Start

To quickly try out the Pumphouse, install 2 OpenStack clouds using your
favorite installer. Then install Pumphouse using instructions above, and create
configuration based on samples.

Now prepare your source cloud for the test run by adding certain resources to
it. Use `setup` flag of the migration script:

```sh
$ pumphouse config.yaml setup
```

Then run migration script as follows:

```sh
$ pumphouse config.yaml migrate <resource_class> --ids <ID> [<ID> ...]
```

`<resource_class>` could be one of the following:

* `images` - replicate images from source to destination cloud.
* `identity` - replicate complete identity structure (including projects, users
  and roles with assignment) of the source cloud in the destination cloud.
* `resources` - migrate all resources that belong to the tenant/project
  identified by its ID in source cloud and all resources they depend on.
* `volumes` - migrate all volumes with specified IDs.

You can obtain `<ID>`s of resources you want to migrate by using standard
OpenStack clients or Horizon dashboard UI.

If you need to clean your source or target cloud up, run migration script
with `cleanup` command and specify which cloud you want to clean up:

```sh
$ pumphouse config.yaml cleanup { source | destination }
```

See detailed usage scenario in [USAGE](doc/USAGE.md) document.

## User Interface

To perform installation with a third-party user interface the package should be
prepared. It is a simple action and it require just copy files in the 
`pumphouse/api/static directory`. A file with the index.html name must be there.

You can prepare for running API service with 3rd-party user interface with:

```sh
$ env SERVER_NAME=$SERVER_NAME \
UI_URL=$UI_URL \
make api
```

Set `$SERVER_NAME` to `address:port` of the server you're installing on. Defaults
to `127.0.0.1:5000`.
Set `$UI_URL` to the working Git repo URL where user interface is being
developed.

## Docker

A prebuilt docker image from the included `Dockerfile` is available

```sh
docker pull xarses/pumphouse
```
