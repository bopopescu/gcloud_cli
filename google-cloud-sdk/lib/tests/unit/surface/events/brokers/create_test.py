# -*- coding: utf-8 -*- #
# Copyright 2020 Google LLC. All Rights Reserved.
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
"""Unit tests for the `events brokers create` command."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from googlecloudsdk.api_lib.events import iam_util
from googlecloudsdk.calliope import base as calliope_base
from googlecloudsdk.command_lib.events import exceptions
from googlecloudsdk.command_lib.iam import iam_util as core_iam_util
from googlecloudsdk.core.console import console_io
from tests.lib.surface.events import base


class CreateTestAlpha(base.EventsBase):

  def PreSetUp(self):
    self.track = calliope_base.ReleaseTrack.ALPHA

  def SetUp(self):
    self.service_account = 'svcacc@gserviceaccount.com'
    self.service_account_ref = self._registry.Parse(
        self.service_account,
        params={'projectsId': '-'},
        collection=core_iam_util.SERVICE_ACCOUNTS_COLLECTION)
    self.service_account_key_ref = self._registry.Parse(
        'somehexvalue',
        params={
            'projectsId': 'fake-project',
            'serviceAccountsId': self.service_account
        },
        collection='iam.projects.serviceAccounts.keys')
    self.operations.CreateOrReplaceServiceAccountSecret.return_value = (
        None, self.service_account_key_ref)
    self.bind_missing_roles = self.StartObjectPatch(
        iam_util,
        'BindMissingRolesWithPrompt',
    )

  def testEventTypesFailFailNonGKE(self):
    """This command is only for initializing a cluster."""
    with self.assertRaises(exceptions.UnsupportedArgumentError):
      self.Run('events brokers create default '
               '--service-account=svcacc@gserviceaccount.com '
               '--platform=managed --region=us-central1')
    self.AssertErrContains(
        'This command is only available with Cloud Run for Anthos.')

  def testCreateWithPromptYes(self):
    """Tests successful init with success message on prompt confirmation."""
    self.WriteInput('y\n')
    self.Run('events brokers create default '
             '--service-account=svcacc@gserviceaccount.com '
             '--platform=gke --cluster=cluster-1 '
             '--cluster-location=us-central1-a')
    self.operations.UpdateNamespaceWithLabels.assert_called_once_with(
        self._CoreNamespaceRef('default'),
        {'knative-eventing-injection': 'enabled'})
    self.AssertErrContains('Created broker [default]')
    self.AssertErrContains(self.service_account)
    self.AssertErrContains(self.service_account_key_ref.Name())
    self.bind_missing_roles.assert_called_once_with(
        self.service_account_ref, frozenset(['roles/pubsub.editor']))

  def testCreateWithPromptNoFails(self):
    """Tests failed init without prompt confirmation."""
    self.WriteInput('n\n')
    with self.assertRaises(console_io.OperationCancelledError):
      self.Run('events brokers create default '
               '--service-account=svcacc@gserviceaccount.com '
               '--platform=gke --cluster=cluster-1 '
               '--cluster-location=us-central1-a')

  def testCreateNoPrompt(self):
    """Tests successful init with success message on no prompting allowed."""
    self.is_interactive.return_value = False
    self.Run('events brokers create default '
             '--service-account=svcacc@gserviceaccount.com '
             '--platform=gke --cluster=cluster-1 '
             '--cluster-location=us-central1-a')
    self.AssertErrContains('Created broker [default]')
    self.AssertErrContains(self.service_account)
    self.AssertErrContains(self.service_account_key_ref.Name())
    self.bind_missing_roles.assert_called_once_with(
        self.service_account_ref, frozenset(['roles/pubsub.editor']))

  def testUsesCustomNamespace(self):
    self.WriteInput('y\n')
    self.Run('events brokers create default --namespace=roberto '
             '--service-account=svcacc@gserviceaccount.com '
             '--platform=gke --cluster=cluster-1 '
             '--cluster-location=us-central1-a')
    self.operations.UpdateNamespaceWithLabels.assert_called_once_with(
        self._CoreNamespaceRef('roberto'),
        {'knative-eventing-injection': 'enabled'})

  def testNonDefaultBrokerNameFails(self):
    with self.assertRaises(exceptions.UnsupportedArgumentError):
      self.Run('events brokers create not-default '
               '--service-account=svcacc@gserviceaccount.com '
               '--platform=gke --cluster=cluster-1 '
               '--cluster-location=us-central1-a')
    self.AssertErrContains('Only brokers named "default" may be created.')

  def testServiceAccountNotProvidedUsesDefault(self):
    service_account = 'existing-account@gserviceaccount.com'
    self.StartObjectPatch(
        iam_util,
        'GetOrCreateEventingServiceAccountWithPrompt',
        return_value=service_account,
    )
    self.WriteInput('y\n')
    self.Run('events brokers create default '
             '--platform=gke --cluster=cluster-1 '
             '--cluster-location=us-central1-a')
    self.AssertErrContains('Created broker [default]')
    self.AssertErrContains(service_account)
