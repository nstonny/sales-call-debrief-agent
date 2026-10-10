// Shared Container Apps Environment. Every Container App and Job in this
// stack joins it, which is what lets them address each other by internal DNS
// name (<app-name>.internal.<defaultDomain>) the same way Compose's service
// names do today.
param location string
param name string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    // Consumption-only workload profile -- no dedicated-plan baseline charge,
    // matching the demo-project cost bias documented in infra/README.md.
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

output environmentId string = environment.id
output defaultDomain string = environment.properties.defaultDomain
output staticIp string = environment.properties.staticIp
