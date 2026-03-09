// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Azure AI Search
// Standard tier with managed identity, semantic search, and vector support.
// ──────────────────────────────────────────────────────────────────────────────

@description('Project name used for resource naming.')
param projectName string

@allowed(['dev', 'prod'])
@description('Deployment environment.')
param environmentName string

@description('Azure region for resources.')
param location string

@description('Unique token for globally unique resource names.')
param resourceToken string

@description('Resource tags applied to all resources.')
param tags object

// ─── Variables ────────────────────────────────────────────────────────────────

var searchServiceName = '${projectName}-${environmentName}-search-${resourceToken}'

// ─── Azure AI Search Service ──────────────────────────────────────────────────
// Standard tier provides vector search and semantic ranking capabilities.
// Managed identity enabled for secure access to external data sources.
// NOTE: Search indexes (e.g., openinsure-knowledge) must be created via
//       REST API or SDK at application deployment time, as Bicep does not
//       support index resource definitions.

resource searchService 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: 'standard'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hostingMode: 'default'
    partitionCount: 1
    replicaCount: 1
    publicNetworkAccess: 'enabled'
    // Prefer RBAC auth; fall back to API key with 401 challenge for migration
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    // Semantic search enabled for natural language queries over insurance data
    semanticSearch: 'standard'
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────

output searchServiceId string = searchService.id
output searchServiceName string = searchService.name
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
