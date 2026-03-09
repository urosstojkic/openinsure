// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Azure SQL Server + Database
// Entra-only authentication (no SQL auth). TDE and auditing enabled.
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

@description('Object ID (principal ID) of the Entra admin identity.')
param adminPrincipalId string

@description('Display name of the Entra admin identity.')
param adminPrincipalName string

// ─── Variables ────────────────────────────────────────────────────────────────

var serverName = '${projectName}-${environmentName}-sql-${resourceToken}'
var databaseName = '${projectName}-db'

// ─── SQL Server ───────────────────────────────────────────────────────────────
// Entra-only auth: SQL authentication is disabled entirely.
// The user-assigned managed identity is set as Azure AD administrator.

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: serverName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // Entra-only authentication — no SQL login/password required
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      login: adminPrincipalName
      sid: adminPrincipalId
      tenantId: tenant().tenantId
      principalType: 'Application'
    }
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

// ─── Firewall: Allow Azure Services ───────────────────────────────────────────
// Start/end IP 0.0.0.0 is the Azure-standard way to allow Azure service access.

resource firewallRule 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ─── Database ─────────────────────────────────────────────────────────────────
// Standard S1 tier for dev workloads. TDE is enabled by default on Azure SQL.

resource database 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  tags: tags
  sku: {
    name: 'S1'
    tier: 'Standard'
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 268435456000 // ~250 GB
    catalogCollation: 'SQL_Latin1_General_CP1_CI_AS'
    zoneRedundant: false
    readScale: 'Disabled'
    // Geo-redundant backups for prod; locally redundant for dev
    requestedBackupStorageRedundancy: environmentName == 'prod' ? 'Geo' : 'Local'
  }
}

// ─── Transparent Data Encryption ──────────────────────────────────────────────
// TDE with service-managed key. Customer-managed keys can be configured for prod.

resource tde 'Microsoft.Sql/servers/databases/transparentDataEncryption@2023-08-01-preview' = {
  parent: database
  name: 'current'
  properties: {
    state: 'Enabled'
  }
}

// ─── Auditing ─────────────────────────────────────────────────────────────────
// Server-level auditing routed to Azure Monitor for centralized log analysis.

resource auditing 'Microsoft.Sql/servers/auditingSettings@2023-08-01-preview' = {
  parent: sqlServer
  name: 'default'
  properties: {
    state: 'Enabled'
    isAzureMonitorTargetEnabled: true
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────

output serverId string = sqlServer.id
output serverName string = sqlServer.name
output serverFqdn string = sqlServer.properties.fullyQualifiedDomainName
output databaseName string = database.name
