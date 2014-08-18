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

from pumphouse import task
from pumphouse import utils


LOG = logging.getLogger(__name__)


class RetrieveServer(task.BaseCloudTask):
    def execute(self, server_id):
        server = self.cloud.nova.servers.get(server_id)
        return server.to_dict()


class SuspendServer(task.BaseCloudTask):
    def execute(self, server_info):
        self.cloud.nova.servers.suspend(server_info)
        server = utils.wait_for(server_info, self.cloud.nova.servers.get,
                                value="SUSPENDED")
        return server.to_dict()

    def revert(self, server_info, result, flow_failures):
        self.cloud.nova.servers.resume(server_info)
        server = utils.wait_for(server_info, self.cloud.nova.servers.get,
                                value="ACTIVE")
        return server.to_dict()


class BootServerFromImage(task.BaseCloudTask):
    def execute(self, server_info, image_info, flavor_info):
        # TODO(akscram): Network information doesn't saved.
        server = self.cloud.nova.servers.create(server_info["name"],
                                                image_info["id"],
                                                flavor_info["id"])
        server = utils.wait_for(server, self.cloud.nova.servers.get,
                                value="ACTIVE")
        return server.to_dict()


class TerminateServer(task.BaseCloudTask):
    def execute(self, server_info):
        self.cloud.nova.servers.delete(server_info)


def migrate_server(src, dst, store, server_id, image_id, flavor_id):
    server_binding = "server-{}".format(server_id)
    server_retrieve = "server-{}-retrieve".format(server_id)
    server_suspend = "server-{}-suspend".format(server_id)
    server_boot = "server-{}-boot".format(server_id)
    image_ensure = "image-{}-ensure".format(image_id)
    flavor_ensure = "flavor-{}-ensure".format(flavor_id)
    flow = linear_flow.Flow("migrate-server-{}".format(server_id))
    flow.add(RetrieveServer(src,
                            name=server_binding,
                            provides=server_retrieve,
                            requires=[server_binding]))
    flow.add(SuspendServer(src,
                           name=server_binding,
                           provides=server_suspend,
                           requires=[server_retrieve]))
    flow.add(BootServerFromImage(dst,
                                 name=server_binding,
                                 provides=server_boot,
                                 requires=[server_suspend, image_ensure,
                                           flavor_ensure]
                                 ))
    flow.add(TerminateServer(src,
                             name=server_binding,
                             requires=[server_suspend]))
    store[server_binding] = server_id
    return (flow, store)
