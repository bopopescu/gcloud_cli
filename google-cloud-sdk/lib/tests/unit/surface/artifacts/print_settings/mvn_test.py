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
"""Tests for artifacts print-settings maven."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from googlecloudsdk.api_lib.artifacts import exceptions as ar_exceptions
from googlecloudsdk.calliope import base as calliope_base
from tests.lib import test_case
from tests.lib.surface.artifacts import base


class MavenTestsBeta(base.ARTestBase):

  def PreSetUp(self):
    super(MavenTestsBeta, self).PreSetUp()
    self.track = calliope_base.ReleaseTrack.BETA

  def testMaven(self):
    cmd = ' '.join([
        'artifacts', 'print-settings', 'mvn', '--repository=my-repo',
        '--location=us'
    ])
    self.SetListLocationsExpect('us')
    self.SetGetRepositoryExpect(
        'us', 'my-repo', self.messages.Repository.FormatValueValuesEnum.MAVEN)
    self.Run(cmd)
    self.AssertOutputEquals(
        """\
Please insert following snippet into your pom.xml

======================================================
<project>
  <distributionManagement>
    <snapshotRepository>
      <id>artifact-registry</id>
      <url>artifactregistry://us-maven.pkg.dev/fake-project/my-repo</url>
    </snapshotRepository>
    <repository>
      <id>artifact-registry</id>
      <url>artifactregistry://us-maven.pkg.dev/fake-project/my-repo</url>
    </repository>
  </distributionManagement>

  <repositories>
    <repository>
      <id>artifact-registry</id>
      <url>artifactregistry://us-maven.pkg.dev/fake-project/my-repo</url>
      <releases>
        <enabled>true</enabled>
      </releases>
      <snapshots>
        <enabled>true</enabled>
      </snapshots>
    </repository>
  </repositories>

  <build>
    <extensions>
      <extension>
        <groupId>com.google.cloud.artifactregistry</groupId>
        <artifactId>artifactregistry-maven-wagon</artifactId>
        <version>2.0.1</version>
      </extension>
    </extensions>
  </build>
</project>
======================================================

""",
        normalize_space=True)

  def testMissingRepo(self):
    cmd = ' '.join(['artifacts', 'print-settings', 'mvn'])
    with self.assertRaises(ar_exceptions.InvalidInputValueError):
      self.Run(cmd)
    self.AssertErrContains('Failed to find attribute [repository]')

  def testInvalidLocation(self):
    cmd = ' '.join([
        'artifacts', 'print-settings', 'mvn', '--repository=my-repo',
        '--location=invalid'
    ])
    self.SetListLocationsExpect('us')
    with self.assertRaises(ar_exceptions.UnsupportedLocationError):
      self.Run(cmd)
    self.AssertErrContains(
        'invalid is not a valid location. Valid locations are')

  def testInvalidRepoType(self):
    cmd = ' '.join([
        'artifacts', 'print-settings', 'mvn', '--repository=my-repo',
        '--location=us'
    ])
    self.SetListLocationsExpect('us')
    self.SetGetRepositoryExpect(
        'us', 'my-repo', self.messages.Repository.FormatValueValuesEnum.NPM)
    with self.assertRaises(ar_exceptions.InvalidInputValueError):
      self.Run(cmd)
    self.AssertErrContains('Invalid repository type NPM. Valid type is MAVEN')


class MavenTestsAlpha(MavenTestsBeta):

  def PreSetUp(self):
    super(MavenTestsAlpha, self).PreSetUp()
    self.track = calliope_base.ReleaseTrack.ALPHA


if __name__ == '__main__':
  test_case.main()
