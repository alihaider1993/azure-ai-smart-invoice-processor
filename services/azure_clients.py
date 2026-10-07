# Shared Azure clients
# Author: Syed Ali Haider
# One credential and one client per service, reused across agents and pages.
# DefaultAzureCredential resolves to Managed Identity on Azure, a service principal
# (AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET) on Streamlit Cloud,
# or your `az login` session locally — no API keys in code.

import os
from functools import lru_cache

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

DATABASE_NAME = "invoice-db"
OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")


def get_deployment_name() -> str:
    return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")


@lru_cache(maxsize=1)
def get_credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


@lru_cache(maxsize=1)
def get_openai_client() -> AzureOpenAI:
    token_provider = get_bearer_token_provider(
        get_credential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_ad_token_provider=token_provider,
        api_version=OPENAI_API_VERSION,
    )


@lru_cache(maxsize=1)
def get_doc_intel_client() -> DocumentAnalysisClient:
    return DocumentAnalysisClient(
        endpoint=os.getenv("DOC_INTEL_ENDPOINT"),
        credential=get_credential(),
    )


@lru_cache(maxsize=1)
def get_cosmos_client() -> CosmosClient:
    return CosmosClient(url=os.getenv("COSMOS_ENDPOINT"), credential=get_credential())


def get_container(container_name: str):
    database = get_cosmos_client().get_database_client(DATABASE_NAME)
    return database.get_container_client(container_name)
