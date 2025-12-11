storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

api_addr = "https://vault.nelyah.eu"

default_lease_ttl = "168h"
max_lease_ttl = "720h"
ui = true

