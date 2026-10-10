// FastAPI/uvicorn service. Provisioned on a placeholder image -- this module
// owns structure and secret shape only; the app CD workflow (`deploy` job in
// ci.yml) owns which image tag actually runs, via `az containerapp update
// --image`, which leaves this secret/env wiring untouched.
//
// minReplicas=1 (not scale-to-zero): this is demoed from a remote host, so a
// cold start on someone's first click is explicitly not an acceptable
// tradeoff for the small always-on cost of one consumption replica.
param location string
param environmentId string
param acrLoginServer string
param acrUsername string
@secure()
param acrPassword string
param image string = 'mcr.microsoft.com/k8se/quickstart:latest'
@secure()
param databaseUrl string
@secure()
param openAiApiKey string
param qdrantUrl string
param qdrantCollectionName string = 'sales_knowledge_chunks'
@secure()
param qdrantApiKey string = ''
param langfusePublicKey string = ''
@secure()
param langfuseSecretKey string = ''
param langfuseBaseUrl string = ''

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-debrief-api'
  location: location
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        { name: 'acr-password', value: acrPassword }
        { name: 'database-url', value: databaseUrl }
        { name: 'openai-api-key', value: openAiApiKey }
        { name: 'qdrant-api-key', value: qdrantApiKey }
        { name: 'langfuse-secret-key', value: langfuseSecretKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: image
          command: [
            'uvicorn'
            'debrief_agent.app.main:app'
            '--host'
            '0.0.0.0'
            '--port'
            '8000'
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
            { name: 'QDRANT_URL', value: qdrantUrl }
            { name: 'QDRANT_COLLECTION_NAME', value: qdrantCollectionName }
            { name: 'QDRANT_API_KEY', secretRef: 'qdrant-api-key' }
            { name: 'LANGFUSE_PUBLIC_KEY', value: langfusePublicKey }
            { name: 'LANGFUSE_SECRET_KEY', secretRef: 'langfuse-secret-key' }
            { name: 'LANGFUSE_BASE_URL', value: langfuseBaseUrl }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output fqdn string = api.properties.configuration.ingress.fqdn
