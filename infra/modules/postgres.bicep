// Azure Database for PostgreSQL Flexible Server, replacing Compose's `db`
// service. Compose's postgres:17-alpine dev creds are intentionally not
// reused -- README already flags those as dev-only, not deployable.
param location string
param serverName string
param administratorLogin string
@secure()
param administratorPassword string
param databaseName string = 'debrief_db'

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: serverName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '17'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: databaseName
}

// Container Apps' consumption workload profile has no static/predictable
// egress IP range to allowlist individually, so this is the flexible-server
// equivalent of Compose's open-by-default container network: allow traffic
// from any Azure-internal service. Tightening this to a VNet-integrated
// Container Apps Environment + private endpoint is the documented upgrade
// path if this moves beyond a demo.
resource allowAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: server
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output fqdn string = server.properties.fullyQualifiedDomainName
output databaseName string = database.name
