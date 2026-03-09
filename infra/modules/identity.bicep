// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Managed Identity RBAC Role Assignments
// Least-privilege role assignments for the app's user-assigned managed identity.
//
// NOTE: The user-assigned managed identity resource is created in main.bicep
// to break a dependency cycle — SQL Server needs the MI principal ID for
// Entra-only admin, while this module needs the SQL Server ID for RBAC.
// ──────────────────────────────────────────────────────────────────────────────

@description('Principal ID of the app managed identity.')
param managedIdentityPrincipalId string

@description('Name of the SQL Server for scoped role assignment.')
param sqlServerName string

@description('Name of the Cosmos DB account for scoped role assignment.')
param cosmosAccountName string

@description('Name of the Storage account for scoped role assignment.')
param storageAccountName string

@description('Name of the AI Search service for scoped role assignment.')
param searchServiceName string

@description('Name of the Service Bus namespace for scoped role assignment.')
param serviceBusNamespaceName string

// ─── Built-in Role Definition GUIDs ──────────────────────────────────────────
// Using well-known Azure built-in role GUIDs for least-privilege access.

var roles = {
  sqlDbContributor: '9b7fa17d-e63e-47b0-bb0a-15c516ac86ec'
  cosmosDbAccountReader: 'fbdf93bf-df7d-467e-a4d2-9458aa1360c8'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  serviceBusDataSender: '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'
  serviceBusDataReceiver: '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
}

// ─── Existing Resource References ─────────────────────────────────────────────
// Reference existing resources by name to scope role assignments correctly.

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' existing = {
  name: sqlServerName
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource searchService 'Microsoft.Search/searchServices@2024-03-01-preview' existing = {
  name: searchServiceName
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' existing = {
  name: serviceBusNamespaceName
}

// ─── SQL DB Contributor ───────────────────────────────────────────────────────
// Allows managing SQL databases (schema, data) but not server-level settings.

resource sqlRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sqlServer.id, managedIdentityPrincipalId, roles.sqlDbContributor)
  scope: sqlServer
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.sqlDbContributor)
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Cosmos DB Account Reader ─────────────────────────────────────────────────
// Read-only access to Cosmos DB account metadata. Data access is via Gremlin RBAC.

resource cosmosRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmosAccount.id, managedIdentityPrincipalId, roles.cosmosDbAccountReader)
  scope: cosmosAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cosmosDbAccountReader)
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Storage Blob Data Contributor ────────────────────────────────────────────
// Read, write, and delete blob data in the storage account (documents container).

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, managedIdentityPrincipalId, roles.storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Search Index Data Contributor ────────────────────────────────────────────
// Read and write search index data for the openinsure-knowledge index.

resource searchRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, managedIdentityPrincipalId, roles.searchIndexDataContributor)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Service Bus Data Sender ──────────────────────────────────────────────────
// Send messages to Service Bus queues and topics.

resource serviceBusSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, managedIdentityPrincipalId, roles.serviceBusDataSender)
  scope: serviceBusNamespace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.serviceBusDataSender)
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Service Bus Data Receiver ────────────────────────────────────────────────
// Receive messages from Service Bus queues and subscriptions.

resource serviceBusReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, managedIdentityPrincipalId, roles.serviceBusDataReceiver)
  scope: serviceBusNamespace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.serviceBusDataReceiver)
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}
