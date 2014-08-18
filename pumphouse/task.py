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

from taskflow import task


class BaseCloudTask(task.Task):
    def __init__(self, cloud, *args, **kwargs):
        super(BaseCloudTask, self).__init__(*args, **kwargs)
        self.cloud = cloud


class BaseCloudsTask(task.Task):
    def __init__(self, src_cloud, dst_cloud, *args, **kwargs):
        super(BaseCloudsTask, self).__init__(*args, **kwargs)
        self.src_cloud = src_cloud
        self.dst_cloud = dst_cloud


class BaseRetrieveTask(BaseCloudTask):
    def execute(self, obj_id):
        obj = self.retrieve(obj_id)
        serialized_obj = self.serialize(obj)
        return serialized_obj

    def retrieve(self, obj_id):
        raise NotImplementedError()

    def serialize(self, obj):
        return obj.to_dict()
