// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Azure Blob Storage
// StorageV2 with Entra-only auth (shared key disabled), soft delete,
// and blob versioning for document protection.
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
// Storage account names: 3–24 chars, lowercase alphanumeric only.

var storageAccountName = toLower('${projectName}${environmentName}${take(resourceToken, 8)}')

// ─── Storage Account ──────────────────────────────────────────────────────────
// Shared key access disabled — all access via Entra ID RBAC.
// Public blob access disabled for security.

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    // Disable shared key access — Entra-only authentication
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// ─── Blob Services ────────────────────────────────────────────────────────────
// Soft delete (7 days) and versioning protect against accidental data loss.

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    isVersioningEnabled: true
  }
}

// ─── Blob Container: documents ────────────────────────────────────────────────

resource documentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: 'documents'
  properties: {
    publicAccess: 'None'
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────

output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
