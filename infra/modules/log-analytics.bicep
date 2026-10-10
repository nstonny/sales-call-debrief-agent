// Log Analytics workspace backing the Container Apps Environment. Container
// Apps requires one for its platform logs; a 30-day retention keeps this cheap
// for a demo project with no long-term log-analysis need.
param location string
param name string

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: name
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

output customerId string = workspace.properties.customerId
// Consumed directly as a @secure() param by the container-apps-environment module.
#disable-next-line outputs-should-not-contain-secrets
output sharedKey string = workspace.listKeys().primarySharedKey
