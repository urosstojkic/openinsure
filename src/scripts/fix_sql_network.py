"""Fix Azure SQL networking — enable access from Container Apps."""

import subprocess


def run(cmd):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(r.stdout[:100] if r.returncode == 0 else f"ERROR: {r.stderr[:200]}")
    return r.returncode == 0


run(
    "az sql server update --name openinsure-dev-sql-knshtzbusr734 --resource-group openinsure-dev-sc --set publicNetworkAccess=Enabled"
)
run(
    "az sql server firewall-rule create --server openinsure-dev-sql-knshtzbusr734 --resource-group openinsure-dev-sc --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0"
)
run("az containerapp update --name openinsure-backend --resource-group openinsure-dev-sc --revision-suffix v35-net")
