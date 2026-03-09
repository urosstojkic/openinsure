// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Azure Service Bus
// Standard tier namespace with event processing and dead-letter queues.
// Local (SAS) auth disabled — RBAC only.
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

var namespaceName = '${projectName}-${environmentName}-servicebus'

// ─── Service Bus Namespace ────────────────────────────────────────────────────
// Standard tier supports queues, topics, and sessions.
// Local auth disabled — all access via Entra RBAC.

resource namespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    // Disable local (SAS key) auth — enforce Entra RBAC
    disableLocalAuth: true
  }
}

// ─── Events Queue ─────────────────────────────────────────────────────────────
// Primary queue for OpenInsure platform events.
// Dead-lettering on expiration routes failed messages for investigation.

resource eventsQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: namespace
  name: 'openinsure-events'
  properties: {
    maxDeliveryCount: 10
    lockDuration: 'PT1M'
    defaultMessageTimeToLive: 'P14D'
    deadLetteringOnMessageExpiration: true
    enablePartitioning: false
    requiresSession: false
  }
}

// ─── Dead-Letter Queue ────────────────────────────────────────────────────────
// Dedicated queue for failed/poisoned messages requiring manual inspection.
// Longer TTL (30 days) and single delivery attempt for review workflows.

resource deadLetterQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: namespace
  name: 'openinsure-deadletter'
  properties: {
    maxDeliveryCount: 1
    lockDuration: 'PT5M'
    defaultMessageTimeToLive: 'P30D'
    deadLetteringOnMessageExpiration: false
    enablePartitioning: false
    requiresSession: false
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────

output namespaceId string = namespace.id
output namespaceName string = namespace.name
output namespaceFqdn string = '${namespace.name}.servicebus.windows.net'
