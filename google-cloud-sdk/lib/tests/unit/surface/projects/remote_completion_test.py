# Copyright 2014 Google Inc. All Rights Reserved.
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

"""Tests for projects list."""

from __future__ import absolute_import
from __future__ import unicode_literals
from googlecloudsdk.core import properties
from tests.lib import cli_test_base
from tests.lib import test_case
from tests.lib.surface.projects import base
from tests.lib.surface.projects import util


class RemoteCompletionTest(base.ProjectsUnitTestBase,
                           cli_test_base.CliTestBase):

  def SetUp(self):
    properties.VALUES.core.project.Set('my-project')
    test_projects = util.GetTestActiveProjectsList()
    self.mock_client.projects.List.Expect(
        self.messages.CloudresourcemanagerProjectsListRequest(
            pageSize=500,
            filter='lifecycleState:ACTIVE'),
        self.messages.ListProjectsResponse(projects=test_projects))

  def testDescribeCompletionAll(self):
    self.RunCompletion('beta projects describe ',
                       [
                           'feisty-catcher-644',
                           'test-project-2',
                           'test-project-3',
                       ])

  def testDescribeCompletion(self):
    self.RunCompletion('beta projects describe fe',
                       ['feisty-catcher-644'])

  def testProjectFlag(self):
    self.RunCompletion('--project fe',
                       ['feisty-catcher-644'])

  # This test is here because it relies on the project lister
  def testConfigSetProject(self):
    self.RunCompletion('config set project fe',
                       ['feisty-catcher-644'])


if __name__ == '__main__':
  test_case.main()
