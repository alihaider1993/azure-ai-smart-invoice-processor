# Azure App Service Deployment Notes

Recommended startup command:

```bash
python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0
```

Required App Settings:

```text
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
DOC_INTEL_ENDPOINT
COSMOS_ENDPOINT
```

Enable System Assigned Managed Identity on the Azure App Service.

Assign roles:

- Cognitive Services User on Azure AI resources
- Cosmos DB Built-in Data Contributor on Cosmos DB SQL data plane
