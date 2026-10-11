// qdrant/qdrant:latest pulled directly from Docker Hub -- this repo never
// builds it, so it's provisioned here only and never touched by the app CD
// workflow's image-update steps. Internal ingress only: api is the sole
// caller, same as Compose's `qdrant:6333` hostname today.
//
// minReplicas == maxReplicas == 1 is a correctness constraint, not a cost
// lever -- Qdrant's local storage engine is single-writer against the shared
// Azure Files mount, and it must stay warm since every analysis call depends
// on it for retrieval.
param location string
param environmentId string
param environmentStorageName string

resource qdrant 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-debrief-qdrant'
  location: location
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: false
        targetPort: 6333
        // Explicit 'http' (HTTP/1.1), not 'auto': a live seed-job failure
        // showed httpx (the qdrant_client's HTTP backend, no h2 package
        // installed) hanging to ConnectTimeout against this FQDN, while curl
        // -- which offered ALPN h2 -- got an instant 200. None of this app's
        // traffic is gRPC, so pin the protocol rather than let 'auto'
        // negotiate something REST clients don't speak.
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'qdrant'
          image: 'docker.io/qdrant/qdrant:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          volumeMounts: [
            {
              volumeName: 'qdrant-storage'
              mountPath: '/qdrant/storage'
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'qdrant-storage'
          storageType: 'AzureFile'
          storageName: environmentStorageName
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output internalFqdn string = qdrant.properties.configuration.ingress.fqdn
