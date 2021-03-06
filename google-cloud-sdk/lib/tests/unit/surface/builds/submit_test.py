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
"""Tests that exercise build creation."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import os.path
import uuid

from apitools.base.py import encoding
from apitools.base.py.testing import mock

from googlecloudsdk.api_lib.cloudbuild import cloudbuild_util
from googlecloudsdk.api_lib.util import apis as core_apis
from googlecloudsdk.calliope import base as calliope_base
from googlecloudsdk.calliope import exceptions as c_exceptions
from googlecloudsdk.core import exceptions as core_exceptions
from googlecloudsdk.core import properties
from googlecloudsdk.core.util import times
from tests.lib import e2e_base
from tests.lib import sdk_test_base
from tests.lib import test_case
from tests.lib.apitools import http_error
from tests.lib.cli_test_base import MockArgumentError
from six.moves import range  # pylint: disable=redefined-builtin

_CONFIG_STEPS = """\
steps:
 - name: gcr.io/cloud-builders/docker
   args:
   - build
   - --network
   - cloudbuild
   - --no-cache
   - -t
   - gcr.io/my-project/image
   - .
"""

_DOCKER_BUILD_STEPS = [
    core_apis.GetMessagesModule('cloudbuild', 'v1').BuildStep(
        name='gcr.io/cloud-builders/docker',
        args=[
            'build', '--network', 'cloudbuild', '--no-cache', '-t',
            'gcr.io/my-project/image', '.'
        ])
]

_DEFAULT_BUILDPACK_BUILDER = 'gcr.io/buildpacks/builder'

_DOCKER_BUILD_STEPS_WITH_AR = [
    core_apis.GetMessagesModule('cloudbuild', 'v1').BuildStep(
        name='gcr.io/cloud-builders/docker',
        args=[
            'build', '--network', 'cloudbuild', '--no-cache', '-t',
            'us-east1-docker.pkg.dev/my-project/image', '.'
        ])
]


def _MakeConfig(images=None, timeout=None):
  config_contents = _CONFIG_STEPS
  if images:
    config_contents += 'images:\n{}\n'.format('\n'.join(
        ['- {}'.format(i) for i in images]))
  if timeout:
    config_contents += 'timeout: {}s\n'.format(timeout)
  return config_contents


# TODO(b/29358031): Move WithMockHttp somewhere more appropriate for unit tests.
class SubmitTest(e2e_base.WithMockHttp, sdk_test_base.WithFakeAuth,
                 sdk_test_base.WithTempCWD):

  def PreSetUp(self):
    self.track = calliope_base.ReleaseTrack.GA

  def SetUp(self):
    self.StartPatch('time.sleep')  # To speed up tests with polling

    self.mocked_cloudbuild_v1 = mock.Client(
        core_apis.GetClientClass('cloudbuild', 'v1'))
    self.mocked_cloudbuild_v1.Mock()
    self.addCleanup(self.mocked_cloudbuild_v1.Unmock)
    self.cloudbuild_v1_messages = core_apis.GetMessagesModule(
        'cloudbuild', 'v1')

    self.mocked_storage_v1 = mock.Client(
        core_apis.GetClientClass('storage', 'v1'))
    self.mocked_storage_v1.Mock()
    self.addCleanup(self.mocked_storage_v1.Unmock)
    self.storage_v1_messages = core_apis.GetMessagesModule('storage', 'v1')

    properties.VALUES.core.project.Set('my-project')

    messages = self.cloudbuild_v1_messages
    self._statuses = messages.Build.StatusValueValuesEnum
    self._vmtypes = messages.BuildOptions.MachineTypeValueValuesEnum

    frozen_time = times.ParseDateTime('2016-05-26T00:05:00.000000Z')
    frozen_uuid = uuid.uuid4()
    self.frozen_zip_filename = 'source/{frozen_time}-{frozen_uuid}.zip'.format(
        frozen_time=times.GetTimeStampFromDateTime(frozen_time),
        frozen_uuid=frozen_uuid.hex)
    self.frozen_tgz_filename = 'source/{frozen_time}-{frozen_uuid}.tgz'.format(
        frozen_time=times.GetTimeStampFromDateTime(frozen_time),
        frozen_uuid=frozen_uuid.hex)
    self.StartObjectPatch(times, 'Now', return_value=frozen_time)
    self.StartObjectPatch(uuid, 'uuid4', return_value=frozen_uuid)
    self.StartObjectPatch(os.path, 'getsize', return_value=100)

  def _Run(self, args):
    self.Run(args)

  def ExpectMessagesForSimpleBuild(self,
                                   b_in,
                                   b_out,
                                   build_project='my-project',
                                   gcs=True):
    storage_project = build_project.replace('google', 'elgoog')
    storage_project = storage_project.replace(':', '_')
    storage_project = storage_project.replace('.', '_')
    if gcs:
      b = self.storage_v1_messages.Bucket(id=storage_project + '_cloudbuild')
      self.mocked_storage_v1.buckets.Get.Expect(
          self.storage_v1_messages.StorageBucketsGetRequest(bucket=b.id),
          response=b)
      self.mocked_storage_v1.buckets.List.Expect(
          self.storage_v1_messages.StorageBucketsListRequest(
              project=build_project,
              prefix=b.id,
          ),
          response=self.storage_v1_messages.Buckets(items=[b]))
      self.mocked_storage_v1.objects.Rewrite.Expect(
          self.storage_v1_messages.StorageObjectsRewriteRequest(
              destinationBucket=storage_project + '_cloudbuild',
              destinationObject=self.frozen_zip_filename,
              sourceBucket='bucket',
              sourceObject='object.zip',
          ),
          response=self.storage_v1_messages.RewriteResponse(
              resource=self.storage_v1_messages.Object(
                  bucket=storage_project + '_cloudbuild',
                  name=self.frozen_zip_filename,
                  generation=123,
              ),
              done=True,
          ),
      )

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=b_out)

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=b_in,
            projectId=build_project,
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

  def testSubmitUseKaniko(self):
    properties.VALUES.builds.use_kaniko.Set(True)

    b_in = self.cloudbuild_v1_messages.Build(
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/kaniko-project/executor:latest',
                args=[
                    '--destination',
                    'gcr.io/my-project/image',
                    '--cache',
                    '--cache-ttl',
                    '6h',
                    '--cache-dir',
                    '',
                ],
            ),
        ])
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        logUrl='mockLogURL',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/kaniko-project/executor:latest',
                args=[
                    '--destination',
                    'gcr.io/my-project/image',
                    '--cache',
                    '--cache-ttl',
                    '6h',
                    '--cache-dir',
                    '',
                ],
            ),
        ])
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testSubmitUseKanikoCacheTTL(self):
    properties.VALUES.builds.use_kaniko.Set(True)
    properties.VALUES.builds.kaniko_cache_ttl.Set(1)

    b_in = self.cloudbuild_v1_messages.Build(
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/kaniko-project/executor:latest',
                args=[
                    '--destination',
                    'gcr.io/my-project/image',
                    '--cache',
                    '--cache-ttl',
                    '1h',
                    '--cache-dir',
                    '',
                ],
            ),
        ])
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        logUrl='mockLogURL',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/kaniko-project/executor:latest',
                args=[
                    '--destination',
                    'gcr.io/my-project/image',
                    '--cache',
                    '--cache-ttl',
                    '1h',
                    '--cache-dir',
                    '',
                ],
            ),
        ])
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testSubmitNoCacheWithConfig(self):
    properties.VALUES.builds.use_kaniko.Set(True)
    config_path = self.Touch('.', 'config.yaml')
    with self.assertRaises(c_exceptions.ConflictingArgumentsException):
      self._Run([
          'builds', 'submit', 'gs://bucket/object.zip', '--config', config_path,
          '--no-cache'
      ])

  def testSubmitNoCacheWithoutKaniko(self):
    properties.VALUES.builds.use_kaniko.Set(False)
    with self.assertRaises(c_exceptions.InvalidArgumentException):
      self._Run([
          'builds', 'submit', 'gs://bucket/object.zip',
          '--tag=gcr.io/my-project/image', '--no-cache'
      ])

  def testSubmitNoCache(self):
    properties.VALUES.builds.use_kaniko.Set(True)

    b_in = self.cloudbuild_v1_messages.Build(
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/kaniko-project/executor:latest',
                args=[
                    '--destination',
                    'gcr.io/my-project/image',
                    '--cache',
                    '--cache-ttl',
                    '0h',
                    '--cache-dir',
                    '',
                ],
            ),
        ])
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        logUrl='mockLogURL',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/kaniko-project/executor:latest',
                args=[
                    '--destination',
                    'gcr.io/my-project/image',
                    '--cache',
                    '--cache-ttl',
                    '0h',
                    '--cache-dir',
                    '',
                ],
            ),
        ])
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip', '--async',
        '--tag=gcr.io/my-project/image', '--no-cache'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testSubmitUseKanikoOverrideImage(self):
    properties.VALUES.builds.use_kaniko.Set(True)
    properties.VALUES.builds.kaniko_image.Set('gcr.io/some-other/kaniko-image')

    b_in = self.cloudbuild_v1_messages.Build(
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/some-other/kaniko-image',
                args=[
                    '--destination',
                    'gcr.io/my-project/image',
                    '--cache',
                    '--cache-ttl',
                    '6h',
                    '--cache-dir',
                    '',
                ],
            ),
        ])
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        logUrl='mockLogURL',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/some-other/kaniko-image',
                args=[
                    '--destination',
                    'gcr.io/my-project/image',
                    '--cache',
                    '--cache-ttl',
                    '6h',
                    '--cache-dir',
                    '',
                ],
            ),
        ])
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testCreateSuccess(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[
            'gcr.io/my-project/image',
        ],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        logUrl='mockLogURL',
        timeout='600.000s',
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=[
            'gcr.io/my-project/image',
        ],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
    )
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testCreateSuccessWithArtifactRegistry(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[
            'us-east1-docker.pkg.dev/my-project/image',
        ],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS_WITH_AR,
        logUrl='mockLogURL',
        timeout='600.000s',
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=[
            'us-east1-docker.pkg.dev/my-project/image',
        ],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS_WITH_AR,
    )
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=us-east1-docker.pkg.dev/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testCreateSuccessSubstitutions(self):
    substitutions_type = self.cloudbuild_v1_messages.Build.SubstitutionsValue
    substitutions = self.cloudbuild_v1_messages.Build.SubstitutionsValue(
        additionalProperties=[
            substitutions_type.AdditionalProperty(
                key='_DAY_OF_WEEK', value='tuesday'),
            substitutions_type.AdditionalProperty(
                key='_FAVORITE_COLOR', value='blue')
        ])
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[
            'gcr.io/my-project/image',
        ],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        substitutions=substitutions,
        logUrl='mockLogURL',
        timeout='600.000s',
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=[
            'gcr.io/my-project/image',
        ],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        substitutions=substitutions)
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async', '--substitutions',
        '_DAY_OF_WEEK=tuesday,_FAVORITE_COLOR=blue'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testCreateSuccessNoLogUrl(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ),
    )

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=_DOCKER_BUILD_STEPS,
            timeout='600.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async'
    ])

    self.AssertErrNotContains('To see logs in the Cloud Console')
    self.AssertErrContains('Logs are available in the Cloud Console')

  def testCreateWithTimeout(self):
    properties.VALUES.builds.timeout.Set('200')

    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=_DOCKER_BUILD_STEPS,
            timeout='200s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
                timeout='200s',
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateLocalDirectory(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Insert.Expect(
        self.storage_v1_messages.StorageObjectsInsertRequest(
            bucket='my-project_cloudbuild',
            name=self.frozen_tgz_filename,
            object=self.storage_v1_messages.Object(size=100),
        ),
        response=self.storage_v1_messages.Object(
            bucket='my-project_cloudbuild',
            name=self.frozen_tgz_filename,
            generation=123,
            size=100,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_tgz_filename,
                    generation=123,
                )),
            steps=_DOCKER_BUILD_STEPS,
            timeout='600.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_tgz_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self.Touch('.', 'Dockerfile', contents='FROM busybox\n')
    self._Run(
        ['builds', 'submit', '.', '--tag=gcr.io/my-project/image', '--async'])
    self.AssertErrContains('Uploading tarball of ')
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_tgz_filename} - QUEUED
""".format(frozen_tgz_filename=self.frozen_tgz_filename),
        normalize_space=True)

  def testCreateLocalTarball(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Insert.Expect(
        self.storage_v1_messages.StorageObjectsInsertRequest(
            bucket='my-project_cloudbuild',
            name=self.frozen_tgz_filename,
            object=self.storage_v1_messages.Object(size=100),
        ),
        response=self.storage_v1_messages.Object(
            bucket='my-project_cloudbuild',
            name=self.frozen_tgz_filename,
            generation=123,
            size=100))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_tgz_filename,
                    generation=123,
                )),
            steps=_DOCKER_BUILD_STEPS,
            timeout='600.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_tgz_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    tarball_path = self.Touch(
        '.', 'source.tgz', contents='pretend this is a valid tarball')
    self._Run([
        'builds', 'submit', tarball_path, '--tag=gcr.io/my-project/image',
        '--async'
    ])
    self.AssertErrContains('Uploading local file')
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_tgz_filename} - QUEUED
""".format(frozen_tgz_filename=self.frozen_tgz_filename),
        normalize_space=True)

  def testCreateLocalZip(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Insert.Expect(
        self.storage_v1_messages.StorageObjectsInsertRequest(
            bucket='my-project_cloudbuild',
            name=self.frozen_zip_filename,
            object=self.storage_v1_messages.Object(size=100),
        ),
        response=self.storage_v1_messages.Object(
            bucket='my-project_cloudbuild',
            name=self.frozen_zip_filename,
            generation=123,
            size=100))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=_DOCKER_BUILD_STEPS,
            timeout='600.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    zipfile_path = self.Touch(
        '.', 'source.zip', contents='pretend this is a valid zipfile')
    self._Run([
        'builds', 'submit', zipfile_path, '--tag=gcr.io/my-project/image',
        '--async'
    ])
    self.AssertErrContains('Uploading local file')
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateLocalFileOtherDirectory(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Insert.Expect(
        self.storage_v1_messages.StorageObjectsInsertRequest(
            bucket='my-project_cloudbuild',
            name=self.frozen_tgz_filename,
            object=self.storage_v1_messages.Object(size=100),
        ),
        response=self.storage_v1_messages.Object(
            bucket='my-project_cloudbuild',
            name=self.frozen_tgz_filename,
            generation=123,
            size=100,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_tgz_filename,
                    generation=123,
                )),
            steps=_DOCKER_BUILD_STEPS,
            timeout='600.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_tgz_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self.Touch(self.temp_path, 'Dockerfile', contents='FROM busybox\n')
    self._Run([
        'builds', 'submit', self.temp_path, '--tag=gcr.io/my-project/image',
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_tgz_filename} - QUEUED
""".format(frozen_tgz_filename=self.frozen_tgz_filename),
        normalize_space=True)

  def testCreateExistingOwnedBucket(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=_DOCKER_BUILD_STEPS,
            timeout='600.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testGetExistingBucketNotOwned(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(items=[]))

    with self.assertRaisesRegex(
        c_exceptions.RequiredArgumentException,
        'Specify a bucket using --gcs-source-staging-dir'):
      self._Run([
          'builds', 'submit', 'gs://bucket/object.zip',
          '--tag=gcr.io/my-project/image', '--async'
      ])

  def testGetExistingBucketSpecifiedBucketAndLog(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=_DOCKER_BUILD_STEPS,
            timeout='600.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                logsBucket='gs://my-project_cloudbuild/logs',
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--gcs-source-staging-dir=gs://my-project_cloudbuild/source',
        '--gcs-log-dir=gs://my-project_cloudbuild/logs',
        '--tag=gcr.io/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateDeniedBucket(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        exception=http_error.MakeHttpError(
            409,
            url=('https://www.googleapis.com/storage/v1/buckets/'
                 'my-project_cloudbuild?alt=json')))

    with self.AssertRaisesHttpExceptionMatches(
        'Bucket [my-project_cloudbuild] is the subject of a conflict: '
        'Resource already exists.'):
      self._Run([
          'builds', 'submit', '/bucket/object.zip',
          '--tag=gcr.io/my-project/image', '--async'
      ])

  def testCreateAndStream(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    def _MakeBuild(status):
      return self.cloudbuild_v1_messages.Build(
          createTime='2016-03-31T19:12:32.838111Z',
          id='123-456-789',
          images=[
              'gcr.io/my-project/image',
          ],
          projectId='my-project',
          status=status,
          logsBucket='gs://my-project_cloudbuild/logs',
          source=self.cloudbuild_v1_messages.Source(
              storageSource=self.cloudbuild_v1_messages.StorageSource(
                  bucket='my-project_cloudbuild',
                  object=self.frozen_zip_filename,
                  generation=123,
              )),
          steps=[
              self.cloudbuild_v1_messages.BuildStep(
                  name='gcr.io/cloud-builders/docker',
                  args=[
                      'build', '--no-cache', '-t', 'gcr.io/my-project/image',
                      '.'
                  ],
              ),
          ],
          timeout='600.000s')

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=_MakeBuild(self._statuses.QUEUED))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self.mocked_cloudbuild_v1.projects_builds.Get.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsGetRequest(
            id='123-456-789',
            projectId='my-project',
        ),
        response=_MakeBuild(self._statuses.QUEUED))

    self.mocked_cloudbuild_v1.projects_builds.Get.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsGetRequest(
            id='123-456-789',
            projectId='my-project',
        ),
        response=_MakeBuild(self._statuses.QUEUED))

    self.mocked_cloudbuild_v1.projects_builds.Get.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsGetRequest(
            id='123-456-789',
            projectId='my-project',
        ),
        response=_MakeBuild(self._statuses.WORKING))

    self.AddHTTPResponse(
        'https://storage.googleapis.com/my-project_cloudbuild/'
        'logs/log-123-456-789.txt',
        request_headers={'Range': 'bytes=0-'},
        status=200,
        body='Here is some streamed\ndata for you to print\n')

    self.mocked_cloudbuild_v1.projects_builds.Get.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsGetRequest(
            id='123-456-789',
            projectId='my-project',
        ),
        response=_MakeBuild(self._statuses.SUCCESS))

    self.AddHTTPResponse(
        'https://storage.googleapis.com/my-project_cloudbuild/'
        'logs/log-123-456-789.txt',
        request_headers={'Range': 'bytes=44-'},
        status=200,
        body='Here the last line\n')

    self.AddHTTPResponse(
        'https://storage.googleapis.com/my-project_cloudbuild/'
        'logs/log-123-456-789.txt',
        request_headers={'Range': 'bytes=63-'},
        status=200,
        body='')

    self.AddHTTPResponse(
        'https://storage.googleapis.com/my-project_cloudbuild/'
        'logs/log-123-456-789.txt',
        request_headers={'Range': 'bytes=63-'},
        status=200,
        body='')

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image'
    ])

    self.AssertOutputContains(
        """\
Here is some streamed
data for you to print
Here the last line
""",
        normalize_space=True)

  def testCreateAndStreamButFAILURE(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    def _MakeBuild(status):
      return self.cloudbuild_v1_messages.Build(
          createTime='2016-03-31T19:12:32.838111Z',
          id='123-456-789',
          images=[
              'gcr.io/my-project/image',
          ],
          projectId='my-project',
          status=status,
          logsBucket='gs://my-project_cloudbuild/logs',
          source=self.cloudbuild_v1_messages.Source(
              storageSource=self.cloudbuild_v1_messages.StorageSource(
                  bucket='my-project_cloudbuild',
                  object=self.frozen_zip_filename,
                  generation=123,
              )),
          steps=[
              self.cloudbuild_v1_messages.BuildStep(
                  name='gcr.io/cloud-builders/docker',
                  args=[
                      'build', '--no-cache', '-t', 'gcr.io/my-project/image',
                      '.'
                  ],
              ),
          ],
          timeout='600.000s')

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=_MakeBuild(self._statuses.QUEUED))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self.mocked_cloudbuild_v1.projects_builds.Get.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsGetRequest(
            id='123-456-789',
            projectId='my-project',
        ),
        response=_MakeBuild(self._statuses.QUEUED))

    self.mocked_cloudbuild_v1.projects_builds.Get.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsGetRequest(
            id='123-456-789',
            projectId='my-project',
        ),
        response=_MakeBuild(self._statuses.QUEUED))

    self.mocked_cloudbuild_v1.projects_builds.Get.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsGetRequest(
            id='123-456-789',
            projectId='my-project',
        ),
        response=_MakeBuild(self._statuses.WORKING))

    self.AddHTTPResponse(
        'https://storage.googleapis.com/my-project_cloudbuild/'
        'logs/log-123-456-789.txt',
        request_headers={'Range': 'bytes=0-'},
        status=200,
        body='Here is some streamed\ndata for you to print\n')

    self.mocked_cloudbuild_v1.projects_builds.Get.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsGetRequest(
            id='123-456-789',
            projectId='my-project',
        ),
        response=_MakeBuild(self._statuses.FAILURE))

    self.AddHTTPResponse(
        'https://storage.googleapis.com/my-project_cloudbuild/'
        'logs/log-123-456-789.txt',
        request_headers={'Range': 'bytes=44-'},
        status=200,
        body='Here the last line\n')

    self.AddHTTPResponse(
        'https://storage.googleapis.com/my-project_cloudbuild/'
        'logs/log-123-456-789.txt',
        request_headers={'Range': 'bytes=63-'},
        status=200,
        body='')

    self.AddHTTPResponse(
        'https://storage.googleapis.com/my-project_cloudbuild/'
        'logs/log-123-456-789.txt',
        request_headers={'Range': 'bytes=63-'},
        status=200,
        body='')
    with self.assertRaisesRegex(core_exceptions.Error, 'FAILURE'):
      self._Run([
          'builds', 'submit', 'gs://bucket/object.zip',
          '--tag=gcr.io/my-project/image'
      ])

    self.AssertOutputContains(
        """\
Here is some streamed
data for you to print
Here the last line
""",
        normalize_space=True)

  def testCreateConfig(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/cloud-builders/docker',
                    args=['build', '-t', 'gcr.io/my-project/image', '.'],
                ),
            ],
            timeout='200.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
                timeout='200s',
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    config_path = self.Touch(
        '.',
        'config.yaml',
        contents=_MakeConfig(images=['gcr.io/my-project/image'], timeout=200))
    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip', '--config', config_path,
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateConfigSubstitutions(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))
    substitutions_type = self.cloudbuild_v1_messages.Build.SubstitutionsValue
    substitutions = self.cloudbuild_v1_messages.Build.SubstitutionsValue(
        additionalProperties=[
            substitutions_type.AdditionalProperty(
                key='_DAY_OF_WEEK', value='tuesday'),
            substitutions_type.AdditionalProperty(
                key='_FAVORITE_COLOR', value='blue')
        ])

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/cloud-builders/docker',
                    args=['build', '-t', 'gcr.io/my-project/image', '.'],
                ),
            ],
            timeout='200.000s',
            substitutions=substitutions))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
                timeout='200s',
                substitutions=substitutions),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    config_path = self.Touch(
        '.',
        'config.yaml',
        contents=_MakeConfig(images=['gcr.io/my-project/image'], timeout=200))
    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip', '--config', config_path,
        '--async', '--substitutions',
        '_DAY_OF_WEEK=tuesday,_FAVORITE_COLOR=blue'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testManyImages(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/cloud-builders/docker',
                    args=['build', '-t', 'gcr.io/my-project/image', '.'],
                ),
            ],
            timeout='200.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image1',
                    'gcr.io/my-project/image2',
                    'gcr.io/my-project/image3',
                    'gcr.io/my-project/image4',
                    'gcr.io/my-project/image5',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
                timeout='200s',
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    config_path = self.Touch(
        '.',
        'config.yaml',
        contents=_MakeConfig(
            images=['gcr.io/my-project/image{}'.format(i) for i in range(1, 6)],
            timeout=200))
    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip', '--config', config_path,
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateConfigWithTimeout(self):
    properties.VALUES.builds.timeout.Set('200')
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/cloud-builders/docker',
                    args=['build', '-t', 'gcr.io/my-project/image', '.'],
                ),
            ],
            timeout='200.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
                timeout='200s',
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    config_path = self.Touch(
        '.',
        'config.yaml',
        contents=_MakeConfig(images=['gcr.io/my-project/image']))
    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip', '--config', config_path,
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testBadLocalFile(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))

    bad_tarball_path = self.Touch(
        '.', 'source.badfile', contents='pretend this is a valid tarball')
    with self.assertRaisesRegex(c_exceptions.BadFileException, 'Local file'):
      self._Run([
          'builds', 'submit', bad_tarball_path, '--tag=gcr.io/my-project/image',
          '--async'
      ])

  def testNotGCRTag(self):
    img = 'gcr-staging.sandbox.googleapis.com/my-registry/my-image'
    with self.assertRaisesRegex(c_exceptions.InvalidArgumentException,
                                'Tag value must be in the gcr.io'):
      self._Run(['builds', 'submit', '.', '--tag=' + img])

    # Confirm that hidden property disables Exception for non-gcr.io registry
    properties.VALUES.builds.check_tag.Set(False)
    b_in = self.cloudbuild_v1_messages.Build(
        images=[img],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                args=[
                    'build', '--network', 'cloudbuild', '--no-cache', '-t', img,
                    '.'
                ],
                name='gcr.io/cloud-builders/docker',
            ),
        ],
    )
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[img],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/cloud-builders/docker',
                args=[
                    'build', '--network', 'cloudbuild', '--no-cache', '-t', img,
                    '.'
                ],
            ),
        ],
        timeout='600.000s')
    self.ExpectMessagesForSimpleBuild(b_in, b_out)
    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip', '--tag=' + img, '--async'
    ])

  def testNoImage(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/cloud-builders/docker',
                    args=['build', '-t', 'gcr.io/my-project/image', '.'],
                ),
            ],
            timeout='200.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
                timeout='200s',
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    config_path = self.Touch(
        '.', 'config.yaml', contents=_MakeConfig(timeout=200))
    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip', '--config', config_path,
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testTimeout(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[
            'gcr.io/my-project/image',
        ],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        logUrl='mockLogURL',
        timeout='62.000s',
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=[
            'gcr.io/my-project/image',
        ],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        timeout='62s',
    )
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async', '--timeout=1m2s'
    ])

  def testTimeoutBareSeconds(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[
            'gcr.io/my-project/image',
        ],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        logUrl='mockLogURL',
        timeout='62.000s',
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=[
            'gcr.io/my-project/image',
        ],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        timeout='62s',
    )
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--async', '--timeout=62'
    ])

  def testDomainScopedProject(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[
            'gcr.io/google.com/foobar/image',
        ],
        projectId='google.com:foobar',
        status=self._statuses.QUEUED,
        logsBucket='gs://elgoog_com_foobar_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='elgoog_com_foobar_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                name='gcr.io/cloud-builders/docker',
                args=[
                    'build', '--network', 'cloudbuild', '--no-cache', '-t',
                    'gcr.io/google.com/foobar/image', '.'
                ],
            ),
        ],
        logUrl='mockLogURL',
        timeout='600.000s',
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=[
            'gcr.io/google.com/foobar/image',
        ],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='elgoog_com_foobar_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=[
            self.cloudbuild_v1_messages.BuildStep(
                args=[
                    'build', '--network', 'cloudbuild', '--no-cache', '-t',
                    'gcr.io/google.com/foobar/image', '.'
                ],
                name='gcr.io/cloud-builders/docker',
            ),
        ],
    )
    self.ExpectMessagesForSimpleBuild(
        b_in, b_out, build_project='google.com:foobar')

    self._Run([
        'builds', 'submit', '--project=google.com:foobar',
        'gs://bucket/object.zip', '--tag=gcr.io/google.com/foobar/image',
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/google.com%3Afoobar/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://elgoog_com_foobar_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testDefaultSourceSuccess(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Insert.Expect(
        self.storage_v1_messages.StorageObjectsInsertRequest(
            bucket='my-project_cloudbuild',
            name=self.frozen_tgz_filename,
            object=self.storage_v1_messages.Object(size=100),
        ),
        response=self.storage_v1_messages.Object(
            bucket='my-project_cloudbuild',
            name=self.frozen_tgz_filename,
            generation=123,
            size=100,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_tgz_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/cloud-builders/docker',
                    args=[
                        'build', '--no-cache', '-t', 'gcr.io/my-project/image',
                        '.'
                    ],
                ),
            ],
            timeout='600.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_tgz_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self.Touch('.', 'Dockerfile', contents='FROM busybox\n')
    self._Run(['builds', 'submit', '--tag=gcr.io/my-project/image', '--async'])
    self.AssertErrContains('Uploading tarball of ')
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_tgz_filename} - QUEUED
""".format(frozen_tgz_filename=self.frozen_tgz_filename),
        normalize_space=True)

  def testNoSourceSuccess(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[
            'gcr.io/my-project/image',
        ],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=None,
        steps=_DOCKER_BUILD_STEPS,
        logUrl='mockLogURL',
        timeout='600.000s',
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=[
            'gcr.io/my-project/image',
        ],
        source=None,
        steps=_DOCKER_BUILD_STEPS,
    )
    self.ExpectMessagesForSimpleBuild(b_in, b_out, gcs=False)

    self._Run([
        'builds', 'submit', '--no-source', '--tag=gcr.io/my-project/image',
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - - - QUEUED
""",
        normalize_space=True)
    self.AssertErrContains('Logs are available at')
    self.AssertErrContains('mockLogURL')
    self.AssertErrNotContains('Logs can be found in the Cloud Console')

  def testInvalidConfig(self):
    bad_config = """\
steps:
  - name: 'foo'
    args:
      - 'bar'
  - 'foobar'
"""
    config_path = self.Touch('.', 'config.yaml', contents=bad_config)
    with self.assertRaises(cloudbuild_util.ParseProtoException):
      self._Run([
          'builds', 'submit', 'gs://bucket/object.zip', '--config', config_path
      ])

  def testConfigAndTagExclusive(self):
    config_path = self.Touch('.', 'config.yaml')
    with self.assertRaises(MockArgumentError):
      self._Run([
          'builds', 'submit', 'gs://bucket/object.zip', '--config', config_path,
          '--tag=gcr.io/my-project/image'
      ])

  def testNoEmptyTag(self):
    with self.assertRaises(c_exceptions.InvalidArgumentException):
      self._Run(['builds', 'submit', 'gs://bucket/object.zip', '--tag='])

  def testNoEmptyConfigPath(self):
    with self.assertRaises(c_exceptions.InvalidArgumentException):
      self._Run(['builds', 'submit', 'gs://bucket/object.zip', '--config='])

  def testDefaultConfigPath(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/cloud-builders/docker',
                    args=['build', '-t', 'gcr.io/my-project/image', '.'],
                ),
            ],
            timeout='200.000s'))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=_DOCKER_BUILD_STEPS,
                timeout='200s',
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self.Touch(
        '.',
        'cloudbuild.yaml',
        contents=_MakeConfig(images=['gcr.io/my-project/image'], timeout=200))
    self._Run(['builds', 'submit', 'gs://bucket/object.zip', '--async'])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateMachineTypeSuccess(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=[
            'gcr.io/my-project/image',
        ],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        logUrl='mockLogURL',
        timeout='600.000s',
        options=self.cloudbuild_v1_messages.BuildOptions(
            machineType=self._vmtypes.N1_HIGHCPU_8),
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=[
            'gcr.io/my-project/image',
        ],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        options=self.cloudbuild_v1_messages.BuildOptions(
            machineType=self._vmtypes.N1_HIGHCPU_8),
    )
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--machine-type=n1-highcpu-8',
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateWrongMachineType(self):
    with self.assertRaises(Exception):
      self._Run([
          'builds', 'submit', '--tag=gcr.io/my-project/image',
          '--machine-type=n1-wrong-1', '--no-source'
      ])

  def testCreateUnspecifiedMachineType(self):
    with self.assertRaises(Exception):
      self._Run([
          'builds', 'submit', '--tag=gcr.io/my-project/image',
          '--machine-type=unspecified', '--no-source'
      ])

  def testCreateDiskSizeSuccess(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=['gcr.io/my-project/image'],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        logUrl='mockLogURL',
        timeout='600.000s',
        options=self.cloudbuild_v1_messages.BuildOptions(diskSizeGb=111),
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=['gcr.io/my-project/image'],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        options=self.cloudbuild_v1_messages.BuildOptions(diskSizeGb=111),
    )
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--disk-size=111', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateWrongDiskSize(self):
    with self.assertRaises(Exception):
      self._Run([
          'builds', 'submit', '--tag=gcr.io/my-project/image', '--disk-size=1',
          '--no-source'
      ])

  def testCreateVMTypeAndDiskSizeSuccess(self):
    b_out = self.cloudbuild_v1_messages.Build(
        createTime='2016-03-31T19:12:32.838111Z',
        id='123-456-789',
        images=['gcr.io/my-project/image'],
        projectId='my-project',
        status=self._statuses.QUEUED,
        logsBucket='gs://my-project_cloudbuild/logs',
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        logUrl='mockLogURL',
        timeout='600.000s',
        options=self.cloudbuild_v1_messages.BuildOptions(
            diskSizeGb=111,
            machineType=self._vmtypes.N1_HIGHCPU_8,
        ),
    )
    b_in = self.cloudbuild_v1_messages.Build(
        images=['gcr.io/my-project/image'],
        source=self.cloudbuild_v1_messages.Source(
            storageSource=self.cloudbuild_v1_messages.StorageSource(
                bucket='my-project_cloudbuild',
                object=self.frozen_zip_filename,
                generation=123,
            )),
        steps=_DOCKER_BUILD_STEPS,
        options=self.cloudbuild_v1_messages.BuildOptions(
            diskSizeGb=111,
            machineType=self._vmtypes.N1_HIGHCPU_8,
        ),
    )
    self.ExpectMessagesForSimpleBuild(b_in, b_out)

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--tag=gcr.io/my-project/image', '--disk-size=111',
        '--machine-type=n1-highcpu-8', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)


class SubmitTestBeta(SubmitTest):

  def PreSetUp(self):
    self.track = calliope_base.ReleaseTrack.BETA


class SubmitTestAlpha(SubmitTestBeta):

  def PreSetUp(self):
    self.track = calliope_base.ReleaseTrack.ALPHA

  def testCreateConfigWithPack(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/k8s-skaffold/pack',
                    entrypoint='pack',
                    args=[
                        'build', 'gcr.io/my-project/image', '--builder',
                        _DEFAULT_BUILDPACK_BUILDER
                    ],
                ),
            ]))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    u'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=[
                    core_apis.GetMessagesModule('cloudbuild', 'v1').BuildStep(
                        name='gcr.io/k8s-skaffold/pack',
                        entrypoint='pack',
                        args=[
                            'build', 'gcr.io/my-project/image', '--builder',
                            _DEFAULT_BUILDPACK_BUILDER
                        ],
                    )
                ],
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--pack=image=gcr.io/my-project/image', '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateConfigWithPackAndBuilder(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/k8s-skaffold/pack',
                    entrypoint='pack',
                    args=[
                        'build', 'gcr.io/my-project/image', '--builder',
                        'cnbs/sample-builder:bionic'
                    ],
                ),
            ]))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    u'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=[
                    core_apis.GetMessagesModule('cloudbuild', 'v1').BuildStep(
                        name='gcr.io/k8s-skaffold/pack',
                        entrypoint='pack',
                        args=[
                            'build', 'gcr.io/my-project/image', '--builder',
                            'cnbs/sample-builder:bionic'
                        ],
                    )
                ],
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--pack=image=gcr.io/my-project/image,builder=cnbs/sample-builder:bionic',
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateConfigWithPackAndBuilderAndEnvVars(self):
    self.mocked_storage_v1.buckets.Get.Expect(
        self.storage_v1_messages.StorageBucketsGetRequest(
            bucket='my-project_cloudbuild'),
        response=self.storage_v1_messages.Bucket(id='my-project_cloudbuild'))
    self.mocked_storage_v1.buckets.List.Expect(
        self.storage_v1_messages.StorageBucketsListRequest(
            project='my-project',
            prefix='my-project_cloudbuild',
        ),
        response=self.storage_v1_messages.Buckets(
            items=[self.storage_v1_messages.Bucket(
                id='my-project_cloudbuild')]))
    self.mocked_storage_v1.objects.Rewrite.Expect(
        self.storage_v1_messages.StorageObjectsRewriteRequest(
            destinationBucket='my-project_cloudbuild',
            destinationObject=self.frozen_zip_filename,
            sourceBucket='bucket',
            sourceObject='object.zip',
        ),
        response=self.storage_v1_messages.RewriteResponse(
            resource=self.storage_v1_messages.Object(
                bucket='my-project_cloudbuild',
                name=self.frozen_zip_filename,
                generation=123,
            ),
            done=True,
        ))

    op_metadata = self.cloudbuild_v1_messages.BuildOperationMetadata(
        build=self.cloudbuild_v1_messages.Build(
            createTime='2016-03-31T19:12:32.838111Z',
            id='123-456-789',
            images=[
                'gcr.io/my-project/image',
            ],
            projectId='my-project',
            status=self._statuses.QUEUED,
            logsBucket='gs://my-project_cloudbuild/logs',
            source=self.cloudbuild_v1_messages.Source(
                storageSource=self.cloudbuild_v1_messages.StorageSource(
                    bucket='my-project_cloudbuild',
                    object=self.frozen_zip_filename,
                    generation=123,
                )),
            steps=[
                self.cloudbuild_v1_messages.BuildStep(
                    name='gcr.io/k8s-skaffold/pack',
                    entrypoint='pack',
                    args=[
                        'build', 'gcr.io/my-project/image', '--builder',
                        'cnbs/sample-builder:bionic', '--env',
                        'foo=bar,hello=world'
                    ],
                ),
            ]))

    self.mocked_cloudbuild_v1.projects_builds.Create.Expect(
        self.cloudbuild_v1_messages.CloudbuildProjectsBuildsCreateRequest(
            build=self.cloudbuild_v1_messages.Build(
                images=[
                    u'gcr.io/my-project/image',
                ],
                source=self.cloudbuild_v1_messages.Source(
                    storageSource=self.cloudbuild_v1_messages.StorageSource(
                        bucket='my-project_cloudbuild',
                        object=self.frozen_zip_filename,
                        generation=123,
                    )),
                steps=[
                    core_apis.GetMessagesModule('cloudbuild', 'v1').BuildStep(
                        name='gcr.io/k8s-skaffold/pack',
                        entrypoint='pack',
                        args=[
                            'build', 'gcr.io/my-project/image', '--builder',
                            'cnbs/sample-builder:bionic', '--env',
                            'foo=bar,hello=world'
                        ],
                    )
                ],
            ),
            projectId='my-project',
        ),
        response=self.cloudbuild_v1_messages.Operation(
            metadata=encoding.JsonToMessage(
                self.cloudbuild_v1_messages.Operation.MetadataValue,
                encoding.MessageToJson(op_metadata))))

    self._Run([
        'builds', 'submit', 'gs://bucket/object.zip',
        '--pack=^--^image=gcr.io/my-project/image--builder=cnbs/sample-builder:bionic--env=foo=bar,hello=world',
        '--async'
    ])
    self.AssertErrContains(
        """\
Created [https://cloudbuild.googleapis.com/v1/projects/my-project/builds/123-456-789].
""",
        normalize_space=True)
    self.AssertOutputContains(
        """\
ID CREATE_TIME DURATION SOURCE IMAGES STATUS
123-456-789 2016-03-31T19:12:32+00:00 - gs://my-project_cloudbuild/{frozen_zip_filename} - QUEUED
""".format(frozen_zip_filename=self.frozen_zip_filename),
        normalize_space=True)

  def testCreateConfigWithPackNoImage(self):
    with self.assertRaises(c_exceptions.InvalidArgumentException):
      self._Run([
          'builds', 'submit', 'gs://bucket/object.zip',
          '--pack=builder=cnbs/sample-builder:bionic', '--async'
      ])

  def testCreateConfigWithPackWithInvalidImage(self):
    with self.assertRaises(c_exceptions.InvalidArgumentException):
      self._Run([
          'builds', 'submit', 'gs://bucket/object.zip',
          '--pack=image=docker.io/image', '--async'
      ])


if __name__ == '__main__':
  test_case.main()
