"""HTTPS transport pinned to a validated public IP, retaining the TLS/HTTP host."""
import http.client,ipaddress,socket,ssl
class PublicHTTPSConnection(http.client.HTTPSConnection):
 def __init__(self,host,address,timeout=6):
  verified=ipaddress.ip_address(address)
  if not verified.is_global:raise ValueError('Non-public destination is blocked.')
  super().__init__(verified.compressed,443,timeout=timeout,context=ssl.create_default_context())
  self.host=host
  self._create_connection=lambda endpoint,timeout=timeout,source_address=None:socket.create_connection((verified.compressed,443),timeout,source_address)
