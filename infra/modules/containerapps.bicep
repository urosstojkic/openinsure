// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Container Apps Module
// Deploys the Container Apps environment and backend + dashboard apps.
// ──────────────────────────────────────────────────────────────────────────────

@description('Project name for resource naming.')
param projectName string

@description('Deployment environment.')
param environmentName string

@description('Azure region.')
param location string

@description('Resource tags.')
param tags object

@description('Log Analytics workspace ID for diagnostics.')
param logAnalyticsWorkspaceId string

@description('Subnet ID for the Container Apps environment.')
param containerAppsSubnetId string

@description('ACR login server (e.g. myacr.azurecr.io).')
param acrLoginServer string

@description('User-assigned managed identity resource ID.')
param managedIdentityId string

@description('Application Insights connection string.')
param appInsightsConnectionString string

@description('SQL Server FQDN for backend config.')
param sqlServerFqdn string

@description('SQL database name.')
param sqlDatabaseName string

@description('Cosmos DB endpoint.')
param cosmosEndpoint string

@description('AI Search endpoint.')
param searchEndpoint string

// ─── Container Apps Environment ───────────────────────────────────────────

var envName = '${projectName}-${environmentName}-cae'

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspaceId
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: containerAppsSubnetId
      internal: false
    }
  }
}

// ─── Backend Container App ────────────────────────────────────────────────

resource backendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${projectName}-backend'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
        }
      }
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: '${acrLoginServer}/openinsure-backend:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'OPENINSURE_STORAGE_MODE', value: 'azure' }
            { name: 'OPENINSURE_SQL_SERVER', value: sqlServerFqdn }
            { name: 'OPENINSURE_SQL_DATABASE', value: sqlDatabaseName }
            { name: 'OPENINSURE_COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'OPENINSURE_SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/startup'
                port: 8000
              }
              initialDelaySeconds: 3
              periodSeconds: 5
              failureThreshold: 30
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/ready'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 15
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// ─── Dashboard Container App ──────────────────────────────────────────────

resource dashboardApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${projectName}-dashboard'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'dashboard'
          image: '${acrLoginServer}/openinsure-dashboard:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
}

output backendFqdn string = backendApp.properties.configuration.ingress.fqdn
output dashboardFqdn string = dashboardApp.properties.configuration.ingress.fqdn
output environmentId string = containerAppEnv.id
