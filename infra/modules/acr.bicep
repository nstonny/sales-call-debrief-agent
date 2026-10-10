// Basic SKU is ample for one sha-tagged image pushed on every deploy. Admin
// credentials (rather than a user-assigned managed identity + AcrPull role)
// keep the registry-auth wiring on each Container App a single secretRef --
// the pragmatic choice for a demo-sized project; a managed identity is the
// documented upgrade path if this grows beyond one app's registry.
param location string
param name string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

output loginServer string = registry.properties.loginServer
output adminUsername string = registry.listCredentials().username
// Consumed directly as a Container App registry secret by main.bicep.
#disable-next-line outputs-should-not-contain-secrets
output adminPassword string = registry.listCredentials().passwords[0].value
