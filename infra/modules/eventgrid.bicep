// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Azure Event Grid
// Custom topic for platform domain events and system topic for Azure resource
// events. Managed identity enabled for secure event delivery.
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

var topicName = '${projectName}-${environmentName}-events'
var systemTopicName = '${projectName}-${environmentName}-system-events'

// ─── Custom Topic ─────────────────────────────────────────────────────────────
// Platform event bus for OpenInsure domain events (policy changes, claims, etc.).
// Uses CloudEvents v1.0 schema for interoperability.

resource eventGridTopic 'Microsoft.EventGrid/topics@2024-06-01-preview' = {
  name: topicName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    inputSchema: 'CloudEventSchemaV1_0'
    publicNetworkAccess: 'Enabled'
    minimumTlsVersionAllowed: '1.2'
  }
}

// ─── System Topic ─────────────────────────────────────────────────────────────
// Captures Azure resource lifecycle events from the resource group
// (e.g., resource creation, deletion) for audit and automation.

resource systemTopic 'Microsoft.EventGrid/systemTopics@2024-06-01-preview' = {
  name: systemTopicName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    source: resourceGroup().id
    topicType: 'Microsoft.Resources.ResourceGroups'
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────

output topicId string = eventGridTopic.id
output topicName string = eventGridTopic.name
output topicEndpoint string = eventGridTopic.properties.endpoint
output systemTopicId string = systemTopic.id
