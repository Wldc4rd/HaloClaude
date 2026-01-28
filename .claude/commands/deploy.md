Deploy HaloClaude to Azure Container Apps.

Steps:
1. Build the Docker image in Azure Container Registry:
   ```
   bash /c/Users/CharlieCoutts/.azure/az-wrapper.sh acr build --registry haloclauderegistrysoundit --image haloclaude-proxy:latest --file Dockerfile . --no-logs
   ```
   The `--no-logs` flag is required to avoid a Unicode encoding error in the Azure CLI log streamer.

2. Determine the next revision suffix by checking the current latest revision name from Azure, then incrementing the number (e.g. mcp07 → mcp08).

3. Update the container app with a new revision:
   ```
   bash /c/Users/CharlieCoutts/.azure/az-wrapper.sh containerapp update --name haloclaude-proxy --resource-group rg-haloclaude --image haloclauderegistrysoundit.azurecr.io/haloclaude-proxy:latest --revision-suffix <next-suffix>
   ```

4. Confirm the deployment succeeded by checking that `provisioningState` is `Succeeded` and `latestRevisionName` matches the new suffix.

IMPORTANT: Always use `bash /c/Users/CharlieCoutts/.azure/az-wrapper.sh` instead of `az` directly, because Todyl SASE requires a custom CA bundle for SSL.
