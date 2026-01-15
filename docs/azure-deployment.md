# Azure Container Apps Deployment

This guide covers deploying HaloClaude to Azure Container Apps.

## Prerequisites

- Azure subscription with required resource providers registered (see below)
- One of the following:
  - **Azure Cloud Shell** (recommended, no install needed) - access via portal.azure.com
  - **Azure CLI installed locally** - download from https://aka.ms/installazurecliwindows

### Register Required Resource Providers

Azure subscriptions need resource providers registered before using certain services. Run these commands once per subscription:

```powershell
# Register Container Registry provider
az provider register --namespace Microsoft.ContainerRegistry

# Register Container Apps provider
az provider register --namespace Microsoft.App

# Check registration status (wait until both show "Registered")
az provider show --namespace Microsoft.ContainerRegistry --query "registrationState" -o tsv
az provider show --namespace Microsoft.App --query "registrationState" -o tsv
```

Registration can take 1-2 minutes. Wait until both show `Registered` before proceeding.

### Using Azure Cloud Shell

1. Go to [portal.azure.com](https://portal.azure.com)
2. Click the **Cloud Shell** icon in the top navigation bar (looks like `>_`)
3. If prompted, select **PowerShell** (or Bash, both work)
4. If this is your first time, it will create a storage account - click **Create storage**
5. Once the shell loads, clone the repository:

```powershell
git clone https://github.com/Wldc4rd/HaloClaude.git
cd HaloClaude
```

Now you can run all the commands below from Cloud Shell.

## Quick Deploy

### 1. Create Resource Group

```powershell
az group create --name rg-haloclaude --location westus
```

### 2. Create Container Apps Environment

```powershell
az containerapp env create `
    --name haloclaude-env `
    --resource-group rg-haloclaude `
    --location westus
```

### 3. Build and Push Container Image

You can either use Azure Container Registry (ACR) or Docker Hub.

#### Option A: Azure Container Registry

```powershell
# Create ACR (replace <companyname> with your company name, e.g., haloclauderegistrysoundit)
# Note: ACR names must be lowercase, alphanumeric only (no dashes/underscores), and globally unique
az acr create --name haloclauderegistry<companyname> --resource-group rg-haloclaude --sku Basic

# Login to ACR
az acr login --name haloclauderegistry<companyname>

# Build and push
az acr build --registry haloclauderegistry<companyname> --image haloclaude:latest .
```

#### Option B: Docker Hub

```bash
docker build -t yourusername/haloclaude:latest .
docker push yourusername/haloclaude:latest
```

### 4. Deploy Container App

```powershell
# Replace <companyname> with your company name used in step 3
az containerapp create `
    --name haloclaude-proxy `
    --resource-group rg-haloclaude `
    --environment haloclaude-env `
    --image haloclauderegistry<companyname>.azurecr.io/haloclaude:latest `
    --registry-server haloclauderegistry<companyname>.azurecr.io `
    --target-port 4000 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 1 `
    --env-vars `
        "ANTHROPIC_API_KEY=secretref:anthropic-key" `
        "HALO_API_URL=https://yourinstance.halopsa.com" `
        "HALO_CLIENT_ID=secretref:halo-client-id" `
        "HALO_CLIENT_SECRET=secretref:halo-client-secret" `
        "LITELLM_MASTER_KEY=secretref:master-key"
```

### 5. Configure Secrets

```powershell
az containerapp secret set `
    --name haloclaude-proxy `
    --resource-group rg-haloclaude `
    --secrets `
        anthropic-key=sk-ant-your-key `
        halo-client-id=your-client-id `
        halo-client-secret=your-client-secret `
        master-key=your-proxy-secret
```

### 6. Get Endpoint URL

```powershell
az containerapp show `
    --name haloclaude-proxy `
    --resource-group rg-haloclaude `
    --query properties.configuration.ingress.fqdn `
    -o tsv
```

## Updating the Deployment

### Update Image

```powershell
# Rebuild and push new image (replace <companyname> with your company name)
az acr build --registry haloclauderegistry<companyname> --image haloclaude:latest .

# Update container app
az containerapp update `
    --name haloclaude-proxy `
    --resource-group rg-haloclaude `
    --image haloclauderegistry<companyname>.azurecr.io/haloclaude:latest
```

### Update Environment Variables

```powershell
az containerapp update `
    --name haloclaude-proxy `
    --resource-group rg-haloclaude `
    --set-env-vars "LOG_LEVEL=DEBUG"
```

### View Logs

```powershell
az containerapp logs show `
    --name haloclaude-proxy `
    --resource-group rg-haloclaude `
    --tail 100 `
    --follow
```

## Halo PSA Configuration

Once deployed, configure Halo PSA:

1. Go to **Configuration** → **Integrations** → **AI**
2. Select **Own Azure OpenAI Connection**
3. Configure:
   - **Endpoint**: `https://haloclaude-proxy.xxxxx.azurecontainerapps.io`
   - **API Key**: Your `LITELLM_MASTER_KEY` value
   - **API Version**: `2024-02-01`
   - **Default Azure OpenAI Deployment**: `claude-sonnet-4-5`

## Cost Optimization

Container Apps charges by resource usage:

- **Always-on (min-replicas=1)**: ~$5-15/month for light usage
- **Scale to zero (min-replicas=0)**: Pay only when requests come in, but cold starts may cause timeouts

For production use with Halo, we recommend min-replicas=1 to avoid cold start delays.

## Troubleshooting

### Container Won't Start

Check logs:
```powershell
az containerapp logs show --name haloclaude-proxy --resource-group rg-haloclaude --tail 50
```

### Authentication Errors

Verify secrets are set correctly:
```powershell
az containerapp secret list --name haloclaude-proxy --resource-group rg-haloclaude
```

### Halo Returns Errors

Check the AI logs in Halo: **Configuration** → **Integrations** → **AI** → **Logs**

## Migrating from LiteLLM Proxy

If you're migrating from the LiteLLM-based setup:

1. Deploy the new HaloClaude container alongside the existing one
2. Update Halo to point to the new endpoint
3. Test thoroughly
4. Remove the old LiteLLM container app

The endpoint URL and authentication method remain the same, so Halo configuration changes are minimal.
