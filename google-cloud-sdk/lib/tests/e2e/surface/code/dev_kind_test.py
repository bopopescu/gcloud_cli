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
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import contextlib
import datetime
import json
import os
import signal
import time

from googlecloudsdk.core.util import retry
from tests.lib import cli_test_base
from tests.lib import sdk_test_base
from tests.lib import test_case
import six
import six.moves.urllib.request


class SkaffoldContext(object):
  """Context of running skaffold."""

  _EVENTS_READ_CHUNK_SIZE_BYTES = 50

  def __init__(self, events_port):
    self._events_port = events_port

  def GetLocalPort(self, service_name):
    """Get the local port of a port-forwarded kubernetes service."""
    url = 'http://localhost:%s/v1/events' % self._events_port
    with contextlib.closing(six.moves.urllib.request.urlopen(url)) as response:
      for line in self._ReadStreamingLines(response):
        try:
          payload = json.loads(line)
          if not isinstance(payload, dict):
            continue
          event = payload['result']['event']
          if ('portEvent' in event and
              event['portEvent']['resourceName'] == service_name):
            return event['portEvent']['localPort']
        except ValueError:
          # Some of the output will not be json. We don't care about those
          # lines. Ignore the line if the line is invalid json.
          pass
      return None

  def _ReadStreamingLines(self, response):
    # The standard http response readline waits until either the buffer is full
    # or the connection closes. The connection to read the event stream
    # stays open forever until the client closes it. As a result, we can get
    # into a state where http readline() never returns because the buffer
    # is not full but the server is waiting for the test to do something
    # to generate more events.
    # This function will not block a buffer not being full. os.read() will
    # return data of any size if a response is received. This allows the test
    # to make progress.
    pending = None

    while True:
      chunk = six.ensure_text(
          os.read(response.fp.fileno(), self._EVENTS_READ_CHUNK_SIZE_BYTES))
      if not chunk:
        break

      if pending is not None:
        chunk = pending + chunk
        pending = None

      lines = chunk.split('\n')
      if lines and lines[-1]:
        pending = lines.pop()

      for line in lines:
        yield line

    if pending:
      yield pending


class TerminateWithSigInt(object):
  """Context manager that terminates a process with SIGINT."""

  def __init__(self,
               proc,
               timeout,
               check_interval=datetime.timedelta(seconds=5)):
    self._proc = proc
    self._timeout = timeout
    self._check_interval = check_interval

  def __enter__(self):
    return self

  def __exit__(self, exception_type, exception_value, traceback):
    os.kill(self._proc.pid, signal.SIGINT)

    deadline = datetime.datetime.now() + self._timeout
    while (self._IsStillRunning(self._proc) and
           datetime.datetime.now() < deadline):
      time.sleep(self._check_interval)

  @staticmethod
  def _IsStillRunning(proc):
    return not hasattr(proc, 'returncode') and not hasattr(proc, 'exitcode')


class DevOnKindTest(sdk_test_base.BundledBase, cli_test_base.CliTestBase):

  KIND_CLUSTER_PREFIX = 'gcloud-local-dev'

  def SetUp(self):
    self.ShowTestOutput()

    # Bump up the size limit to accomodate the docker image when it is stored
    # in the kind image cache.
    self._dirs_size_limit_method = 2 << 21

  def TearDown(self):
    # If the kind cluster was not properly torn down as part of the
    # gcloud local dev command, delete the cluster here.
    result = self.ExecuteLegacyScript('kind', ['get', 'clusters'])
    if self.ClusterName() in result.stdout:
      self.ExecuteLegacyScript(
          'kind', ['delete', 'cluster', '--name= ' + self.ClusterName()])

  def ClusterName(self):
    return self.KIND_CLUSTER_PREFIX + self.id().split('.')[-1]

  def assertIsUp(self, skaffold_context, service_name):
    local_port = skaffold_context.GetLocalPort(service_name=service_name)
    retryer = retry.Retryer()
    self.assertTrue(
        retryer.RetryOnException(self._IsUp, [local_port], sleep_ms=5000))

  @staticmethod
  def _IsUp(port):
    url = 'http://127.0.0.1:' + six.text_type(port) + '/'
    with contextlib.closing(six.moves.urllib.request.urlopen(url)) as response:
      return response.getcode() == 200

  def _GetServices(self, context, namespace=None):
    args = ['--context', context]
    if namespace:
      args += ['--namespace', namespace]
    args += ['get', 'services', '-o', 'name']

    result = self.ExecuteLegacyScript('kubectl', args)
    return six.ensure_text(result.stdout).splitlines()

  @contextlib.contextmanager
  def _RunDevelopmentServer(self,
                            dockerfile,
                            service_name,
                            additional_gcloud_flags=None):
    skaffold_event_port = self.GetPort()

    additional_skaffold_flags = ('--enable-rpc,--rpc-http-port=%s' %
                                 str(skaffold_event_port))
    gcloud_args = [
        'alpha',
        'code',
        'dev',
        '--service-name=' + service_name,
        '--image-name=fake-image-name',
        '--dockerfile=' + dockerfile,
        '--stop-cluster',
        '--kind-cluster=' + self.ClusterName(),
        '--additional-skaffold-flags=%s' % additional_skaffold_flags,
    ]
    if additional_gcloud_flags:
      gcloud_args += additional_gcloud_flags

    match_strings = ['Serving Flask app']

    with self.ExecuteLegacyScriptAsync(
        'gcloud', gcloud_args, match_strings=match_strings,
        timeout=450) as process_context:
      with TerminateWithSigInt(
          process_context.p, timeout=datetime.timedelta(minutes=2)):
        yield SkaffoldContext(skaffold_event_port)

  @test_case.Filters.RunOnlyOnLinux
  def testNamespace(self):
    dockerfile = self.Resource('tests', 'e2e', 'surface', 'code', 'testdata',
                               'hello', 'Dockerfile')

    gcloud_flags = ['--namespace', 'my-namespace']
    with self._RunDevelopmentServer(
        dockerfile, 'myservice',
        additional_gcloud_flags=gcloud_flags) as skaffold_context:
      self.assertIsUp(skaffold_context, 'myservice')

      kube_context_name = 'kind-' + self.ClusterName()
      self.assertIn('service/myservice',
                    self._GetServices(kube_context_name, 'my-namespace'))

  @test_case.Filters.RunOnlyOnLinux
  def testDev(self):
    dockerfile = self.Resource('tests', 'e2e', 'surface', 'code', 'testdata',
                               'hello', 'Dockerfile')

    with self._RunDevelopmentServer(dockerfile,
                                    'myservice') as skaffold_context:
      self.assertIsUp(skaffold_context, 'myservice')


if __name__ == '__main__':
  test_case.main()
