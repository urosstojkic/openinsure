// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Cosmos DB with Gremlin API
// Graph database for the insurance knowledge graph.
// Key-based access disabled; Entra RBAC only.
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

var accountName = '${projectName}-${environmentName}-cosmos-${resourceToken}'
var databaseName = 'openinsure-knowledge'
var graphName = 'insurance-graph'

// ─── Cosmos DB Account ────────────────────────────────────────────────────────
// Gremlin API enabled via capability. Key-based auth disabled (disableLocalAuth).
// Session consistency balances performance and read-your-writes for graph queries.

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    // Gremlin API capability
    capabilities: [
      { name: 'EnableGremlin' }
    ]
    // Disable key-based auth — Entra RBAC only
    disableLocalAuth: true
    // Single region for dev; add geo-replication entries for prod
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    enableMultipleWriteLocations: false
    enableAutomaticFailover: environmentName == 'prod'
    publicNetworkAccess: 'Enabled'
    minimalTlsVersion: 'Tls12'
  }
}

// ─── Gremlin Database ─────────────────────────────────────────────────────────

resource gremlinDatabase 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// ─── Graph Container ──────────────────────────────────────────────────────────
// Partition key /partitionKey enables scalable graph traversal across partitions.

resource graphContainer 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases/graphs@2024-05-15' = {
  parent: gremlinDatabase
  name: graphName
  properties: {
    resource: {
      id: graphName
      partitionKey: {
        paths: ['/partitionKey']
        kind: 'Hash'
      }
      indexingPolicy: {
        automatic: true
        indexingMode: 'consistent'
      }
    }
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────

output accountId string = cosmosAccount.id
output accountName string = cosmosAccount.name
output accountEndpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = gremlinDatabase.name
