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
"""A simple command to test the CommandBase processing.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from googlecloudsdk.calliope import base as calliope_base
from googlecloudsdk.core import log


class SubCommand(calliope_base.Command):
  """subcommand short help.

  subcommand long help.
  """

  @staticmethod
  def Args(parser):
    parser.add_argument('--flag', type=int, help='Auxilio aliis.')

  def Run(self, args):
    if 'newstyle' not in self.context or self.context['newstyle'] != 'working':
      raise Exception('not working')
    return args.flag-1

  def Display(self, args, result):
    log.Print(args, result)
