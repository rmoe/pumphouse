# Copyright (c) 2014 mirantis inc.
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

import unittest
from mock import MagicMock, Mock, patch

from pumphouse import task
from pumphouse import exceptions
from pumphouse.tasks import server


class TestServer(unittest.TestCase):
    def setUp(self):
        self.test_server_id = "123"
        self.server_info = {
            "id": self.test_server_id,
            "state": "ACTIVE",
            "name": "test-server-name",
        }

        self.image_info = {
            "id": "234"
        }
        self.flavor_info = {
            "id": "345"
        }
        self.user_info = {
            "name": "test-user-name"
        }
        self.tenant_info = {
            "name": "test-tenant-name"
        }

        self.server = Mock()
        self.server.status = "ACTIVE"
        self.server.image = self.image_info
        self.server.flavor = self.flavor_info
        self.server.to_dict.return_value = self.server_info

        self.cloud = Mock()
        self.cloud.name = "test-cloud"
        self.cloud.restrict.return_value = self.cloud
        self.cloud.nova.servers.get.return_value = self.server
        self.cloud.nova.servers.find.return_value = self.server
        self.cloud.nova.servers.create.return_value = self.server


class TestRetrieveServer(TestServer):
    def test_execute(self):
        retrieve_server = server.RetrieveServer(self.cloud)
        self.assertIsInstance(retrieve_server, task.BaseCloudTask)

        server_info = retrieve_server.execute(self.test_server_id)
        self.cloud.nova.servers.get.assert_called_once_with(
            self.test_server_id)
        self.server.to_dict.assert_called_once_with()
        self.assertEqual(self.server_info, server_info)


class TestSuspendServer(TestServer):
    def test_execute(self):
        suspend_server = server.SuspendServer(self.cloud)
        self.assertIsInstance(suspend_server, task.BaseCloudTask)

        server_suspended = self.server.copy()
        server_suspended.status = "SUSPENDED"
        self.cloud.nova.servers.get.return_value = server_suspended

        server_info = suspend_server.execute(self.server_info)
        self.cloud.nova.servers.suspend.assert_called_once_with(
            self.test_server_id)
        self.cloud.nova.servers.get.assert_called_once_with(
            self.test_server_id)

    def test_revert(self):
        suspend_server = server.SuspendServer(self.cloud)
        server_suspended = self.server.copy()
        server_suspended.status = "SUSPENDED"
        server_suspended_info = self.server_info.copy()
        server_suspended_info["status"] = "SUSPENDED"
        self.cloud.nova.servers.get.return_value = self.server
        result = MagicMock()
        flow_failures = MagicMock()

        server_info = suspend_server.revert(server_suspended_info,
                                            result,
                                            flow_failures)
        self.cloud.nova.servers.resume.assert_called_once_with(
            self.test_server_id)
        self.cloud.nova.servers.get.assert_called_once_with(
            self.test_server_id)


class TestBootServer(TestServer):
    def test_execute(self):
        boot_server = server.BootServerFromImage(self.cloud)
        self.assertIsInstance(boot_server, task.BaseCloudTask)

        server_info = boot_server.execute(self.server_info,
                                          self.image_info,
                                          self.flavor_info,
                                          self.user_info,
                                          self.tenant_info)
        self.cloud.restrict.assert_called_once_with(
            username=self.user_info["name"],
            tenant_name=self.tenant_info["name"],
            password="default")
        self.cloud.nova.servers.create.assert_called_once_with(
            self.server_info["name"],
            self.image_info["id"],
            self.flavor_info["id"])
        self.assertEqual(self.server_info, server_info)
