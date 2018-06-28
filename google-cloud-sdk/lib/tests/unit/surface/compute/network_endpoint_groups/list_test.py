# Copyright 2018 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the network-endpoint-groups list subcommand."""

from __future__ import absolute_import
from __future__ import unicode_literals
from googlecloudsdk.calliope import base
from googlecloudsdk.core import properties
from tests.lib import test_case
from tests.lib.surface.compute import test_base
from tests.lib.surface.compute import test_resources
import mock


class NetworkEndpointGroupsListTest(test_base.BaseTest):

  def SetUp(self):
    self.track = base.ReleaseTrack.ALPHA
    self.SelectApi(self.track.prefix)
    list_json_patcher = mock.patch(
        'googlecloudsdk.api_lib.compute.request_helper.ListJson', autospec=True)
    self.addCleanup(list_json_patcher.stop)
    self.list_json = list_json_patcher.start()

  def testTableOutput(self):
    self.list_json.side_effect = iter([test_resources.NETWORK_ENDPOINT_GROUPS])
    self.Run('compute network-endpoint-groups list')
    self.list_json.assert_called_once_with(
        requests=[(
            self.compute.networkEndpointGroups,
            'AggregatedList',
            self.messages.ComputeNetworkEndpointGroupsAggregatedListRequest(
                project='my-project'))],
        http=self.mock_http(),
        batch_url=self.batch_url,
        errors=[])

    self.AssertOutputEquals("""\
---
description: My NEG 1
kind: compute#networkEndpointGroup
loadBalancer:
  network: https://www.googleapis.com/compute/v1/projects/my-project/global/networks/network-1
  zone: zone-1
name: my-neg1
networkEndpointType: GCE_VM_IP_PORT
selfLink: https://www.googleapis.com/compute/alpha/projects/my-project/zones/zone-1/networkEndpointGroups/my-neg1
size: 5
type: LOAD_BALANCING
---
description: My NEG Too
kind: compute#networkEndpointGroup
loadBalancer:
  network: https://www.googleapis.com/compute/v1/projects/my-project/global/networks/network-2
  zone: zone-2
name: my-neg2
networkEndpointType: GCE_VM_IP_PORT
selfLink: https://www.googleapis.com/compute/alpha/projects/my-project/zones/zone-2/networkEndpointGroups/my-neg2
size: 2
type: LOAD_BALANCING
""", normalize_space=True)

  def testCommandOuput(self):
    properties.VALUES.core.user_output_enabled.Set(False)
    self.list_json.side_effect = iter([test_resources.NETWORK_ENDPOINT_GROUPS])
    result = list(self.Run('compute network-endpoint-groups list'))
    self.list_json.assert_called_once_with(
        requests=[(
            self.compute.networkEndpointGroups,
            'AggregatedList',
            self.messages.ComputeNetworkEndpointGroupsAggregatedListRequest(
                project='my-project'))],
        http=self.mock_http(),
        batch_url=self.batch_url,
        errors=[])

    self.assertEqual(test_resources.NETWORK_ENDPOINT_GROUPS, result)


if __name__ == '__main__':
  test_case.main()