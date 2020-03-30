"""Generated client library for iamassist version v1alpha3."""
# NOTE: This file is autogenerated and should not be edited by hand.
from apitools.base.py import base_api
from googlecloudsdk.third_party.apis.iamassist.v1alpha3 import iamassist_v1alpha3_messages as messages


class IamassistV1alpha3(base_api.BaseApiClient):
  """Generated client library for service iamassist version v1alpha3."""

  MESSAGES_MODULE = messages
  BASE_URL = u'https://iamassist.googleapis.com/'
  MTLS_BASE_URL = u'https://iamassist.mtls.googleapis.com/'

  _PACKAGE = u'iamassist'
  _SCOPES = [u'https://www.googleapis.com/auth/cloud-platform']
  _VERSION = u'v1alpha3'
  _CLIENT_ID = '1042881264118.apps.googleusercontent.com'
  _CLIENT_SECRET = 'x_Tw5K8nnjoRAqULM9PFAC2b'
  _USER_AGENT = 'x_Tw5K8nnjoRAqULM9PFAC2b'
  _CLIENT_CLASS_NAME = u'IamassistV1alpha3'
  _URL_VERSION = u'v1alpha3'
  _API_KEY = None

  def __init__(self, url='', credentials=None,
               get_credentials=True, http=None, model=None,
               log_request=False, log_response=False,
               credentials_args=None, default_global_params=None,
               additional_http_headers=None, response_encoding=None):
    """Create a new iamassist handle."""
    url = url or self.BASE_URL
    super(IamassistV1alpha3, self).__init__(
        url, credentials=credentials,
        get_credentials=get_credentials, http=http, model=model,
        log_request=log_request, log_response=log_response,
        credentials_args=credentials_args,
        default_global_params=default_global_params,
        additional_http_headers=additional_http_headers,
        response_encoding=response_encoding)
    self.replays_results = self.ReplaysResultsService(self)
    self.replays = self.ReplaysService(self)

  class ReplaysResultsService(base_api.BaseApiService):
    """Service class for the replays_results resource."""

    _NAME = u'replays_results'

    def __init__(self, client):
      super(IamassistV1alpha3.ReplaysResultsService, self).__init__(client)
      self._upload_configs = {
          }

    def Export(self, request, global_params=None):
      r"""Export the results of the replay to the specified destination.

      Args:
        request: (IamassistReplaysResultsExportRequest) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (GoogleLongrunningOperation) The response message.
      """
      config = self.GetMethodConfig('Export')
      return self._RunMethod(
          config, request, global_params=global_params)

    Export.method_config = lambda: base_api.ApiMethodInfo(
        flat_path=u'v1alpha3/replays/{replaysId}/results:export',
        http_method=u'POST',
        method_id=u'iamassist.replays.results.export',
        ordered_params=[u'parent'],
        path_params=[u'parent'],
        query_params=[],
        relative_path=u'v1alpha3/{+parent}/results:export',
        request_field=u'googleIamAssistV1alpha3ExportReplayResultsRequest',
        request_type_name=u'IamassistReplaysResultsExportRequest',
        response_type_name=u'GoogleLongrunningOperation',
        supports_download=False,
    )

  class ReplaysService(base_api.BaseApiService):
    """Service class for the replays resource."""

    _NAME = u'replays'

    def __init__(self, client):
      super(IamassistV1alpha3.ReplaysService, self).__init__(client)
      self._upload_configs = {
          }

    def Create(self, request, global_params=None):
      r"""Create a replay using the given ReplayConfig.

      Args:
        request: (GoogleIamAssistV1alpha3Replay) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (GoogleLongrunningOperation) The response message.
      """
      config = self.GetMethodConfig('Create')
      return self._RunMethod(
          config, request, global_params=global_params)

    Create.method_config = lambda: base_api.ApiMethodInfo(
        http_method=u'POST',
        method_id=u'iamassist.replays.create',
        ordered_params=[],
        path_params=[],
        query_params=[],
        relative_path=u'v1alpha3/replays',
        request_field='<request>',
        request_type_name=u'GoogleIamAssistV1alpha3Replay',
        response_type_name=u'GoogleLongrunningOperation',
        supports_download=False,
    )

    def Get(self, request, global_params=None):
      r"""Get the specified Replay.

      Args:
        request: (IamassistReplaysGetRequest) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (GoogleIamAssistV1alpha3Replay) The response message.
      """
      config = self.GetMethodConfig('Get')
      return self._RunMethod(
          config, request, global_params=global_params)

    Get.method_config = lambda: base_api.ApiMethodInfo(
        flat_path=u'v1alpha3/replays/{replaysId}',
        http_method=u'GET',
        method_id=u'iamassist.replays.get',
        ordered_params=[u'name'],
        path_params=[u'name'],
        query_params=[],
        relative_path=u'v1alpha3/{+name}',
        request_field='',
        request_type_name=u'IamassistReplaysGetRequest',
        response_type_name=u'GoogleIamAssistV1alpha3Replay',
        supports_download=False,
    )

    def List(self, request, global_params=None):
      r"""List all Replays.

      Args:
        request: (IamassistReplaysListRequest) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (GoogleIamAssistV1alpha3ListReplaysResponse) The response message.
      """
      config = self.GetMethodConfig('List')
      return self._RunMethod(
          config, request, global_params=global_params)

    List.method_config = lambda: base_api.ApiMethodInfo(
        http_method=u'GET',
        method_id=u'iamassist.replays.list',
        ordered_params=[],
        path_params=[],
        query_params=[u'pageSize', u'pageToken'],
        relative_path=u'v1alpha3/replays',
        request_field='',
        request_type_name=u'IamassistReplaysListRequest',
        response_type_name=u'GoogleIamAssistV1alpha3ListReplaysResponse',
        supports_download=False,
    )