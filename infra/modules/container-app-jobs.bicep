// One-shot `migrate`/`seed` steps map to Container Apps Jobs, not long-running
// apps -- they run to a defined completion and exit, mirroring Compose's
// `migrate`/`seed` one-shot services. Both are manually triggered (the app CD
// workflow starts an execution explicitly and polls it); `core/config.py`
// raises at import on a missing DATABASE_URL *or* OPENAI_API_KEY regardless
// of which one the job's own command actually needs, so both env vars are
// supplied to both jobs.
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

var registryConfig = {
  server: acrLoginServer
  username: acrUsername
  passwordSecretRef: 'acr-password'
}

var sharedSecrets = [
  { name: 'acr-password', value: acrPassword }
  { name: 'database-url', value: databaseUrl }
  { name: 'openai-api-key', value: openAiApiKey }
  { name: 'qdrant-api-key', value: qdrantApiKey }
]

var sharedEnv = [
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
  { name: 'QDRANT_URL', value: qdrantUrl }
  { name: 'QDRANT_COLLECTION_NAME', value: qdrantCollectionName }
  { name: 'QDRANT_API_KEY', secretRef: 'qdrant-api-key' }
]

resource migrateJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'caj-debrief-migrate'
  location: location
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 120
      replicaRetryLimit: 1
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [registryConfig]
      secrets: sharedSecrets
    }
    template: {
      containers: [
        {
          name: 'migrate'
          image: image
          command: ['alembic', 'upgrade', 'head']
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: sharedEnv
        }
      ]
    }
  }
}

resource seedJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'caj-debrief-seed'
  location: location
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 1
      manualTriggerConfig: {
        // Must stay 1 -- seed_all's idempotency check reads the collection
        // then decides whether to embed; concurrent executions could both
        // pass the check before either commits, double-embedding.
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [registryConfig]
      secrets: sharedSecrets
    }
    template: {
      containers: [
        {
          name: 'seed'
          image: image
          command: ['python', '-m', 'debrief_agent.rag.ingestion.seed_all']
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: sharedEnv
        }
      ]
    }
  }
}

output migrateJobName string = migrateJob.name
output seedJobName string = seedJob.name
