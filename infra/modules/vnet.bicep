// ──────────────────────────────────────────────────────────────────────────────
// OpenInsure — Virtual Network Module
// Provides private networking for all platform services.
// ──────────────────────────────────────────────────────────────────────────────

@description('Project name for resource naming.')
param projectName string

@description('Deployment environment.')
param environmentName string

@description('Azure region.')
param location string

@description('Resource tags.')
param tags object

var vnetName = '${projectName}-${environmentName}-vnet'

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: ['10.0.0.0/16']
    }
    subnets: [
      {
        name: 'container-apps'
        properties: {
          addressPrefix: '10.0.0.0/21'
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: '10.0.8.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'services'
        properties: {
          addressPrefix: '10.0.9.0/24'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output containerAppsSubnetId string = vnet.properties.subnets[0].id
output privateEndpointsSubnetId string = vnet.properties.subnets[1].id
output servicesSubnetId string = vnet.properties.subnets[2].id
