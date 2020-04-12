"""Generated client library for testing version v1."""
# NOTE: This file is autogenerated and should not be edited by hand.
from apitools.base.py import base_api
from googlecloudsdk.third_party.apis.testing.v1 import testing_v1_messages as messages


class TestingV1(base_api.BaseApiClient):
  """Generated client library for service testing version v1."""

  MESSAGES_MODULE = messages
  BASE_URL = u'https://testing.googleapis.com/'
  MTLS_BASE_URL = u'https://testing.mtls.googleapis.com/'

  _PACKAGE = u'testing'
  _SCOPES = [u'https://www.googleapis.com/auth/cloud-platform', u'https://www.googleapis.com/auth/cloud-platform.read-only']
  _VERSION = u'v1'
  _CLIENT_ID = '1042881264118.apps.googleusercontent.com'
  _CLIENT_SECRET = 'x_Tw5K8nnjoRAqULM9PFAC2b'
  _USER_AGENT = u'google-cloud-sdk'
  _CLIENT_CLASS_NAME = u'TestingV1'
  _URL_VERSION = u'v1'
  _API_KEY = None

  def __init__(self, url='', credentials=None,
               get_credentials=True, http=None, model=None,
               log_request=False, log_response=False,
               credentials_args=None, default_global_params=None,
               additional_http_headers=None, response_encoding=None):
    """Create a new testing handle."""
    url = url or self.BASE_URL
    super(TestingV1, self).__init__(
        url, credentials=credentials,
        get_credentials=get_credentials, http=http, model=model,
        log_request=log_request, log_response=log_response,
        credentials_args=credentials_args,
        default_global_params=default_global_params,
        additional_http_headers=additional_http_headers,
        response_encoding=response_encoding)
    self.applicationDetailService = self.ApplicationDetailServiceService(self)
    self.projects_testMatrices = self.ProjectsTestMatricesService(self)
    self.projects = self.ProjectsService(self)
    self.testEnvironmentCatalog = self.TestEnvironmentCatalogService(self)

  class ApplicationDetailServiceService(base_api.BaseApiService):
    """Service class for the applicationDetailService resource."""

    _NAME = u'applicationDetailService'

    def __init__(self, client):
      super(TestingV1.ApplicationDetailServiceService, self).__init__(client)
      self._upload_configs = {
          }

    def GetApkDetails(self, request, global_params=None):
      r"""Gets the details of an Android application APK.

      Args:
        request: (FileReference) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (GetApkDetailsResponse) The response message.
      """
      config = self.GetMethodConfig('GetApkDetails')
      return self._RunMethod(
          config, request, global_params=global_params)

    GetApkDetails.method_config = lambda: base_api.ApiMethodInfo(
        http_method=u'POST',
        method_id=u'testing.applicationDetailService.getApkDetails',
        ordered_params=[],
        path_params=[],
        query_params=[],
        relative_path=u'v1/applicationDetailService/getApkDetails',
        request_field='<request>',
        request_type_name=u'FileReference',
        response_type_name=u'GetApkDetailsResponse',
        supports_download=False,
    )

  class ProjectsTestMatricesService(base_api.BaseApiService):
    """Service class for the projects_testMatrices resource."""

    _NAME = u'projects_testMatrices'

    def __init__(self, client):
      super(TestingV1.ProjectsTestMatricesService, self).__init__(client)
      self._upload_configs = {
          }

    def Cancel(self, request, global_params=None):
      r"""Cancels unfinished test executions in a test matrix.
This call returns immediately and cancellation proceeds asychronously.
If the matrix is already final, this operation will have no effect.

May return any of the following canonical error codes:

- PERMISSION_DENIED - if the user is not authorized to read project
- INVALID_ARGUMENT - if the request is malformed
- NOT_FOUND - if the Test Matrix does not exist

      Args:
        request: (TestingProjectsTestMatricesCancelRequest) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (CancelTestMatrixResponse) The response message.
      """
      config = self.GetMethodConfig('Cancel')
      return self._RunMethod(
          config, request, global_params=global_params)

    Cancel.method_config = lambda: base_api.ApiMethodInfo(
        http_method=u'POST',
        method_id=u'testing.projects.testMatrices.cancel',
        ordered_params=[u'projectId', u'testMatrixId'],
        path_params=[u'projectId', u'testMatrixId'],
        query_params=[],
        relative_path=u'v1/projects/{projectId}/testMatrices/{testMatrixId}:cancel',
        request_field='',
        request_type_name=u'TestingProjectsTestMatricesCancelRequest',
        response_type_name=u'CancelTestMatrixResponse',
        supports_download=False,
    )

    def Create(self, request, global_params=None):
      r"""Creates and runs a matrix of tests according to the given specifications.
Unsupported environments will be returned in the state UNSUPPORTED.
Matrices are limited to at most 200 supported executions.

May return any of the following canonical error codes:

- PERMISSION_DENIED - if the user is not authorized to write to project
- INVALID_ARGUMENT - if the request is malformed or if the matrix expands
                     to more than 200 supported executions

      Args:
        request: (TestingProjectsTestMatricesCreateRequest) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (TestMatrix) The response message.
      """
      config = self.GetMethodConfig('Create')
      return self._RunMethod(
          config, request, global_params=global_params)

    Create.method_config = lambda: base_api.ApiMethodInfo(
        http_method=u'POST',
        method_id=u'testing.projects.testMatrices.create',
        ordered_params=[u'projectId'],
        path_params=[u'projectId'],
        query_params=[u'requestId'],
        relative_path=u'v1/projects/{projectId}/testMatrices',
        request_field=u'testMatrix',
        request_type_name=u'TestingProjectsTestMatricesCreateRequest',
        response_type_name=u'TestMatrix',
        supports_download=False,
    )

    def Get(self, request, global_params=None):
      r"""Checks the status of a test matrix.

May return any of the following canonical error codes:

- PERMISSION_DENIED - if the user is not authorized to read project
- INVALID_ARGUMENT - if the request is malformed
- NOT_FOUND - if the Test Matrix does not exist

      Args:
        request: (TestingProjectsTestMatricesGetRequest) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (TestMatrix) The response message.
      """
      config = self.GetMethodConfig('Get')
      return self._RunMethod(
          config, request, global_params=global_params)

    Get.method_config = lambda: base_api.ApiMethodInfo(
        http_method=u'GET',
        method_id=u'testing.projects.testMatrices.get',
        ordered_params=[u'projectId', u'testMatrixId'],
        path_params=[u'projectId', u'testMatrixId'],
        query_params=[],
        relative_path=u'v1/projects/{projectId}/testMatrices/{testMatrixId}',
        request_field='',
        request_type_name=u'TestingProjectsTestMatricesGetRequest',
        response_type_name=u'TestMatrix',
        supports_download=False,
    )

  class ProjectsService(base_api.BaseApiService):
    """Service class for the projects resource."""

    _NAME = u'projects'

    def __init__(self, client):
      super(TestingV1.ProjectsService, self).__init__(client)
      self._upload_configs = {
          }

  class TestEnvironmentCatalogService(base_api.BaseApiService):
    """Service class for the testEnvironmentCatalog resource."""

    _NAME = u'testEnvironmentCatalog'

    def __init__(self, client):
      super(TestingV1.TestEnvironmentCatalogService, self).__init__(client)
      self._upload_configs = {
          }

    def Get(self, request, global_params=None):
      r"""Gets the catalog of supported test environments.

May return any of the following canonical error codes:

- INVALID_ARGUMENT - if the request is malformed
- NOT_FOUND - if the environment type does not exist
- INTERNAL - if an internal error occurred

      Args:
        request: (TestingTestEnvironmentCatalogGetRequest) input message
        global_params: (StandardQueryParameters, default: None) global arguments
      Returns:
        (TestEnvironmentCatalog) The response message.
      """
      config = self.GetMethodConfig('Get')
      return self._RunMethod(
          config, request, global_params=global_params)

    Get.method_config = lambda: base_api.ApiMethodInfo(
        http_method=u'GET',
        method_id=u'testing.testEnvironmentCatalog.get',
        ordered_params=[u'environmentType'],
        path_params=[u'environmentType'],
        query_params=[u'projectId'],
        relative_path=u'v1/testEnvironmentCatalog/{environmentType}',
        request_field='',
        request_type_name=u'TestingTestEnvironmentCatalogGetRequest',
        response_type_name=u'TestEnvironmentCatalog',
        supports_download=False,
    )
