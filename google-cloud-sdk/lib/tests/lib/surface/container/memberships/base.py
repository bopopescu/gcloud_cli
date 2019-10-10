# -*- coding: utf-8 -*- #
# Copyright 2019 Google LLC. All Rights Reserved.

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
"""Base classes for memberships tests."""
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from apitools.base.py.testing import mock as apimock
from googlecloudsdk.api_lib.util import apis as core_apis
from googlecloudsdk.core import resources
from tests.lib import cli_test_base
from tests.lib import sdk_test_base

import six


class MembershipsTestBase(cli_test_base.CliTestBase,
                          sdk_test_base.WithFakeAuth):
  """Base class for membership testing."""

  MODULE_NAME = 'gkehub'
  API_VERSION = 'v1beta1'
  MEMBERSHIP_DESCRIPTION = 'my-external-cluster'
  MEMBERSHIP_SELF_LINK = 'my-external-cluster'
  MEMBERSHIP_NAME = '12345-abcde'

  def SetUp(self):
    self.messages = core_apis.GetMessagesModule(self.MODULE_NAME,
                                                self.API_VERSION)
    self.mocked_client = apimock.Client(
        client_class=core_apis.GetClientClass(self.MODULE_NAME,
                                              self.API_VERSION))
    self.mocked_client.Mock()
    self.addCleanup(self.mocked_client.Unmock)

    self.wait_operation_ref = resources.REGISTRY.Parse(
        'operation-1414184316101-d4546dd2',
        collection='gkehub.projects.locations.operations',
        params={
            'locationsId': 'global',
            'projectsId': self.Project(),
        },
        api_version=self.API_VERSION)
    self.wait_operation_relative_name = self.wait_operation_ref.RelativeName()

    self.parent = 'projects/{0}/locations/global'.format(self.Project())
    self.membership = '{0}/memberships/{1}'.format(self.parent,
                                                   self.MEMBERSHIP_NAME)

  def _RunMembershipCommand(self, cmd):
    prefix = ['container', 'memberships']
    if isinstance(cmd, six.string_types):
      return self.Run(' '.join(prefix + [cmd]))
    return self.Run(prefix + cmd)

  def _MakeMembership(self,
                      name=None,
                      description=None,
                      gke_cluster_self_link=None,
                      labels_dict=None):
    membership = self.messages.Membership(
        name=name,
        description=description,
        labels=self._MakeLabelsProto(labels_dict) if labels_dict else None)
    if gke_cluster_self_link:
      membership.endpoint = self.messages.MembershipEndpoint(
          gkeCluster=self.messages.GkeCluster(
              resourceLink=gke_cluster_self_link))
    return membership

  def _MakeLabelsProto(self, labels_dict):
    return self.messages.Membership.LabelsValue(additionalProperties=[
        self.messages.Membership.LabelsValue.AdditionalProperty(
            key=key, value=value) for key, value in sorted(labels_dict.items())
    ])

  def _MakeOperation(self, name=None, done=False, error=None, response=None):
    operation = self.messages.Operation(
        name=name or self.wait_operation_relative_name, done=done, error=error)
    if done:
      operation.response = response
    return operation

  def ExpectGetMembership(self, membership):
    self.mocked_client.projects_locations_memberships.Get.Expect(
        (self.messages.GkehubProjectsLocationsMembershipsGetRequest(
            name=self.membership)),
        response=membership)

  def ExpectCreateMembership(self, membership, response):
    self.mocked_client.projects_locations_memberships.Create.Expect(
        (self.messages.GkehubProjectsLocationsMembershipsCreateRequest(
            parent=self.parent,
            membershipId=self.MEMBERSHIP_NAME,
            membership=membership)),
        response=response)

  def ExpectDeleteMembership(self, membership, response):
    self.mocked_client.projects_locations_memberships.Delete.Expect(
        request=(
            self.messages.GkehubProjectsLocationsMembershipsDeleteRequest(
                name=self.membership)),
        response=response)

  def ExpectListMemberships(self, responses):
    self.mocked_client.projects_locations_memberships.List.Expect(
        (self.messages.GkehubProjectsLocationsMembershipsListRequest(
            parent=self.parent)),
        response=self.messages.ListMembershipsResponse(resources=responses))

  def ExpectUpdateMembership(self, membership, mask, response):
    self.mocked_client.projects_locations_memberships.Patch.Expect(
        self.messages.GkehubProjectsLocationsMembershipsPatchRequest(
            name=self.membership, membership=membership, updateMask=mask),
        response=response)

  def ExpectGetOperation(self, operation, exception=None):
    req = self.messages.GkehubProjectsLocationsOperationsGetRequest(
        name=self.wait_operation_relative_name)
    self.mocked_client.projects_locations_operations.Get.Expect(
        req, response=operation, exception=exception)