# -*- coding: utf-8 -*- #
# Copyright 2013 Google LLC. All Rights Reserved.
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

"""Tests for the http module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import uuid

from apitools.base.py import batch

import google_auth_httplib2

from googlecloudsdk.core import config
from googlecloudsdk.core import properties
from googlecloudsdk.core.console import console_attr
from googlecloudsdk.core.console import console_io
from googlecloudsdk.core.credentials import http
from googlecloudsdk.core.credentials import store
from googlecloudsdk.core.util import platforms
from tests.lib import sdk_test_base
from tests.lib import test_case

import httplib2
from oauth2client import client
import six
from google.auth import credentials


class CredentialsTest(sdk_test_base.WithFakeAuth):

  def FakeAuthAccessToken(self):
    return None

  def testTokenRefreshError(self):
    refresh_mock = self.StartObjectPatch(client.OAuth2Credentials,
                                         '_do_refresh_request')
    refresh_mock.side_effect = client.AccessTokenRefreshError
    http_client = http.Http()
    with self.assertRaisesRegex(
        store.TokenRefreshError,
        'There was a problem refreshing your current auth tokens'):
      http_client.request('http://foo.com')
    # Make sure it also extends the original exception.
    with self.assertRaisesRegex(
        client.AccessTokenRefreshError,
        'There was a problem refreshing your current auth tokens'):
      http_client.request('http://foo.com')

  def testTokenRefreshErrorGoogleAuth(self):
    refresh_mock = self.StartObjectPatch(credentials.Credentials,
                                         'before_request')
    refresh_mock.side_effect = client.AccessTokenRefreshError
    http_client = http.Http(use_google_auth=True)
    with self.assertRaisesRegex(
        store.TokenRefreshError,
        'There was a problem refreshing your current auth tokens'):
      http_client.request('http://foo.com')
    # Make sure it also extends the original exception.
    with self.assertRaisesRegex(
        client.AccessTokenRefreshError,
        'There was a problem refreshing your current auth tokens'):
      http_client.request('http://foo.com')

  def testBatchTokenRefreshError(self):
    refresh_mock = self.StartObjectPatch(client.OAuth2Credentials,
                                         '_do_refresh_request')
    refresh_mock.side_effect = client.AccessTokenRefreshError
    http_client = http.Http()
    batch_http_request = batch.BatchHttpRequest(
        batch_url='https://www.googleapis.com/batch/compute')
    with self.assertRaisesRegex(
        store.TokenRefreshError,
        'There was a problem refreshing your current auth tokens'):
      batch_http_request.Execute(http_client)

  def testBatchTokenRefreshErrorGoogleAuth(self):
    refresh_mock = self.StartObjectPatch(credentials.Credentials,
                                         'before_request')
    refresh_mock.side_effect = client.AccessTokenRefreshError
    http_client = http.Http(use_google_auth=True)
    batch_http_request = batch.BatchHttpRequest(
        batch_url='https://www.googleapis.com/batch/compute')
    with self.assertRaisesRegex(
        store.TokenRefreshError,
        'There was a problem refreshing your current auth tokens'):
      batch_http_request.Execute(http_client)


class HttpTestBase(sdk_test_base.SdkBase):

  def FakeAuthUserAgent(self):
    return ''

  def UserAgent(self, cmd_path, invocation_id, python_version, interactive,
                fromscript=False):
    template = ('gcloud/{0} command/{1} invocation-id/{2} environment/{3} '
                'environment-version/{4} interactive/{5} from-script/{8} '
                'python/{6} term/xterm {7}')
    # Mocking the platform fragment doesn't seem to work all the time.
    # Use the real platform we are on.
    platform = platforms.Platform.Current().UserAgentFragment()
    environment = properties.GetMetricsEnvironment()
    environment_version = properties.VALUES.metrics.environment_version.Get()
    user_agent = template.format(config.CLOUD_SDK_VERSION,
                                 cmd_path,
                                 invocation_id,
                                 environment,
                                 environment_version,
                                 interactive,
                                 python_version,
                                 platform,
                                 fromscript)
    return user_agent

  def SetUp(self):
    self.request_mock = self.StartObjectPatch(
        httplib2.Http,
        'request',
        return_value=(httplib2.Response({'status': 200}), b''))
    self.google_auth_request_mock = self.StartObjectPatch(
        google_auth_httplib2.AuthorizedHttp,
        'request',
        return_value=(httplib2.Response({'status': 200}), b''))
    uuid_mock = self.StartObjectPatch(uuid, 'uuid4')
    uuid_mock.return_value = uuid.UUID('12345678123456781234567812345678')
    is_interactive_mock = self.StartObjectPatch(console_io, 'IsInteractive')
    is_interactive_mock.return_value = False
    python_version = '2.7.6'
    self.StartPatch('platform.python_version').return_value = python_version
    self.StartObjectPatch(console_io, 'IsRunFromShellScript',
                          return_value=False)
    self.StartObjectPatch(console_attr.ConsoleAttr, 'GetTermIdentifier',
                          return_value='xterm')
    self.expected_user_agent = self.UserAgent(
        'None', uuid_mock.return_value.hex, python_version, False)


class HttpTestUserCreds(HttpTestBase, sdk_test_base.WithFakeAuth):

  def _EncodeHeaders(self, headers):
    return {
        k.encode('ascii'): v.encode('ascii')
        for k, v in six.iteritems(headers)}

  def testIAMAuthoritySelectorHeader(self):
    url = 'http://foo.com'
    authority_selector = 'superuser@google.com'
    properties.VALUES.auth.authority_selector.Set(authority_selector)

    expect_headers = {
        'user-agent': self.expected_user_agent,
        'x-goog-iam-authority-selector': authority_selector,
        'Authorization': 'Bearer ' + self.FakeAuthAccessToken()}
    expect_headers = self._EncodeHeaders(expect_headers)
    http.Http().request(url, 'GET', None, {}, 0, None)
    self.request_mock.assert_called_once_with(
        url, 'GET', None, expect_headers, 0, None)

  def testIAMAuthoritySelectorHeaderGoogleAuth(self):
    url = 'http://foo.com'
    authority_selector = 'superuser@google.com'
    properties.VALUES.auth.authority_selector.Set(authority_selector)

    expect_headers = {'x-goog-iam-authority-selector': authority_selector}
    expect_headers = self._EncodeHeaders(expect_headers)

    # google-auth is invoked by default if use_google_auth is set to True.
    http.Http(use_google_auth=True).request(url, 'GET', None, {}, 0, None)
    self.google_auth_request_mock.assert_called_once_with(
        url, 'GET', None, expect_headers, 0, None)

  def testIAMAuthorizationTokenHeader(self):
    url = 'http://foo.com'
    authorization_token = 'A very interesting authorization token'
    authorization_token_file = self.Touch(
        self.temp_path, 'auth_token_file', contents=authorization_token)
    properties.VALUES.auth.authorization_token_file.Set(
        authorization_token_file)

    expect_headers = {
        'user-agent': self.expected_user_agent,
        'x-goog-iam-authorization-token': authorization_token,
        'Authorization': 'Bearer ' + self.FakeAuthAccessToken()}
    expect_headers = self._EncodeHeaders(expect_headers)
    http.Http().request(url, 'GET', None, {}, 0, None)
    self.request_mock.assert_called_once_with(
        url, 'GET', None, expect_headers, 0, None)

  def testIAMAuthorizationTokenHeaderGoogleAuth(self):
    url = 'http://foo.com'
    authorization_token = 'A very interesting authorization token'
    authorization_token_file = self.Touch(
        self.temp_path, 'auth_token_file', contents=authorization_token)
    properties.VALUES.auth.authorization_token_file.Set(
        authorization_token_file)

    expect_headers = {'x-goog-iam-authorization-token': authorization_token}
    expect_headers = self._EncodeHeaders(expect_headers)
    http.Http(use_google_auth=True).request(url, 'GET', None, {}, 0, None)
    self.google_auth_request_mock.assert_called_once_with(
        url, 'GET', None, expect_headers, 0, None)

  def testDisabledAuth(self):
    properties.VALUES.auth.disable_credentials.Set(True)
    url = 'http://foo.com'
    expect_headers = {'user-agent': self.expected_user_agent}
    expect_headers = self._EncodeHeaders(expect_headers)
    http_client = http.Http()
    http_client.request(url, 'GET', None, None, 0, None)
    self.request_mock.assert_called_once_with(
        url, 'GET', None, expect_headers, 0, None)

  def testDisabledAuthGoogleAuth(self):
    properties.VALUES.auth.disable_credentials.Set(True)
    url = 'http://foo.com'
    expect_headers = {'user-agent': self.expected_user_agent}
    expect_headers = self._EncodeHeaders(expect_headers)
    http_client = http.Http(use_google_auth=True)
    http_client.request(url, 'GET', None, None, 0, None)
    self.request_mock.assert_called_once_with(url, 'GET', None, expect_headers,
                                              0, None)

  def testResourceProjectOverride(self):
    properties.VALUES.billing.quota_project.Set(
        properties.VALUES.billing.CURRENT_PROJECT)
    properties.VALUES.core.project.Set('foo')
    http.Http(enable_resource_quota=True).request('http://foo.com', 'GET', None,
                                                  {})
    expect_headers = self._EncodeHeaders({'X-Goog-User-Project': 'foo'})
    self.assertDictContainsSubset(expect_headers,
                                  self.request_mock.call_args[0][3])

  def testResourceProjectOverrideLegacyProject(self):
    properties.VALUES.billing.quota_project.Set(
        properties.VALUES.billing.LEGACY)
    for x in [False, True]:
      http.Http(enable_resource_quota=x).request(
          'http://foo.com', 'GET', None, {})
      self.assertNotIn('X-Goog-User-Project',
                       self.request_mock.call_args[0][3])
      self.assertNotIn(b'X-Goog-User-Project',
                       self.request_mock.call_args[0][3])

  def testResourceProjectOverrideUnsetDefault(self):
    properties.VALUES.billing.quota_project.Set(None)
    http.Http(enable_resource_quota=False).request(
        'http://foo.com', 'GET', None, {})
    self.assertNotIn('X-Goog-User-Project', self.request_mock.call_args[0][3])
    self.assertNotIn(b'X-Goog-User-Project', self.request_mock.call_args[0][3])

  def testResourceProjectOverrideCustomProject(self):
    properties.VALUES.billing.quota_project.Set('bar')
    http.Http(enable_resource_quota=True).request('http://foo.com', 'GET', None,
                                                  {})
    expect_headers = self._EncodeHeaders({'X-Goog-User-Project': 'bar'})
    self.assertDictContainsSubset(expect_headers,
                                  self.request_mock.call_args[0][3])

  def testResourceProjectOverrideForceResourceQuota(self):
    properties.VALUES.billing.quota_project.Set(
        properties.VALUES.billing.LEGACY)
    properties.VALUES.core.project.Set('foo')
    http.Http(
        enable_resource_quota=True,
        force_resource_quota=True).request('http://foo.com', 'GET', None, {})
    expect_headers = self._EncodeHeaders({'X-Goog-User-Project': 'foo'})
    self.assertDictContainsSubset(expect_headers,
                                  self.request_mock.call_args[0][3])

  def testResourceProjectOverrideGoogleAuth(self):
    properties.VALUES.billing.quota_project.Set(
        properties.VALUES.billing.CURRENT_PROJECT)
    properties.VALUES.core.project.Set('foo')
    http.Http(
        enable_resource_quota=True,
        use_google_auth=True).request('http://foo.com', 'GET', None, {})
    expect_headers = self._EncodeHeaders({'X-Goog-User-Project': 'foo'})
    self.assertDictContainsSubset(expect_headers,
                                  self.google_auth_request_mock.call_args[0][3])

  def testResourceProjectOverrideLegacyProjectGoogleAuth(self):
    properties.VALUES.billing.quota_project.Set(
        properties.VALUES.billing.LEGACY)
    for x in [False, True]:
      http.Http(
          enable_resource_quota=x,
          use_google_auth=True).request('http://foo.com', 'GET', None, {})
      self.assertNotIn('X-Goog-User-Project',
                       self.google_auth_request_mock.call_args[0][3])
      self.assertNotIn(b'X-Goog-User-Project',
                       self.google_auth_request_mock.call_args[0][3])

  def testResourceProjectOverrideUnsetDefaultGoogleAuth(self):
    properties.VALUES.billing.quota_project.Set(None)
    http.Http(
        enable_resource_quota=False,
        use_google_auth=True).request('http://foo.com', 'GET', None, {})
    self.assertNotIn('X-Goog-User-Project',
                     self.google_auth_request_mock.call_args[0][3])
    self.assertNotIn(b'X-Goog-User-Project',
                     self.google_auth_request_mock.call_args[0][3])

  def testResourceProjectOverrideCustomProjectGoogleAuth(self):
    properties.VALUES.billing.quota_project.Set('bar')
    http.Http(
        enable_resource_quota=True,
        use_google_auth=True).request('http://foo.com', 'GET', None, {})
    expect_headers = self._EncodeHeaders({'X-Goog-User-Project': 'bar'})
    self.assertDictContainsSubset(expect_headers,
                                  self.google_auth_request_mock.call_args[0][3])

  def testResourceProjectOverrideForceResourceQuotGoogleAuth(self):
    properties.VALUES.billing.quota_project.Set(
        properties.VALUES.billing.LEGACY)
    properties.VALUES.core.project.Set('foo')
    http.Http(
        enable_resource_quota=True,
        force_resource_quota=True,
        use_google_auth=True).request('http://foo.com', 'GET', None, {})
    expect_headers = self._EncodeHeaders({'X-Goog-User-Project': 'foo'})
    self.assertDictContainsSubset(expect_headers,
                                  self.google_auth_request_mock.call_args[0][3])


class HttpTestGCECreds(HttpTestBase, sdk_test_base.WithFakeComputeAuth):

  def testComputeServiceAccount(self):
    # Don't do it for service accounts.
    properties.VALUES.billing.quota_project.Set('bar')
    http.Http(enable_resource_quota=True).request(
        'http://foo.com', 'GET', None, {})
    self.assertNotIn('X-Goog-User-Project', self.request_mock.call_args[0][3])
    self.assertNotIn(b'X-Goog-User-Project', self.request_mock.call_args[0][3])

  def testComputeServiceAccountGoogleAuth(self):
    # Don't do it for service accounts.
    properties.VALUES.billing.quota_project.Set('bar')
    http.Http(
        enable_resource_quota=True,
        use_google_auth=True).request('http://foo.com', 'GET', None, {})
    self.assertNotIn('X-Goog-User-Project',
                     self.google_auth_request_mock.call_args[0][3])
    self.assertNotIn(b'X-Goog-User-Project',
                     self.google_auth_request_mock.call_args[0][3])


if __name__ == '__main__':
  test_case.main()
