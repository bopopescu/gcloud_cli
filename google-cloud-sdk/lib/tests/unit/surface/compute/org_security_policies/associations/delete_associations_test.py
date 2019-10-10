# -*- coding: utf-8 -*- #
# Copyright 2019 Google LLC. All Rights Reserved.
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
"""Tests for the organization security policy associations delete subcommand."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from googlecloudsdk.calliope import base as calliope_base
from googlecloudsdk.core import resources
from tests.lib import test_case
from tests.lib.surface.compute import test_base


class OrgSecurityPoliciesAssociationsDeleteAlphaTest(test_base.BaseTest):

  def PreSetUp(self):
    self.track = calliope_base.ReleaseTrack.ALPHA

  def SetUp(self):
    self.SelectApi(self.track.prefix)
    self.resources = resources.REGISTRY.Clone()
    self.resources.RegisterApiByName('compute', 'alpha')

  def CheckOrgSecurityPolicyRequest(self, **kwargs):
    self.CheckRequests([
        (self.compute.organizationSecurityPolicies, 'RemoveAssociation',
         self.messages
         .ComputeOrganizationSecurityPoliciesRemoveAssociationRequest(
             securityPolicy='12345', name='associ-name'))
    ])

  def testAssociationsDeleteOrgSecurityPolicy(self):
    self.Run('compute org-security-policies associations delete associ-name '
             '--security-policy 12345')

    self.CheckOrgSecurityPolicyRequest()


if __name__ == '__main__':
  test_case.main()