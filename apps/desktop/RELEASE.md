# MobileShop ERP Desktop Release

## Build

Windows desktop releases are built by GitHub Actions from semantic tags such as `v1.0.0`.

The workflow produces a portable `MobileShopERP-windows-x64.zip` containing `MobileShopERP.exe`.

## Online mode

Configure the target Windows machine with:

- `MOBILE_SHOP_ERP_MODE=online`
- `MOBILE_SHOP_ERP_API_URL=<production API URL>`
- `MOBILE_SHOP_ERP_API_TOKEN=<customer-specific token>`
- `MOBILE_SHOP_ERP_BRANCH_ID=<branch id>`

Do not commit production API tokens or embed shared administrator credentials in the executable.

A GitHub Release packages the desktop application; it does not deploy the backend. The API server and database must already be running and reachable from the customer's network.

The desktop is Online only when the runtime configuration points to a reachable production API and uses valid credentials.

## Release flow

1. Merge tested changes into `main`.
2. Create a semantic tag such as `v1.0.0`.
3. GitHub Actions builds and smoke-checks the Windows executable.
4. The workflow attaches the ZIP to the GitHub Release.
5. Configure the production API URL, customer token, and branch ID on the target machine.
6. Launch `MobileShopERP.exe`.
