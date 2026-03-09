// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure Platform — Root Deployment Template
// Orchestrates all infrastructure modules for the OpenInsure platform.
// Deploys managed identity, monitoring, data stores, messaging, and RBAC.
// ──────────────────────────────────────────────────────────────────────────────

targetScope = 'resourceGroup'

// ─── Parameters ───────────────────────────────────────────────────────────────

@allowed(['dev', 'prod'])
@description('Deployment environment name.')
param environmentName string

@description('Azure region for all resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Project name used as a prefix for resource naming.')
param projectName string = 'openinsure'

// ─── Variables ────────────────────────────────────────────────────────────────

var resourceToken = uniqueString(resourceGroup().id, projectName, environmentName)
var tags = {
  project: projectName
  environment: environmentName
  managedBy: 'bicep'
}

// ─── User-Assigned Managed Identity ───────────────────────────────────────────
// Created here in main.bicep (not in identity.bicep) to break a dependency
// cycle: SQL Server needs the MI principal ID for Entra-only admin at creation
// time, while identity.bicep needs the SQL Server resource ID for RBAC scoping.

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectName}-${environmentName}-identity'
  location: location
  tags: tags
}

// ─── Monitoring ───────────────────────────────────────────────────────────────
// Deployed first — other modules may reference workspace ID for diagnostics.

module monitoring './modules/monitoring.bicep' = {
  name: 'monitoring-deployment'
  params: {
    projectName: projectName
    environmentName: environmentName
    location: location
    tags: tags
  }
}

// ─── Data & Messaging Modules ─────────────────────────────────────────────────
// These modules can deploy in parallel; dependencies are resolved by Bicep.

module storage './modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    projectName: projectName
    environmentName: environmentName
    location: location
    resourceToken: resourceToken
    tags: tags
  }
}

module cosmos './modules/cosmos.bicep' = {
  name: 'cosmos-deployment'
  params: {
    projectName: projectName
    environmentName: environmentName
    location: location
    resourceToken: resourceToken
    tags: tags
  }
}

module sql './modules/sql.bicep' = {
  name: 'sql-deployment'
  params: {
    projectName: projectName
    environmentName: environmentName
    location: location
    resourceToken: resourceToken
    tags: tags
    adminPrincipalId: managedIdentity.properties.principalId
    adminPrincipalName: managedIdentity.name
  }
}

module search './modules/search.bicep' = {
  name: 'search-deployment'
  params: {
    projectName: projectName
    environmentName: environmentName
    location: location
    resourceToken: resourceToken
    tags: tags
  }
}

module servicebus './modules/servicebus.bicep' = {
  name: 'servicebus-deployment'
  params: {
    projectName: projectName
    environmentName: environmentName
    location: location
    tags: tags
  }
}

module eventgrid './modules/eventgrid.bicep' = {
  name: 'eventgrid-deployment'
  params: {
    projectName: projectName
    environmentName: environmentName
    location: location
    tags: tags
  }
}

// ─── RBAC Role Assignments ────────────────────────────────────────────────────
// Deployed after all resource modules so resource IDs are available.
// Grants the managed identity least-privilege access to each service.

module identity './modules/identity.bicep' = {
  name: 'identity-rbac-deployment'
  params: {
    managedIdentityPrincipalId: managedIdentity.properties.principalId
    sqlServerName: sql.outputs.serverName
    cosmosAccountName: cosmos.outputs.accountName
    storageAccountName: storage.outputs.storageAccountName
    searchServiceName: search.outputs.searchServiceName
    serviceBusNamespaceName: servicebus.outputs.namespaceName
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────
// Key resource identifiers and endpoints for application configuration.

output managedIdentityId string = managedIdentity.id
output managedIdentityClientId string = managedIdentity.properties.clientId
output managedIdentityPrincipalId string = managedIdentity.properties.principalId

output sqlServerFqdn string = sql.outputs.serverFqdn
output sqlDatabaseName string = sql.outputs.databaseName

output cosmosAccountEndpoint string = cosmos.outputs.accountEndpoint
output cosmosDatabaseName string = cosmos.outputs.databaseName

output storageAccountName string = storage.outputs.storageAccountName
output storageBlobEndpoint string = storage.outputs.blobEndpoint

output searchServiceName string = search.outputs.searchServiceName
output searchEndpoint string = search.outputs.searchEndpoint

output serviceBusNamespace string = servicebus.outputs.namespaceName
output serviceBusFqdn string = servicebus.outputs.namespaceFqdn

output eventGridTopicEndpoint string = eventgrid.outputs.topicEndpoint

output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
output logAnalyticsWorkspaceId string = monitoring.outputs.workspaceId
