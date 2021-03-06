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

from taskflow.patterns import graph_flow, unordered_flow

from pumphouse.tasks import server_resources


LOG = logging.getLogger(__name__)


def migrate_resources(context, tenant_id):
    servers = context.src_cloud.nova.servers.list(
        search_opts={'all_tenants': 1, 'tenant_id': tenant_id})
    flow = graph_flow.Flow("migrate-resources-{}".format(tenant_id))
    servers_flow = unordered_flow.Flow("migrate-servers-{}".format(tenant_id))
    migrate_server = server_resources.migrate_server
    for server in servers:
        server_binding = "server-{}".format(server.id)
        if server_binding not in context.store:
            resources, server_flow = migrate_server(context, server.id)
            flow.add(*resources)
            servers_flow.add(server_flow)
    flow.add(servers_flow)
    return flow
