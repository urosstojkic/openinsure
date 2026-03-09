// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Cosmos DB with NoSQL API
// Document database for the insurance knowledge graph.
// Key-based access disabled; Entra RBAC only.
// Uses NoSQL API with JSON documents to model graph relationships.
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
var containerName = 'insurance-graph'

// ─── Cosmos DB Account ────────────────────────────────────────────────────────
// NoSQL API (default). Key-based auth disabled (disableLocalAuth).
// Session consistency balances performance and read-your-writes.
// Serverless capacity for dev to minimize cost.

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
    capabilities: environmentName == 'dev' ? [
      { name: 'EnableServerless' }
    ] : []
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

// ─── NoSQL Database ───────────────────────────────────────────────────────────

resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// ─── Knowledge Graph Container ────────────────────────────────────────────────
// Partition key /entityType enables scalable queries across entity types.
// Stores vertices and edges as JSON documents.

resource graphContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: sqlDatabase
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: ['/entityType']
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
output databaseName string = sqlDatabase.name
