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
"""Test of the 'memberships update' command."""
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import copy

from googlecloudsdk.calliope import base as calliope_base
from tests.lib import test_case
from tests.lib.surface.container.memberships import base


class UpdateTestBeta(base.MembershipsTestBase):
  """gcloud Beta track using GKE Hub v1 API."""

  # TODO(b/116715821): add more negative tests.
  def PreSetUp(self):
    self.track = calliope_base.ReleaseTrack.BETA

  def _ExpectUpdateCalls(self, update, mask, asynchronous=False):
    operation = self._MakeOperation()
    self.ExpectUpdateMembership(update, mask, operation)
    if asynchronous:
      return
    self.ExpectGetOperation(operation)
    operation = self._MakeOperation(done=True)
    self.ExpectGetOperation(operation)
    result = copy.deepcopy(update)
    result.name = self.MEMBERSHIP_NAME
    self.ExpectGetMembership(result)

  def testUpdateDescription(self):
    new_description = 'my-updated-membership'
    membership = self._MakeMembership(description='my-membership')
    updated_membership = self._MakeMembership(description=new_description)

    self.ExpectGetMembership(membership)
    self._ExpectUpdateCalls(updated_membership, 'description')

    self.WriteInput('y')
    self._RunMembershipCommand(
        ['update', self.MEMBERSHIP_NAME, '--description', new_description])

  def testUpdateGkeClusterSelfLink(self):
    membership = self._MakeMembership()
    updated_membership = self._MakeMembership(
        gke_cluster_self_link=self.MEMBERSHIP_SELF_LINK)

    self.ExpectGetMembership(membership)
    self._ExpectUpdateCalls(updated_membership,
                            'endpoint.gkeCluster.resourceLink')

    self.WriteInput('y')
    self._RunMembershipCommand([
        'update', self.MEMBERSHIP_NAME, '--gke-cluster-self-link',
        self.MEMBERSHIP_SELF_LINK
    ])

  def testUpdateLabels(self):
    membership = self._MakeMembership(labels_dict={'foo': 'bar'})
    updated_membership = self._MakeMembership(labels_dict={
        'foo': 'baz',
        'new': 'bar',
    })
    self.ExpectGetMembership(membership)
    self._ExpectUpdateCalls(updated_membership, 'labels')

    self.WriteInput('y')
    self._RunMembershipCommand(
        ['update', self.MEMBERSHIP_NAME, '--update-labels', 'foo=baz,new=bar'])

  def testRemoveLabels(self):
    membership = self._MakeMembership(labels_dict={
        'foo': 'bar',
        'remove-me': 'baz',
    })
    updated_membership = self._MakeMembership(labels_dict={'foo': 'bar'})
    self.ExpectGetMembership(membership)
    self._ExpectUpdateCalls(updated_membership, 'labels')

    self.WriteInput('y')
    self._RunMembershipCommand(
        ['update', self.MEMBERSHIP_NAME, '--remove-labels', 'remove-me'])

  def testClearLabels(self):
    membership = self._MakeMembership(labels_dict={
        'foo': 'bar',
        'new': 'baz',
    })
    updated_membership = self._MakeMembership()
    updated_membership.labels = self._MakeLabelsProto({})
    self.ExpectGetMembership(membership)
    self._ExpectUpdateCalls(updated_membership, 'labels')

    self.WriteInput('y')
    self._RunMembershipCommand(
        ['update', self.MEMBERSHIP_NAME, '--clear-labels'])

  def testMultipleLabelsUpdates(self):
    membership = self._MakeMembership(labels_dict={
        'change-me': 'bar',
        'foo': 'bar',
        'remove-me': 'bar',
    })
    updated_membership = self._MakeMembership(labels_dict={
        'change-me': 'baz',
        'foo': 'bar',
    })
    self.ExpectGetMembership(membership)
    self._ExpectUpdateCalls(updated_membership, 'labels')

    self.WriteInput('y')
    self._RunMembershipCommand([
        'update', self.MEMBERSHIP_NAME, '--remove-labels', 'remove-me',
        '--update-labels', 'change-me=baz'
    ])

  def testUpdateMultipleFields(self):
    new_description = 'my-updated-membership'

    membership = self._MakeMembership(
        description='my-membership', labels_dict={'foo': 'bar'})
    updated_membership = self._MakeMembership(
        description=new_description,
        gke_cluster_self_link=self.MEMBERSHIP_SELF_LINK,
        labels_dict={
            'foo': 'baz',
            'new': 'bar',
        })
    self.ExpectGetMembership(membership)
    self._ExpectUpdateCalls(
        updated_membership,
        'description,endpoint.gkeCluster.resourceLink,labels')

    self.WriteInput('y')
    self._RunMembershipCommand([
        'update',
        self.MEMBERSHIP_NAME,
        '--description',
        new_description,
        '--gke-cluster-self-link',
        self.MEMBERSHIP_SELF_LINK,
        '--update-labels',
        'foo=baz,new=bar',
    ])


class UpdateTestAlpha(UpdateTestBeta):
  """gcloud Alpha track using GKE Hub v1 API."""

  def PreSetUp(self):
    self.track = calliope_base.ReleaseTrack.ALPHA


if __name__ == '__main__':
  test_case.main()