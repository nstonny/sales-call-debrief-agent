// Root template, deployed into the already-bootstrapped resource group (see
// infra/README.md -- the RG itself, the GitHub OIDC App Registration, and its
// role assignment are created manually, once, before this ever runs).
//
// This template owns structure and secret *shape* only. `api`/`ui`/the jobs
// are provisioned on a placeholder image; the app CD workflow (`deploy` job
// in .github/workflows/ci.yml) owns which image tag is actually running, via
// `az containerapp update --image`, which never touches this template.
targetScope = 'resourceGroup'

param location string = 'eastus2'

param acrName string = 'acrdebriefagent'
param logAnalyticsName string = 'log-debrief-agent-prod'
param environmentName string = 'cae-debrief-agent-prod'
param postgresServerName string = 'psql-debrief-agent-prod'
param postgresAdminLogin string = 'debriefadmin'
param storageAccountName string = 'stdebriefqdrantprod'
param qdrantCollectionName string = 'sales_knowledge_chunks'

@secure()
param postgresAdminPassword string

@secure()
param openAiApiKey string

@secure()
param qdrantApiKey string = ''

param langfusePublicKey string = ''

@secure()
param langfuseSecretKey string = ''

param langfuseBaseUrl string = ''

// Placeholder until the first `deploy` job run -- see module comments.
param apiImage string = 'mcr.microsoft.com/k8se/quickstart:latest'
param uiImage string = 'mcr.microsoft.com/k8se/quickstart:latest'
param jobsImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'log-analytics'
  params: {
    location: location
    name: logAnalyticsName
  }
}

module environment 'modules/container-apps-environment.bicep' = {
  name: 'container-apps-environment'
  params: {
    location: location
    name: environmentName
    logAnalyticsCustomerId: logAnalytics.outputs.customerId
    logAnalyticsSharedKey: logAnalytics.outputs.sharedKey
  }
}

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    name: acrName
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    location: location
    serverName: postgresServerName
    administratorLogin: postgresAdminLogin
    administratorPassword: postgresAdminPassword
  }
}

module qdrantStorage 'modules/storage-qdrant.bicep' = {
  name: 'qdrant-storage'
  params: {
    location: location
    storageAccountName: storageAccountName
    environmentName: environmentName
  }
  dependsOn: [
    environment
  ]
}

module qdrantApp 'modules/container-app-qdrant.bicep' = {
  name: 'qdrant-app'
  params: {
    location: location
    environmentId: environment.outputs.environmentId
    environmentStorageName: qdrantStorage.outputs.environmentStorageName
  }
}

// ACA internal ingress always terminates TLS at the environment's ingress
// proxy on the standard port, regardless of the container's targetPort --
// callers use https://<internal-fqdn> with no port suffix, same as external
// ingress. Qdrant's REST client never sees TLS itself; ACA forwards decrypted
// traffic to the container's port 6333 internally.
var qdrantUrl = 'https://${qdrantApp.outputs.internalFqdn}'
var databaseUrl = 'postgresql+asyncpg://${postgresAdminLogin}:${postgresAdminPassword}@${postgres.outputs.fqdn}:5432/${postgres.outputs.databaseName}?ssl=true'

module api 'modules/container-app-api.bicep' = {
  name: 'api-app'
  params: {
    location: location
    environmentId: environment.outputs.environmentId
    acrLoginServer: acr.outputs.loginServer
    acrUsername: acr.outputs.adminUsername
    acrPassword: acr.outputs.adminPassword
    image: apiImage
    databaseUrl: databaseUrl
    openAiApiKey: openAiApiKey
    qdrantUrl: qdrantUrl
    qdrantCollectionName: qdrantCollectionName
    qdrantApiKey: qdrantApiKey
    langfusePublicKey: langfusePublicKey
    langfuseSecretKey: langfuseSecretKey
    langfuseBaseUrl: langfuseBaseUrl
  }
}

module ui 'modules/container-app-ui.bicep' = {
  name: 'ui-app'
  params: {
    location: location
    environmentId: environment.outputs.environmentId
    acrLoginServer: acr.outputs.loginServer
    acrUsername: acr.outputs.adminUsername
    acrPassword: acr.outputs.adminPassword
    image: uiImage
    apiFqdn: api.outputs.fqdn
  }
}

module jobs 'modules/container-app-jobs.bicep' = {
  name: 'jobs'
  params: {
    location: location
    environmentId: environment.outputs.environmentId
    acrLoginServer: acr.outputs.loginServer
    acrUsername: acr.outputs.adminUsername
    acrPassword: acr.outputs.adminPassword
    image: jobsImage
    databaseUrl: databaseUrl
    openAiApiKey: openAiApiKey
    qdrantUrl: qdrantUrl
    qdrantCollectionName: qdrantCollectionName
    qdrantApiKey: qdrantApiKey
  }
}

output acrLoginServer string = acr.outputs.loginServer
output apiFqdn string = api.outputs.fqdn
output uiFqdn string = ui.outputs.fqdn
output migrateJobName string = jobs.outputs.migrateJobName
output seedJobName string = jobs.outputs.seedJobName
