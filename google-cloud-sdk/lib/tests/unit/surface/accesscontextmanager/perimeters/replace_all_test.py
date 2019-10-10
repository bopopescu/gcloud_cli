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
"""Tests for `gcloud access-context-manager perimeters replace-all`."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from apitools.base.py import encoding
from googlecloudsdk.calliope import base as calliope_base
from googlecloudsdk.calliope.concepts import handlers
from googlecloudsdk.core import properties
from googlecloudsdk.core import yaml
from tests.lib import cli_test_base
from tests.lib import test_case
from tests.lib.surface import accesscontextmanager


class PerimetersReplaceAllTestAlpha(accesscontextmanager.Base):

  def PreSetUp(self):
    self.track = calliope_base.ReleaseTrack.ALPHA

  def SetUp(self):
    properties.VALUES.core.user_output_enabled.Set(False)

  def _ExpectReplace(self, perimeters=None, policy=''):
    policy_name = 'accessPolicies/{}'.format(policy)
    m = self.messages
    req_type = m.AccesscontextmanagerAccessPoliciesServicePerimetersReplaceAllRequest
    replace_levels_req_type = m.ReplaceServicePerimetersRequest
    response_type = m.ReplaceServicePerimetersResponse(
        servicePerimeters=perimeters)
    response_value = encoding.DictToMessage(
        encoding.MessageToDict(response_type), m.Operation.ResponseValue)

    op = self.messages.Operation(
        name='operations/my-op', response=response_value, done=True)
    self.client.accessPolicies_servicePerimeters.ReplaceAll.Expect(
        req_type(
            parent=policy_name,
            replaceServicePerimetersRequest=replace_levels_req_type(
                servicePerimeters=perimeters)), op)

  def testReplace_InvalidSourceFileArg(self):
    self.SetUpForTrack(self.track)
    with self.AssertRaisesExceptionMatches(
        yaml.FileLoadError, 'Failed to load YAML from [not-found]'):
      self.Run('access-context-manager perimeters replace-all 123 '
               '--source-file not-found')

  def testReplace_MissingSourceFile(self):
    self.SetUpForTrack(self.track)
    with self.AssertRaisesExceptionMatches(cli_test_base.MockArgumentError,
                                           'Must be specified'):
      self.Run('access-context-manager perimeters replace-all 123')

  def testReplace_MissingPolicy(self):
    self.SetUpForTrack(self.track)
    perimeter_spec_path = self.Touch(
        self.temp_path, '', contents=self.SERVICE_PERIMETERS_SPECS)
    with self.AssertRaisesExceptionMatches(
        handlers.ParseError, 'resource is not properly specified.'):
      self.Run('access-context-manager perimeters replace-all --source-file {}'
               .format(perimeter_spec_path))

  def testReplace(self):
    self.SetUpForTrack(self.track)
    perimeter_name1 = 'myPerimeter1'
    perimeter_name2 = 'myPerimeter2'
    perimeters = [
        self._MakePerimeter(
            id_=perimeter_name1, title='replacement perimeter 1'),
        self._MakePerimeter(
            id_=perimeter_name2, title='replacement perimeter 2')
    ]

    self._ExpectReplace(perimeters, '123')
    perimeter_spec_path = self.Touch(
        self.temp_path, '', contents=self.SERVICE_PERIMETERS_SPECS)

    results = self.Run(
        'access-context-manager perimeters replace-all 123 --source-file {}'
        .format(perimeter_spec_path))
    self.assertEqual(results, perimeters)

  def testReplace_PolicyFromProperty(self):
    self.SetUpForTrack(self.track)
    policy = '123'
    properties.VALUES.access_context_manager.policy.Set(policy)

    perimeter_name1 = 'myPerimeter1'
    perimeter_name2 = 'myPerimeter2'
    perimeters = [
        self._MakePerimeter(
            id_=perimeter_name1, title='replacement perimeter 1'),
        self._MakePerimeter(
            id_=perimeter_name2, title='replacement perimeter 2')
    ]

    self._ExpectReplace(perimeters, '123')
    perimeter_spec_path = self.Touch(
        self.temp_path, '', contents=self.SERVICE_PERIMETERS_SPECS)

    results = self.Run(
        'access-context-manager perimeters replace-all --source-file {}'.format(
            perimeter_spec_path))
    self.assertEqual(results, perimeters)


if __name__ == '__main__':
  test_case.main()