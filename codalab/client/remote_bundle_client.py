import contextlib
import sys
import xmlrpclib

from codalab.client.bundle_client import BundleClient
from codalab.common import (
  BUNDLE_RPC_PORT,
  UsageError,
)
from codalab.lib import (
  file_util,
  zip_util,
)
from codalab.server.rpc_file_handle import RPCFileHandle


class RemoteBundleClient(BundleClient):
  CLIENT_COMMANDS = (
    'make',
    'run',
    'update',
    'info',
    'ls',
    #'grep',
    'search',
    #'download',
    'wait',
  )
  COMMANDS = CLIENT_COMMANDS + (
    'open_target',
    'open_temp_file',
    'read_file',
    'close_file',
    'upload_zip',
  )

  def __init__(self):
    address = 'http://localhost:%s/' % (BUNDLE_RPC_PORT,)
    self.proxy = xmlrpclib.ServerProxy(address)
    def do_command(command):
      def inner(*args, **kwargs):
        try:
          return getattr(self.proxy, command)(*args, **kwargs)
        except xmlrpclib.Fault, e:
          # Transform server-side UsageErrors into client-side UsageErrors.
          if 'codalab.common.UsageError' in e.faultString:
            index = e.faultString.find(':')
            raise UsageError(e.faultString[index + 1:])
          else:
            raise
      return inner
    for command in self.COMMANDS:
      setattr(self, command, do_command(command))

  def upload(self, bundle_type, path, metadata):
    zip_path = zip_util.zip_directory(path)
    with open(zip_path, 'rb') as source:
      remote_file_uuid = self.open_temp_file()
      dest = RPCFileHandle(remote_file_uuid, self.proxy)
      with contextlib.closing(dest):
        # FileServer does not expose an API for forcibly flushing writes, so
        # we rely on closing the file to flush it.
        file_util.copy(source, dest, autoflush=False)
    return self.upload_zip(bundle_type, remote_file_uuid, metadata)

  def cat(self, target):
    remote_file_uuid = self.open_target(target)
    source = RPCFileHandle(remote_file_uuid, self.proxy)
    with contextlib.closing(source):
      file_util.copy(source, sys.stdout)
