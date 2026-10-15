# Infra

Bicep templates for the Azure Container Apps deployment. See `CLAUDE.md` and
the root `README.md` for the app itself — this covers only the cloud
structure: what exists, and how it's applied.

## Bootstrap (manual, one-time, run by a human — never by a workflow)

Creating an Azure AD App Registration needs directory permissions broader
than "Contributor on one resource group," and GitHub's OIDC exchange needs
that identity to exist and hold a role assignment before any workflow can
authenticate at all. That's chicken-and-egg, so this step is deliberately
imperative `az` CLI, not Bicep, and deliberately not automated.

```zsh
az login

# 1. Resource group -- everything else lives here.
az group create --name rg-debrief-agent-prod --location eastus2

# 2. App Registration + Service Principal for GitHub Actions OIDC.
az ad app create --display-name "sales-call-debrief-agent-cd"
# -> note the returned appId
az ad sp create --id <appId>
# -> note the returned service principal id

# 3. Federated credential, bound to the GitHub *Environment* (not a branch
#    ref) so protection rules (required reviewers, a wait timer) can be added
#    later on the GitHub side with zero Azure-side changes.
cat > federated-credential.json <<'EOF'
{
  "name": "github-production-environment",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:nstonny/sales-call-debrief-agent:environment:production",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF
az ad app federated-credential create --id <appId> --parameters federated-credential.json

# 4. Role assignment, scoped to the resource group only -- not the
#    subscription. Contributor is the pragmatic choice for a demo-sized
#    project whose RG contains only this app's resources; narrow this first
#    if the project grows.
az role assignment create \
  --assignee-object-id <service-principal-id> \
  --assignee-principal-type ServicePrincipal \
  --role "Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/rg-debrief-agent-prod"
```

Then, on the GitHub side (`nstonny/sales-call-debrief-agent` → Settings →
Environments):

- Create an Environment named `production`, deployment branches restricted
  to `main`.
- **Variables**: `AZURE_CLIENT_ID` (the appId above), `AZURE_TENANT_ID`,
  `AZURE_SUBSCRIPTION_ID`.
- **Secrets**: `OPENAI_API_KEY`, `POSTGRES_ADMIN_PASSWORD` (alphanumeric —
  generate with `openssl rand -hex 24` to avoid URL-encoding issues in the
  connection string Bicep builds from it), and optionally
  `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL` /
  `QDRANT_API_KEY`.

## Applying the template

Structural changes (new resource, SKU change, added Container App) go
through `.github/workflows/infra.yml` (`workflow_dispatch` only — never
triggered by a push, since a bad change here can resize/relocate/delete a
database or storage account). Preview first:

```
gh workflow run infra.yml -f whatIf=true
```

Review the diff in the run's logs, then apply for real:

```
gh workflow run infra.yml -f whatIf=false
```

Both run `az deployment group create`/`what-if` against
`infra/main.bicep` using the OIDC identity from bootstrap.

To do the same thing locally instead of through the workflow:

```zsh
az deployment group what-if \
  --resource-group rg-debrief-agent-prod \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json \
  --parameters postgresAdminPassword="$POSTGRES_ADMIN_PASSWORD" openAiApiKey="$OPENAI_API_KEY"

az deployment group create \
  --resource-group rg-debrief-agent-prod \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json \
  --parameters postgresAdminPassword="$POSTGRES_ADMIN_PASSWORD" openAiApiKey="$OPENAI_API_KEY"
```

`api`/`ui`/the jobs come up on a placeholder image
(`mcr.microsoft.com/k8se/quickstart:latest`) on first apply — that's
expected. The `deploy` job in `.github/workflows/ci.yml` points them at the
real image on the next push to `main`.

## Tearing down / redeploying for a demo

```zsh
az group delete --name rg-debrief-agent-prod --yes
```

deletes everything, including Postgres data and the Qdrant collection. It
also deletes the GitHub identity's role assignment, which was scoped to the
group. The App Registration, federated credential and GitHub Environment
secrets/variables survive.

Redeploying is:

1. Re-create the resource group (`infra.yml` deploys *into* it; it doesn't
   create it):
   ```zsh
   az group create --name rg-debrief-agent-prod --location eastus2
   ```
2. Re-create the role assignment (bootstrap step 4). Without it,
   `infra.yml` fails with `AuthorizationFailed`:
   ```zsh
   SP_ID=$(az ad sp show --id <AZURE_CLIENT_ID> --query id -o tsv)
   SUB_ID=$(az account show --query id -o tsv)
   az role assignment create \
     --assignee-object-id "$SP_ID" \
     --assignee-principal-type ServicePrincipal \
     --role "Contributor" \
     --scope "/subscriptions/$SUB_ID/resourceGroups/rg-debrief-agent-prod"
   ```
3. Re-run `infra.yml` (`gh workflow run infra.yml -f whatIf=false`).
4. Re-run (or push to trigger) the `deploy` job — it rebuilds the image,
   re-runs `migrate` against the fresh database, and re-runs `seed` to
   re-embed the knowledge base.

See the root
`README.md`'s deployment section for the full tradeoffs of this cycle
(notably: no Postgres data persists across a teardown, and reseeding
re-spends OpenAI embedding cost).
