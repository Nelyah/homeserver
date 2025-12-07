{ ... }:
{
  services.frp = {
    enable = true;
    role = "client";
    settings = {
      serverAddr = "100.75.232.42"; # tailscale IP
      serverPort = 7000;
      proxies = [
        {
          name = "forward-https";
          type = "tcp";
          localIP = "127.0.0.1";
          localPort = 443;
          remotePort = 443;
          transport.proxyProtocolVersion = "v2";
        }
        {
          name = "forward-http";
          type = "tcp";
          localIP = "127.0.0.1";
          localPort = 80;
          remotePort = 80;
          transport.proxyProtocolVersion = "v2";
        }
      ];
    };
  };
}
