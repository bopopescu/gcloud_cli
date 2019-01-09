# -*- coding: utf-8 -*- #
# Copyright 2018 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
"""compute node templates get-iam-policy tests."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import textwrap

from apitools.base.py.testing import mock
from googlecloudsdk.api_lib.util import apis
from googlecloudsdk.calliope import base as calliope_base
from tests.lib import cli_test_base
from tests.lib import parameterized
from tests.lib import sdk_test_base
from tests.lib.surface.compute import test_resources


# TODO(b/117336602) Stop using parameterized for track parameterization.
@parameterized.parameters((calliope_base.ReleaseTrack.ALPHA, 'alpha'),
                          (calliope_base.ReleaseTrack.BETA, 'beta'))
class GetIamPolicyUnitTest(sdk_test_base.WithFakeAuth,
                           cli_test_base.CliTestBase, parameterized.TestCase):

  def _SetUp(self, track, api_version):
    self.messages = apis.GetMessagesModule('compute', api_version)
    self.mock_client = mock.Client(
        apis.GetClientClass('compute', api_version),
        real_client=apis.GetClientInstance(
            'compute', api_version, no_http=True))
    self.mock_client.Mock()
    self.addCleanup(self.mock_client.Unmock)
    self.track = track

  def testEmptyPolicyCase(self, track, api_version):
    self._SetUp(track, api_version)
    self.mock_client.nodeTemplates.GetIamPolicy.Expect(
        self.messages.ComputeNodeTemplatesGetIamPolicyRequest(
            resource='my-resource',
            project='fake-project',
            region='fake-region'),
        response=test_resources.EmptyIamPolicy(self.messages))

    self.Run('compute sole-tenancy node-templates get-iam-policy '
             'my-resource --region=fake-region')
    self.assertMultiLineEqual(
        self.GetOutput(),
        textwrap.dedent("""\
            etag: dGVzdA==
            """))

  def testSimpleResponseCase(self, track, api_version):
    self._SetUp(track, api_version)
    self.mock_client.nodeTemplates.GetIamPolicy.Expect(
        self.messages.ComputeNodeTemplatesGetIamPolicyRequest(
            resource='my-resource',
            project='fake-project',
            region='fake-region'),
        response=test_resources.IamPolicyWithOneBindingAndDifferentEtag(
            self.messages))

    self.Run('compute sole-tenancy node-templates get-iam-policy '
             'my-resource --region=fake-region')
    self.assertMultiLineEqual(
        self.GetOutput(),
        textwrap.dedent("""\
            bindings:
            - members:
              - user:testuser@google.com
              role: owner
            etag: ZXRhZ1R3bw==
            """))

  def testListCommandFilter(self, track, api_version):
    self._SetUp(track, api_version)
    self.mock_client.nodeTemplates.GetIamPolicy.Expect(
        self.messages.ComputeNodeTemplatesGetIamPolicyRequest(
            resource='my-resource',
            project='fake-project',
            region='fake-region'),
        response=test_resources.IamPolicyWithOneBindingAndDifferentEtag(
            self.messages))

    self.Run("""
        compute sole-tenancy node-templates get-iam-policy my-resource
        --region=fake-region
        --flatten=bindings[].members --filter=bindings.role:owner
        --format='value(bindings.members)'
        """)

    self.AssertOutputContains('user:testuser@google.com')


if __name__ == '__main__':
  sdk_test_base.main()