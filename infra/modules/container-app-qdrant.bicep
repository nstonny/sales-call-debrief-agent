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
        // Explicit 'http': none of this app's traffic is gRPC, so there's
        // no reason to let 'auto' negotiate a protocol nothing here speaks.
        // (The real fix for an earlier seed-job ConnectTimeout against this
        // FQDN was unrelated to transport -- see core/qdrant.py's port=None:
        // QdrantClient was appending :6333 to the host regardless of what
        // QDRANT_URL said, and 6333 isn't reachable through ACA's ingress.)
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
