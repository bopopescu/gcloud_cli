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
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import json
import os.path
import subprocess
import textwrap

from googlecloudsdk.command_lib.code import kubernetes
from googlecloudsdk.core import config
from googlecloudsdk.core.updater import update_manager
from tests.lib import test_case
import mock
import six


class Matcher(object):

  def __init__(self, matcher):
    self._matcher = matcher

  def __eq__(self, other):
    return self._matcher(other)


class SdkPathTestCase(test_case.TestCase):

  SDK_PATH = os.path.join("sdk", "path")

  def SetUp(self):
    self.StartObjectPatch(config, "Paths").return_value.sdk_root = self.SDK_PATH
    self.StartObjectPatch(update_manager.UpdateManager,
                          "EnsureInstalledAndRestart").return_value = True


class StartMinikubeTest(SdkPathTestCase):

  def testAlreadyRunning(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        status = six.ensure_binary(json.dumps({"Host": "Running"}))
        popen.return_value.communicate.return_value = (status, None)

        with kubernetes.Minikube("cluster-name"):
          # Assert "minikube start" is not called.
          check_call.assert_not_called()

    self.assertIn("stop", check_call.call_args[0][0])

  def testNotYetRunning(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        status = six.ensure_binary(json.dumps({}))
        popen.return_value.communicate.return_value = (status, None)

        with kubernetes.Minikube("cluster-name"):
          self.assertIn("cluster-name", check_call.call_args[0][0])
          self.assertIn("start", check_call.call_args[0][0])

    self.assertIn("stop", check_call.call_args[0][0])

  def testDriver(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        status = six.ensure_binary(json.dumps({}))
        popen.return_value.communicate.return_value = (status, None)

        with kubernetes.Minikube("cluster-name", vm_driver="my-driver"):
          self.assertIn("--vm-driver=my-driver", check_call.call_args[0][0])

    self.assertIn("stop", check_call.call_args[0][0])

  def testDockerDriver(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        status = six.ensure_binary(json.dumps({}))
        popen.return_value.communicate.return_value = (status, None)

        with kubernetes.Minikube("cluster-name", vm_driver="docker"):
          check_call.assert_called_once_with(
              Matcher(lambda cmd: "--vm-driver=docker" in cmd),
              stdout=mock.ANY,
              stderr=mock.ANY)
          check_call.assert_called_once_with(
              Matcher(lambda cmd: "--container-runtime=docker" in cmd),
              stdout=mock.ANY,
              stderr=mock.ANY)

    self.assertIn("stop", check_call.call_args[0][0])


class MinikubeClusterTest(SdkPathTestCase):

  def testEnvVars(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      env_vars = six.ensure_binary(
          textwrap.dedent("""\
            DOCKER_A=abcd
            DOCKER_B=1234
            MY_ENV_VAR=My23
            ENV_VAR_WITH_EQ=a=3
      """))
      popen.return_value.communicate.return_value = (env_vars, None)

      minikube_cluster = kubernetes.MinikubeCluster("cluster-name", False)

      expected_env_vars = {
          "DOCKER_A": "abcd",
          "DOCKER_B": "1234",
          "MY_ENV_VAR": "My23",
          "ENV_VAR_WITH_EQ": "a=3"
      }
      self.assertEqual(minikube_cluster.env_vars, expected_env_vars)


class StartKindTest(SdkPathTestCase):

  PATH_TO_KIND = os.path.join(SdkPathTestCase.SDK_PATH, "bin", "kind")

  def testAlreadyRunning(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        popen.return_value.communicate.return_value = ("cluster-name\n", None)

        with kubernetes.KindClusterContext("cluster-name"):
          # Assert "kind create cluster" is not called.
          check_call.assert_not_called()

    self.assertEqual(popen.call_args[0][0],
                     [self.PATH_TO_KIND, "get", "clusters"])
    self.assertIn("delete", check_call.call_args[0][0])

  def testNotYetRunning(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        popen.return_value.communicate.return_value = ("", None)

        with kubernetes.KindClusterContext("cluster-name"):
          check_call.assert_called_once_with([
              self.PATH_TO_KIND, "create", "cluster", "--name", "cluster-name"
          ])

    self.assertIn("delete", check_call.call_args[0][0])

  def testDeleteKind(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        popen.return_value.communicate.return_value = ("cluster-name\n", None)

        kubernetes.DeleteKindClusterIfExists("cluster-name")

    check_call.assert_called_once_with(
        [self.PATH_TO_KIND, "delete", "cluster", "--name", "cluster-name"],
        stdout=mock.ANY,
        stderr=mock.ANY)


class KubeNamespace(SdkPathTestCase):

  PATH_TO_KUBECTL = os.path.join(SdkPathTestCase.SDK_PATH, "bin", "kubectl")

  def testNamespaceAlreadyExists(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        namespaces = six.b("namespace/a\nnamespace/b\n")
        popen.return_value.communicate.return_value = (namespaces, None)

        with kubernetes.KubeNamespace("a"):
          check_call.assert_not_called()

        with kubernetes.KubeNamespace("b"):
          check_call.assert_not_called()

  def testNamespaceNotExists(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        namespaces = six.b("namespace/a")
        popen.return_value.communicate.return_value = (namespaces, None)

        with kubernetes.KubeNamespace("b"):
          self.assertEqual(check_call.call_args[0][0],
                           [self.PATH_TO_KUBECTL, "create", "namespace", "b"])

        self.assertEqual(check_call.call_args_list[1][0][0],
                         [self.PATH_TO_KUBECTL, "delete", "namespace", "b"])

  def testCallWithContext(self):
    with mock.patch.object(subprocess, "Popen") as popen:
      with mock.patch.object(subprocess, "check_call") as check_call:
        namespaces = six.b("namespace/a")
        popen.return_value.communicate.return_value = (namespaces, None)

        with kubernetes.KubeNamespace("b", "my-context"):
          self.assertEqual(popen.call_args[0][0], [
              self.PATH_TO_KUBECTL, "--context", "my-context", "get",
              "namespaces", "-o", "name"
          ])
          self.assertEqual(check_call.call_args_list[0][0][0], [
              self.PATH_TO_KUBECTL, "--context", "my-context", "create",
              "namespace", "b"
          ])

        self.assertEqual(check_call.call_args_list[1][0][0], [
            self.PATH_TO_KUBECTL, "--context", "my-context", "delete",
            "namespace", "b"
        ])
