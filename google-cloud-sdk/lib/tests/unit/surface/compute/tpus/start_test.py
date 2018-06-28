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
"""tpus describe tests."""

from __future__ import absolute_import
from __future__ import unicode_literals
from googlecloudsdk.calliope import base as calliope_base
from googlecloudsdk.core import properties
from googlecloudsdk.core import resources
from tests.lib import parameterized
from tests.lib import test_case
from tests.lib.surface.compute.tpus import base


@parameterized.parameters([calliope_base.ReleaseTrack.ALPHA,
                           calliope_base.ReleaseTrack.BETA])
class StartTest(base.TpuUnitTestBase):

  def SetUp(self):
    self.zone = 'us-central1-c'
    self.track = calliope_base.ReleaseTrack.ALPHA
    properties.VALUES.compute.zone.Set(self.zone)
    self.start_op_ref = resources.REGISTRY.Parse(
        'start',
        params={
            'projectsId': self.Project(),
            'locationsId': self.zone},
        collection='tpu.projects.locations.operations')
    self.node_ref = resources.REGISTRY.Parse(
        'mytpu',
        params={
            'projectsId': self.Project(),
            'locationsId': self.zone},
        collection='tpu.projects.locations.nodes')

  def testStart(self, track):
    self._SetTrack(track)
    start_response = self.GetOperationResponse(
        op_name=self.start_op_ref.RelativeName())
    self.mock_client.projects_locations_nodes.Start.Expect(
        request=self.messages.TpuProjectsLocationsNodesStartRequest(
            name=self.node_ref.RelativeName(),
            startNodeRequest=self.messages.StartNodeRequest()),
        response=start_response)

    self.mock_client.projects_locations_operations.Get.Expect(
        request=self.messages.TpuProjectsLocationsOperationsGetRequest(
            name=self.start_op_ref.RelativeName()),
        response=start_response)

    self.assertEqual(self.Run('compute tpus start mytpu'), start_response)

  def testStartAsync(self, track):
    self._SetTrack(track)
    start_response = self.GetOperationResponse(
        op_name=self.start_op_ref.RelativeName())
    self.mock_client.projects_locations_nodes.Start.Expect(
        request=self.messages.TpuProjectsLocationsNodesStartRequest(
            name=self.node_ref.RelativeName(),
            startNodeRequest=self.messages.StartNodeRequest()),
        response=start_response)

    self.assertEqual(self.Run('compute tpus start mytpu --async'),
                     start_response)

if __name__ == '__main__':
  test_case.main()