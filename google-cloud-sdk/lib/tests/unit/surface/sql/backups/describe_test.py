# -*- coding: utf-8 -*- #
# Copyright 2015 Google LLC. All Rights Reserved.
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
"""Tests that exercise operations listing and executing."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import datetime

from apitools.base.protorpclite import util as protorpc_util
from tests.lib import test_case
from tests.lib.surface.sql import base


class _BaseBackupsDescribeTest(object):
  # pylint:disable=g-tzinfo-datetime

  def testBackupsDescribe(self):
    self.mocked_client.backupRuns.Get.Expect(
        self.messages.SqlBackupRunsGetRequest(
            project=self.Project(), instance='clone-instance-7', id=42),
        self.messages.BackupRun(
            id=42,
            windowStartTime=datetime.datetime(
                2014,
                8,
                13,
                23,
                0,
                0,
                802000,
                tzinfo=protorpc_util.TimeZoneOffset(
                    datetime.timedelta(0))).isoformat(),
            endTime=datetime.datetime(
                2014,
                8,
                14,
                0,
                27,
                47,
                910000,
                tzinfo=protorpc_util.TimeZoneOffset(
                    datetime.timedelta(0))).isoformat(),
            enqueuedTime=datetime.datetime(
                2014,
                8,
                14,
                0,
                25,
                12,
                318000,
                tzinfo=protorpc_util.TimeZoneOffset(
                    datetime.timedelta(0))).isoformat(),
            error=None,
            instance='clone-instance-7',
            kind='sql#backupRun',
            startTime=datetime.datetime(
                2014,
                8,
                14,
                0,
                25,
                12,
                321000,
                tzinfo=protorpc_util.TimeZoneOffset(
                    datetime.timedelta(0))).isoformat(),
            status=self.messages.BackupRun.StatusValueValuesEnum.SUCCESSFUL,
        ))

    self.Run('sql backups describe --instance=clone-instance-7 42')
    self.AssertOutputContains(
        """\
endTime: '2014-08-14T00:27:47.910000+00:00'
enqueuedTime: '2014-08-14T00:25:12.318000+00:00'
id: '42'
instance: clone-instance-7
kind: sql#backupRun
startTime: '2014-08-14T00:25:12.321000+00:00'
status: SUCCESSFUL
windowStartTime: '2014-08-13T23:00:00.802000+00:00'
""",
        normalize_space=True)


class BackupsDescribeGATest(_BaseBackupsDescribeTest, base.SqlMockTestGA):
  pass


class BackupsDescribeBetaTest(_BaseBackupsDescribeTest, base.SqlMockTestBeta):
  pass


class BackupsDescribeAlphaTest(_BaseBackupsDescribeTest, base.SqlMockTestAlpha):
  pass


if __name__ == '__main__':
  test_case.main()
