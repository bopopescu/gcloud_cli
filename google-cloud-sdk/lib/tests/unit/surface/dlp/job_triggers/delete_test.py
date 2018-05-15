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
"""dlp job-triggers delete tests."""
from __future__ import absolute_import
from __future__ import unicode_literals

from googlecloudsdk.calliope import base as calliope_base
from googlecloudsdk.core import resources
from tests.lib import parameterized
from tests.lib import test_case
from tests.lib.surface.dlp import base


class DeleteTest(base.DlpUnitTestBase):
  """dlp job-triggers delete tests."""

  @parameterized.parameters([calliope_base.ReleaseTrack.ALPHA])
  def testDelete(self, track):
    self.track = track
    self.StartPatch('time.sleep')
    trigger_ref = resources.REGISTRY.Parse(
        'my_trigger', params={'projectsId': self.Project()},
        collection='dlp.projects.jobTriggers')
    delete_request = self.msg.DlpProjectsJobTriggersDeleteRequest(
        name=trigger_ref.RelativeName())
    self.client.projects_jobTriggers.Delete.Expect(
        request=delete_request, response=self.msg.GoogleProtobufEmpty())
    self.WriteInput('y')
    self.Run('dlp job-triggers delete my_trigger')

if __name__ == '__main__':
  test_case.main()
