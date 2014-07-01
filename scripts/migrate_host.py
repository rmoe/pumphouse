import argparse
import logging
import os
import pyipmi
import pyipmi.bmc
import sys
import time
import urllib2
import yaml

sys.path.append('../pumphouse')
from operator import attrgetter

from pumphouse.baremetal import Fuel
from pumphouse.baremetal import IPMI


LOG = logging.getLogger(__name__)

SOURCE_CLOUD_TAG = 'source'
FUEL_MASTER_NODE_TAG = 'fuel.master'
FUEL_API_IFACE_TAG = 'fuel.api'
DEFAULT_INVENTORY_FILE = 'inventory.yaml'


class Error(Exception):
    pass


class NotFound(Error):
    pass


class TimeoutException(Error):
    pass


def safe_load_yaml(filename):
    with open(filename) as f:
        return yaml.safe_load(f.read())


def get_parser():
    parser = argparse.ArgumentParser(description="Migrates physical servers "
                                                 "from OpenStack cloud to "
                                                 "Mirantis OpenStack cloud.")
    parser.add_argument("-i", "--inventory",
                        default=None,
                        type=safe_load_yaml,
                        help="A filename of an inventory of datacenter "
                             "hardware")
    parser.add_argument("-e", "--env-id",
                        default=1,
                        type=int,
                        help="An ID of target Mirantis "
                             "OpenStack cloud in Fuel")
    parser.add_argument("hostname",
                        type=str,
                        help="A host reference of server to migrate as it "
                        "appears in the 'hosts' section in INVENTORY file")
    return parser


def read_configuration(stream):
    with stream as f:
        return yaml.safe_load(f.read())


def get_fuel_endpoint(config):
    for host_ref in config['hosts']:
        host = config['hosts'][host_ref]
        if FUEL_MASTER_NODE_TAG in host['notes']:
            fuel_master = host
    for iface_ref in fuel_master['interfaces']:
        iface = fuel_master['interfaces'][iface_ref]
        if FUEL_API_IFACE_TAG in iface['tags']:
            endpoint = iface['ip'][0]
    return endpoint


def main():
    parser = get_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    env_id = args.env_id
    hostname = args.hostname
    if args.inventory is not None:
        inventory = args.inventory
    else:
        inventory = safe_load_yaml(DEFAULT_INVENTORY_FILE)
    fuel_endpoint = get_fuel_endpoint(inventory)
    inventory_host = inventory['hosts'][hostname]

    if SOURCE_CLOUD_TAG not in inventory_host['notes']:
        LOG.exception("Host not in source cloud: %s", inventory_host)
        raise Error

    fuel = Fuel(fuel_endpoint, env_id)
    ipmi = IPMI.from_dict(inventory_host['ipmi'])
    ipmi.force_pxeboot(inventory_host)
    node = fuel.wait_for_node('discover')
    fuel.assign_role(node)
    try:
        fuel.env.deploy_changes()
    except urllib2.HTTPError as exc:
        LOG.exception("Cannot deploy changes: %s", exc.code)
        raise Error
    node = fuel.wait_for_node('ready', node.id, 3600)
    LOG.info("Node deployed: %s", node.data)


if __name__ == "__main__":
    main()
