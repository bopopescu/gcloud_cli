# -*- coding: utf-8 -*- #
# Copyright 2016 Google LLC. All Rights Reserved.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from googlecloudsdk.api_lib.auth import refresh_token
from googlecloudsdk.core import properties
from googlecloudsdk.core.credentials import store
from tests.lib import sdk_test_base
from tests.lib import test_case


class RefreshTokenTests(sdk_test_base.SdkBase):

  def testActivateAndRetrieve(self):
    self.StartObjectPatch(store, 'Refresh', autospec=True)

    refresh_token.ActivateCredentials('my-account', 'my-refresh-token')
    self.assertEqual('my-account', properties.VALUES.core.account.Get())

    self.assertEqual('my-refresh-token',
                     refresh_token.GetForAccount('my-account'))


if __name__ == '__main__':
  test_case.main()
