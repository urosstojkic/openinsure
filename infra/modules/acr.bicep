// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Azure Container Registry Module
// Private ACR for backend and dashboard container images.
// ──────────────────────────────────────────────────────────────────────────────

@description('Project name for resource naming.')
param projectName string

@description('Deployment environment.')
param environmentName string

@description('Azure region.')
param location string

@description('Unique token for globally unique names.')
param resourceToken string

@description('Resource tags.')
param tags object

var acrName = '${projectName}${environmentName}acr${take(resourceToken, 6)}'

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output acrId string = acr.id
