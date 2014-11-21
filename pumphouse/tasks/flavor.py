# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

import logging

from taskflow.patterns import linear_flow

from pumphouse import exceptions
from pumphouse import events
from pumphouse import task


LOG = logging.getLogger(__name__)


class RetrieveFlavor(task.BaseCloudTask):
    def execute(self, flavor_id):
        flavor = self.cloud.nova.flavors.get(flavor_id)
        return flavor.to_dict()


class EnsureFlavor(task.BaseCloudTask):
    def execute(self, flavor_info):
        try:
            # TODO(akscram): Ensure that the flavor with the same ID is
            #                equal to the source flavor.
            flavor = self.cloud.nova.flavors.get(flavor_info["id"])
        except exceptions.nova_excs.NotFound:
            flavor = self.cloud.nova.flavors.create(
                flavor_info["name"],
                flavor_info["ram"],
                flavor_info["vcpus"],
                flavor_info["disk"],
                flavorid=flavor_info["id"],
                ephemeral=flavor_info["OS-FLV-EXT-DATA:ephemeral"],
                swap=flavor_info["swap"] or 0,
                rxtx_factor=flavor_info["rxtx_factor"],
                is_public=flavor_info["os-flavor-access:is_public"]
            )
            self.created_event(flavor)
        return flavor.to_dict()

    def created_event(self, flavor):
        LOG.info("Flavor created: %s", flavor.id)
        events.emit("create", {
            "id": flavor.id,
            "type": "flavor",
            "cloud": self.cloud.name,
            "data": flavor.to_dict(),
        }, namespace="/events")


def migrate_flavor(context, flavor_id):
    flavor_binding = "flavor-{}".format(flavor_id)
    flavor_retrieve = "{}-retrieve".format(flavor_binding)
    flavor_ensure = "{}-ensure".format(flavor_binding)
    flow = linear_flow.Flow("migrate-flavor-{}".format(flavor_id)).add(
        RetrieveFlavor(context.src_cloud,
                       name=flavor_binding,
                       provides=flavor_binding,
                       rebind=[flavor_retrieve]),
        EnsureFlavor(context.dst_cloud,
                     name=flavor_ensure,
                     provides=flavor_ensure,
                     rebind=[flavor_binding])
    )
    context.store[flavor_retrieve] = flavor_id
    return flow
