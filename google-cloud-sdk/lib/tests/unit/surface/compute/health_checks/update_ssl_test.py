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
"""Tests for the health-checks update ssl subcommand."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import textwrap

from googlecloudsdk.calliope import base as calliope_base
from googlecloudsdk.calliope import exceptions
from googlecloudsdk.core import exceptions as core_exceptions

from tests.lib import parameterized
from tests.lib import test_case
from tests.lib.surface.compute import test_base


class HealthChecksUpdateSslTest(test_base.BaseTest, test_case.WithOutputCapture,
                                parameterized.TestCase):

  def testNoArgs(self):
    with self.AssertRaisesToolExceptionRegexp(
        'At least one property must be modified.'):
      self.Run(
          'compute health-checks update ssl my-health-check')
    self.CheckRequests()

  def testNoChange(self):
    self.make_requests.side_effect = [
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                description='fezzes are cool',
                sslHealthCheck=self.messages.SSLHealthCheck(port=80))
        ],
    ]

    self.Run('compute health-checks update ssl my-health-check '
             '--description "fezzes are cool"')

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
    )

    self.AssertErrEquals(
        'No change requested; skipping update for [my-health-check].\n',
        normalize_space=True)

  def testUriSupport(self):
    # This is the same as testRequestOption, but uses a full URI.
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='initial-req',
                port=80,
                response='ack'))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl
          https://compute.googleapis.com/compute/v1/projects/my-project/global/healthChecks/my-health-check
          --request req
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update', self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      request='req',
                      port=80,
                      response='ack')),
              project='my-project'))],
    )

  def testRequestOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='req1',
                port=80,
                response='ack'))],
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='req2',
                port=80,
                response='ack'))],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --request req2
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update', self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      request='req2',
                      port=80,
                      response='ack')),
              project='my-project'))],
    )

    # By default, the resource should not be displayed
    self.assertFalse(self.GetOutput())

  def testJsonOutput(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='req-1',
                port=80))],
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='req-2',
                port=80))],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --request req-2
          --format json
        """)

    self.assertMultiLineEqual(
        self.GetOutput(),
        textwrap.dedent("""\
            [
              {
                "name": "my-health-check",
                "sslHealthCheck": {
                  "port": 80,
                  "request": "req-2"
                },
                "type": "SSL"
              }
            ]
            """))

  def testTextOutput(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='req-1',
                port=80,
                portName='happy-port',
                response='ack-1'))],
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='req-2',
                port=80,
                portName='happy-port',
                response='ack-2'))],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --request req-2
          --format text
        """)

    self.assertMultiLineEqual(
        self.GetOutput(),
        textwrap.dedent("""\
            ---
            name:                    my-health-check
            sslHealthCheck.port:     80
            sslHealthCheck.portName: happy-port
            sslHealthCheck.request:  req-2
            sslHealthCheck.response: ack-2
            type:                    SSL
            """))

  def testYamlOutput(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='req_1',
                port=80,
                response='ack'))],
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='req_2',
                port=80,
                response='ack'))],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --request req_2
          --format yaml
        """)

    self.assertMultiLineEqual(
        self.GetOutput(),
        textwrap.dedent("""\
            ---
            name: my-health-check
            sslHealthCheck:
              port: 80
              request: req_2
              response: ack
            type: SSL
            """))

  def testUnsetRequestOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                request='my-req',
                port=80))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check --request ''
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80)),
              project='my-project'))],
    )

  def testPortOption(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(port=80))
        ],
        [],
    ])

    self.Run('compute health-checks update ssl my-health-check --port 8888')

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      portSpecification=(
                          self.messages.SSLHealthCheck
                          .PortSpecificationValueValuesEnum.USE_FIXED_PORT),
                      port=8888)),
              project='my-project'))],
    )

  def testPortNameOptionWithPreexistingPortName(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    portName='old-port'))
        ],
        [],
    ])

    self.Run('compute health-checks update ssl my-health-check '
             '--port-name new-port')

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      portSpecification=(
                          self.messages.SSLHealthCheck
                          .PortSpecificationValueValuesEnum.USE_NAMED_PORT),
                      portName='new-port')),
              project='my-project'))],
    )

  def testPortNameOptionWithoutPreexistingPortName(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck())
        ],
        [],
    ])

    self.Run('compute health-checks update ssl my-health-check '
             '--port-name new-port')

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      portSpecification=(
                          self.messages.SSLHealthCheck
                          .PortSpecificationValueValuesEnum.USE_NAMED_PORT),
                      portName='new-port')),
              project='my-project'))],
    )

  def testUnsetPortNameOption(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    portName='happy-port'))
        ],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check --port-name ''
        """)

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      portSpecification=(
                          self.messages.SSLHealthCheck
                          .PortSpecificationValueValuesEnum.USE_FIXED_PORT),)),
              project='my-project'))],
    )

  def testPortAndPortNameOption(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck())
        ],
        [],
    ])

    self.Run('compute health-checks update ssl my-health-check '
             '--port 8888 --port-name new-port')

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      portSpecification=(
                          self.messages.SSLHealthCheck
                          .PortSpecificationValueValuesEnum.USE_FIXED_PORT),
                      port=8888)),
              project='my-project'))],
    )

  def testUseServingPortOption(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck())
        ],
        [],
    ])

    self.Run('compute health-checks update ssl my-health-check '
             '--use-serving-port')

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      portSpecification=(
                          self.messages.SSLHealthCheck
                          .PortSpecificationValueValuesEnum.USE_SERVING_PORT))),
              project='my-project'))],
    )

  def testUseServingPortOptionWithPreexistingPortName(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    portName='old-port'))
        ],
        [],
    ])

    self.Run('compute health-checks update ssl my-health-check '
             '--use-serving-port')

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      portSpecification=(
                          self.messages.SSLHealthCheck
                          .PortSpecificationValueValuesEnum.USE_SERVING_PORT))),
              project='my-project'))],
    )

  @parameterized.parameters(('--port', 80), ('--port-name', 'my-port'))
  def testUseServingPortOptionErrors(self, flag, flag_value):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck())
        ],
        [],
    ])

    with self.AssertRaisesExceptionMatches(
        exceptions.InvalidArgumentException,
        'Invalid value for [--use-serving-port]: {0} cannot '
        'be specified when using: --use-serving-port'.format(flag)):
      self.Run("""
          compute health-checks update ssl my-health-check
          --use-serving-port {0} {1}
      """.format(flag, flag_value))

  def testResponseOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=88,
                portName='happy-port',
                request='req',
                response='old-response'))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --response new-response
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=88,
                      portName='happy-port',
                      request='req',
                      response='new-response')),
              project='my-project'))],
    )

  def testUnsetResponseOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                response='my-ack',
                port=80))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check --response ''
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80)),
              project='my-project'))],
    )

  def testCheckIntervalOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=80,
                response='///'))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --check-interval 30s
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80,
                      response='///'),
                  checkIntervalSec=30),
              project='my-project'))],
    )

  def testCheckIntervalBadValue(self):
    with self.AssertRaisesToolExceptionRegexp(
        'must not be less than 1 second or greater than 300 seconds'):
      self.Run("""
          compute health-checks update ssl my-health-check
            --check-interval 0
          """)
    self.CheckRequests()

  def testTimeoutSecOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=80,
                request='/',
                response='///'))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --timeout 2m
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80,
                      request='/',
                      response='///'),
                  timeoutSec=120),
              project='my-project'))],
    )

  def testTimeoutBadValue(self):
    with self.AssertRaisesToolExceptionRegexp(
        'must not be less than 1 second or greater than 300 seconds'):
      self.Run("""
          compute health-checks update ssl my-health-check
             --timeout 0
          """)
    self.CheckRequests()

  def testHealthyThresholdOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=80))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --healthy-threshold 7
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80),
                  healthyThreshold=7),
              project='my-project'))],
    )

  def testHealthyTresholdBadValue(self):
    with self.AssertRaisesToolExceptionRegexp(
        'must be an integer between 1 and 10'):
      self.Run("""
          compute health-checks update ssl my-health-check
            --healthy-threshold 0
          """)
    self.CheckRequests()

  def testUnhealthyThresholdOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=80,
                portName='happy-port'))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --unhealthy-threshold 8
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80,
                      portName='happy-port'),
                  unhealthyThreshold=8),
              project='my-project'))],
    )

  def testUnhealthyTresholdBadValue(self):
    with self.AssertRaisesToolExceptionRegexp(
        r'\[--unhealthy-threshold\] must be an integer between 1 and 10, '
        r'inclusive; received \[0\].'):
      self.Run("""
          compute health-checks update ssl my-health-check
            --unhealthy-threshold 0
          """)
    self.CheckRequests()

  def testDescriptionOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=80))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --description 'Circulation, Airway, Breathing'
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80),
                  description='Circulation, Airway, Breathing'),
              project='my-project'))],
    )

  def testUnsetDescriptionOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=80),
            description='Short Description')],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --description ''
        """)

    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80)),
              project='my-project'))],
    )

  def testUpdatingDifferentProtocol(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.TCP,
            tcpHealthCheck=self.messages.TCPHealthCheck(
                port=80))],
        [],
    ])

    with self.assertRaisesRegex(
        core_exceptions.Error,
        'update ssl subcommand applied to health check with protocol TCP'):
      self.Run(
          'compute health-checks update ssl my-health-check --port 8888')

  def testProxyHeaderOption(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=80))],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --proxy-header PROXY_V1
        """)
    self.CheckRequests(
        [(self.compute.healthChecks,
          'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project'))],
        [(self.compute.healthChecks,
          'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80,
                      proxyHeader=(self.messages.SSLHealthCheck
                                   .ProxyHeaderValueValuesEnum.PROXY_V1))),
              project='my-project'))],
    )

  def testProxyHeaderBadValue(self):
    self.make_requests.side_effect = iter([
        [self.messages.HealthCheck(
            name='my-health-check',
            type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
            sslHealthCheck=self.messages.SSLHealthCheck(
                port=80))],
        [],
    ])

    with self.AssertRaisesArgumentErrorRegexp(
        'argument --proxy-header: Invalid choice: \'bad_value\''):
      self.Run("""
          compute health-checks update ssl my-health-check
            --proxy-header bad_value
          """)


class HealthChecksUpdateSslBetaTest(HealthChecksUpdateSslTest):

  def SetUp(self):
    self.track = calliope_base.ReleaseTrack.BETA
    self.SelectApi(self.track.prefix)

  def testUriSupport(self):
    # This is the same as testRequestOption, but uses a full URI.
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    request='initial-req', port=80, response='ack'))
        ],
        [],
    ])

    self.Run("""
        compute health-checks update ssl
          https://compute.googleapis.com/compute/v1/projects/my-project/global/healthChecks/my-health-check
          --request req
        """)

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      request='req', port=80, response='ack')),
              project='my-project'))],
    )

  def testRequestOption(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    request='req1', port=80, response='ack'))
        ],
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    request='req2', port=80, response='ack'))
        ],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --request req2
        """)

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      request='req2', port=80, response='ack')),
              project='my-project'))],
    )

    # By default, the resource should not be displayed
    self.assertFalse(self.GetOutput())

  @parameterized.named_parameters(
      ('DisableLogging', '--no-enable-logging', False),
      ('EnableLogging', '--enable-logging', True))
  def testLogConfig(self, enable_logs_flag, enable_logs):

    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    port=80, portName='happy-port'))
        ],
        [],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check {0}""".format(
            enable_logs_flag))

    expected_log_config = self.messages.HealthCheckLogConfig(enable=enable_logs)

    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80, portName='happy-port'),
                  logConfig=expected_log_config),
              project='my-project'))],
    )

  def testEnableToDisableLogConfig(self):
    log_config = self.messages.HealthCheckLogConfig(enable=True)
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    port=80, portName='happy-port'),
                logConfig=log_config)
        ],
        [],
    ])

    self.Run(
        """compute health-checks update ssl my-health-check --no-enable-logging"""
    )

    expected_log_config = self.messages.HealthCheckLogConfig(enable=False)
    self.CheckRequests(
        [(self.compute.healthChecks, 'Get',
          self.messages.ComputeHealthChecksGetRequest(
              healthCheck='my-health-check', project='my-project'))],
        [(self.compute.healthChecks, 'Update',
          self.messages.ComputeHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80, portName='happy-port'),
                  logConfig=expected_log_config),
              project='my-project'))],
    )


class HealthChecksUpdateSslAlphaTest(HealthChecksUpdateSslBetaTest):

  def SetUp(self):
    self.track = calliope_base.ReleaseTrack.ALPHA
    self.SelectApi(self.track.prefix)

  def Run(self, cmd):
    super(HealthChecksUpdateSslAlphaTest, self).Run(cmd + ' --global')


class RegionHealthChecksUpdateSslTest(test_base.BaseTest,
                                      test_case.WithOutputCapture,
                                      parameterized.TestCase):

  def SetUp(self):
    self.track = calliope_base.ReleaseTrack.GA

  def testUriSupport(self):
    # This is the same as testRequestOption, but uses a full URI.
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    request='initial-req', port=80, response='ack'))
        ],
        [],
    ])

    self.Run("""
        compute health-checks update ssl
          https://compute.googleapis.com/compute/alpha/projects/my-project/regions/us-west-1/healthChecks/my-health-check
          --request req
        """)

    self.CheckRequests(
        [(self.compute.regionHealthChecks, 'Get',
          self.messages.ComputeRegionHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project',
              region='us-west-1'))],
        [(self.compute.regionHealthChecks, 'Update',
          self.messages.ComputeRegionHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      request='req', port=80, response='ack')),
              project='my-project',
              region='us-west-1'))],
    )

  def testRequestOption(self):
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    request='req1', port=80, response='ack'))
        ],
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    request='req2', port=80, response='ack'))
        ],
    ])

    self.Run("""
        compute health-checks update ssl my-health-check
          --request req2 --region us-west-1
        """)

    self.CheckRequests(
        [(self.compute.regionHealthChecks, 'Get',
          self.messages.ComputeRegionHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project',
              region='us-west-1'))],
        [(self.compute.regionHealthChecks, 'Update',
          self.messages.ComputeRegionHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      request='req2', port=80, response='ack')),
              project='my-project',
              region='us-west-1'))],
    )

    # By default, the resource should not be displayed
    self.assertFalse(self.GetOutput())


class RegionHealthChecksUpdateSslBetaTest(RegionHealthChecksUpdateSslTest):

  def SetUp(self):
    self.track = calliope_base.ReleaseTrack.BETA
    self.SelectApi(self.track.prefix)

  @parameterized.named_parameters(
      ('DisableLogging', '--no-enable-logging', False),
      ('EnableLogging', '--enable-logging', True))
  def testLogConfig(self, enable_logs_flag, enable_logs):

    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    port=80, portName='happy-port'))
        ],
        [],
    ])

    self.Run("""
    compute health-checks update ssl my-health-check --region us-west-1 {0}"""
             .format(enable_logs_flag))

    expected_log_config = self.messages.HealthCheckLogConfig(enable=enable_logs)

    self.CheckRequests(
        [(self.compute.regionHealthChecks, 'Get',
          self.messages.ComputeRegionHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project',
              region='us-west-1'))],
        [(self.compute.regionHealthChecks, 'Update',
          self.messages.ComputeRegionHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80, portName='happy-port'),
                  logConfig=expected_log_config),
              project='my-project',
              region='us-west-1'))],
    )

  def testEnableToDisableLogConfig(self):
    log_config = self.messages.HealthCheckLogConfig(enable=True)
    self.make_requests.side_effect = iter([
        [
            self.messages.HealthCheck(
                name='my-health-check',
                type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                sslHealthCheck=self.messages.SSLHealthCheck(
                    port=80, portName='happy-port'),
                logConfig=log_config)
        ],
        [],
    ])

    self.Run("""compute health-checks update ssl my-health-check
             --region us-west-1 --no-enable-logging""")

    expected_log_config = self.messages.HealthCheckLogConfig(enable=False)
    self.CheckRequests(
        [(self.compute.regionHealthChecks, 'Get',
          self.messages.ComputeRegionHealthChecksGetRequest(
              healthCheck='my-health-check',
              project='my-project',
              region='us-west-1'))],
        [(self.compute.regionHealthChecks, 'Update',
          self.messages.ComputeRegionHealthChecksUpdateRequest(
              healthCheck='my-health-check',
              healthCheckResource=self.messages.HealthCheck(
                  name='my-health-check',
                  type=self.messages.HealthCheck.TypeValueValuesEnum.SSL,
                  sslHealthCheck=self.messages.SSLHealthCheck(
                      port=80, portName='happy-port'),
                  logConfig=expected_log_config),
              project='my-project',
              region='us-west-1'))],
    )


class RegionHealthChecksUpdateSslAlphaTest(RegionHealthChecksUpdateSslBetaTest):

  def SetUp(self):
    self.track = calliope_base.ReleaseTrack.ALPHA
    self.SelectApi(self.track.prefix)


if __name__ == '__main__':
  test_case.main()
