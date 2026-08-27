from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential

from config import AZURE_CLIENT_ID


def create_storage_credential():
    """Use the Container App's explicit managed identity in production."""
    if AZURE_CLIENT_ID:
        return ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)
    return DefaultAzureCredential()
