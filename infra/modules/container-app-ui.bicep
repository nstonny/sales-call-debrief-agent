// Streamlit UI. Confirmed by reading streamlit_app.py: it never imports
// debrief_agent (only os/requests/streamlit), so it needs none of api's
// DATABASE_URL/OPENAI_API_KEY secrets -- just DEBRIEF_API_URL, which it calls
// server-side via `requests`. No CORS config needed for the same reason.
param location string
param environmentId string
param acrLoginServer string
param acrUsername string
@secure()
param acrPassword string
param image string = 'mcr.microsoft.com/k8se/quickstart:latest'
param apiFqdn string

resource ui 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-debrief-ui'
  location: location
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8501
        // See container-app-qdrant.bicep -- none of this app's traffic is
        // gRPC, so pinned to 'http' rather than 'auto' everywhere.
        transport: 'http'
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
      ]
    }
    template: {
      containers: [
        {
          name: 'ui'
          image: image
          command: [
            'streamlit'
            'run'
            'src/ui/streamlit_app.py'
            '--server.address'
            '0.0.0.0'
            '--server.port'
            '8501'
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'DEBRIEF_API_URL', value: 'https://${apiFqdn}/api' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

output fqdn string = ui.properties.configuration.ingress.fqdn
