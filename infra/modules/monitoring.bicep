// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Azure Monitor + Application Insights
// Centralized observability: Log Analytics workspace, Application Insights,
// and a reusable diagnostic settings pattern.
// ──────────────────────────────────────────────────────────────────────────────

@description('Project name used for resource naming.')
param projectName string

@allowed(['dev', 'prod'])
@description('Deployment environment.')
param environmentName string

@description('Azure region for resources.')
param location string

@description('Resource tags applied to all resources.')
param tags object

// ─── Variables ────────────────────────────────────────────────────────────────

var workspaceName = '${projectName}-${environmentName}-logs'
var appInsightsName = '${projectName}-${environmentName}-insights'

// ─── Log Analytics Workspace ──────────────────────────────────────────────────
// Central log sink for all Azure resources. 30-day retention for dev;
// increase for prod via parameter or policy override.

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: environmentName == 'prod' ? 90 : 30
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ─── Application Insights ─────────────────────────────────────────────────────
// Workspace-based Application Insights for application telemetry.
// Connected to Log Analytics for unified querying via KQL.

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    RetentionInDays: environmentName == 'prod' ? 90 : 30
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────
// These outputs are consumed by other modules and application configuration.

output workspaceId string = logAnalyticsWorkspace.id
output workspaceName string = logAnalyticsWorkspace.name
output appInsightsId string = appInsights.id
output appInsightsName string = appInsights.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
