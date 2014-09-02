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

from pumphouse import events
from pumphouse import task
from pumphouse import flows
from pumphouse.tasks import utils as task_utils
from pumphouse import utils


LOG = logging.getLogger(__name__)

provision_server = flows.register("provision_server")


class ServerStartMigrationEvent(task.BaseCloudTask):
    def execute(self, server_id):
        LOG.info("Migration of server %r started", server_id)
        events.emit("server migrate", {
            "id": server_id,
        }, namespace="/events")

    # TODO(akscram): Here we can emit the event to report about
    #                failures during migration process. It's commented
    #                because didn't supported by UI and untested.
#    def revert(self, server_id, result, flow_failures):
#        LOG.info("Migration of server %r failed by reason %s",
#                 server_id, result)
#        events.emit("server migration failed", {
#            "id": server_id,
#        }, namespace="/events")


class ServerSuccessMigrationEvent(task.BaseCloudsTask):
    def execute(self, src_server_info, dst_server_info):
        events.emit("server migrated", {
            "source_id": src_server_info["id"],
            "destination_id": dst_server_info["id"],
        }, namespace="/events")


class RetrieveServer(task.BaseCloudTask):
    def execute(self, server_id):
        server = self.cloud.nova.servers.get(server_id)
        return server.to_dict()


class SuspendServer(task.BaseCloudTask):
    def execute(self, server_info):
        self.cloud.nova.servers.suspend(server_info["id"])
        server = utils.wait_for(server_info["id"], self.cloud.nova.servers.get,
                                value="SUSPENDED")
        self.suspend_event(server)
        return server.to_dict()

    def suspend_event(self, server):
        LOG.info("Server suspended: %s", server.id)
        events.emit("server suspended", {
            "id": server.id,
            "cloud": self.cloud.name,
        }, namespace="/events")

    def revert(self, server_info, result, flow_failures):
        self.cloud.nova.servers.resume(server_info["id"])
        server = utils.wait_for(server_info["id"], self.cloud.nova.servers.get,
                                value="ACTIVE")
        self.resume_event(server)
        return server.to_dict()

    def resume_event(self, server):
        LOG.info("Server resumed: %s", server.id)
        events.emit("server resumed", {
            "id": server.id,
            "cloud": self.cloud.name,
        }, namespace="/events")


class BootServerFromImage(task.BaseCloudTask):
    def execute(self, server_info, image_info, flavor_info):
        # TODO(akscram): Network information doesn't saved.
        server = self.cloud.nova.servers.create(server_info["name"],
                                                image_info["id"],
                                                flavor_info["id"])
        server = utils.wait_for(server, self.cloud.nova.servers.get,
                                value="ACTIVE")
        self.spawn_event(server)
        return server.to_dict()

    def spawn_event(self, server):
        LOG.info("Server spawned: %s", server.id)
        try:
            hostname = getattr(server, "OS-EXT-SRV-ATTR:hypervisor_hostname")
        except AttributeError as err:
            LOG.warning("Could not get 'hypervisor_hostname' attribute from "
                        "server %r: %s", server.id, err)
        else:
            events.emit("server boot", {
                "cloud": self.cloud.name,
                "id": server.id,
                "name": server.name,
                "tenant_id": server.tenant_id,
                # XXX(akscram): It may suitable only for images
                #               (untested for snapshots)
                "image_id": server.image["id"],
                "host_name": hostname,
                "status": "active",
            }, namespace="/events")


class TerminateServer(task.BaseCloudTask):
    def execute(self, server_info):
        self.cloud.nova.servers.delete(server_info["id"])
        self.terminate_event(server_info)

    def terminate_event(self, server):
        LOG.info("Server terminated: %s", server["id"])
        events.emit("server terminate", {
            "cloud": self.cloud.name,
            "id": server["id"],
        }, namespace="/events")


@provision_server.add("image")
def reprovision_server(src, dst, store, server_id, image_id, flavor_id):
    server_sync = "server-{}-sync".format(server_id)
    server_binding = "server-{}".format(server_id)
    server_retrieve = "server-{}-retrieve".format(server_id)
    server_suspend = "server-{}-suspend".format(server_id)
    server_boot = "server-{}-boot".format(server_id)
    server_terminate = "server-{}-terminate".format(server_id)
    image_ensure = "image-{}-ensure".format(image_id)
    flavor_ensure = "flavor-{}-ensure".format(flavor_id)
    flow = linear_flow.Flow("migrate-server-{}".format(server_id))
    flow.add(task_utils.SyncPoint(name=server_sync,
                                  requires=[image_ensure, flavor_ensure]))
    flow.add(RetrieveServer(src,
                            name=server_binding,
                            provides=server_retrieve,
                            rebind=[server_binding]))
    flow.add(SuspendServer(src,
                           name=server_retrieve,
                           provides=server_suspend,
                           rebind=[server_retrieve]))
    flow.add(BootServerFromImage(dst,
                                 name=server_boot,
                                 provides=server_boot,
                                 rebind=[server_suspend, image_ensure,
                                         flavor_ensure]
                                 ))
    flow.add(TerminateServer(src,
                             name=server_terminate,
                             rebind=[server_suspend]))
    store[server_binding] = server_id
    return (flow, store)


@provision_server.add("snapshot")
def reprovision_server_with_snapshot(src, dst, store, server_id, flavor_id):
    server_start_event = "server-{}-start-event".format(server_id)
    server_finish_event = "server-{}-finish-event".format(server_id)
    server_sync = "server-{}-sync".format(server_id)
    server_binding = "server-{}".format(server_id)
    server_retrieve = "server-{}-retrieve".format(server_id)
    server_suspend = "server-{}-suspend".format(server_id)
    server_boot = "server-{}-boot".format(server_id)
    server_terminate = "server-{}-terminate".format(server_id)
    image_ensure = "snapshot-{}-ensure".format(server_id)
    flavor_ensure = "flavor-{}-ensure".format(flavor_id)
    flow = linear_flow.Flow("migrate-server-{}".format(server_id))
    flow.add(task_utils.SyncPoint(name=server_sync,
                                  requires=[image_ensure, flavor_ensure]))
    flow.add(ServerStartMigrationEvent(src,
                                       name=server_start_event,
                                       rebind=[server_binding]))
    flow.add(RetrieveServer(src,
                            name=server_binding,
                            provides=server_retrieve,
                            rebind=[server_binding]))
    flow.add(SuspendServer(src,
                           name=server_retrieve,
                           provides=server_suspend,
                           rebind=[server_retrieve]))
    flow.add(BootServerFromImage(dst,
                                 name=server_boot,
                                 provides=server_boot,
                                 rebind=[server_suspend, image_ensure,
                                         flavor_ensure]
                                 ))
    flow.add(TerminateServer(src,
                             name=server_terminate,
                             rebind=[server_suspend]))
    flow.add(ServerSuccessMigrationEvent(src, dst,
                                         name=server_finish_event,
                                         rebind=[server_retrieve,
                                                 server_boot]))
    store[server_binding] = server_id
    return (flow, store)