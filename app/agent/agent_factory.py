"""MAF Agent factory — creates the MITREThreatAnalyzer agent instance."""
import logging

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import search_techniques, get_technique_detail, get_all_tactics, find_mitigations

logger = logging.getLogger(__name__)


def create_agent(settings) -> Agent:
    """Create and return a MAF Agent using Azure OpenAI.

    Auth priority:
    - API key present → use it (works in both dev and prod; key stored as ACA secret)
    - No API key → fall back to Managed Identity / AzureCliCredential
    """
    if settings.azure_openai_api_key:
        # API key available — use it regardless of debug mode.
        # In production the key is injected via the Container App secret "aoai-key".
        chat_client = AzureOpenAIChatClient(
            endpoint=settings.azure_openai_endpoint,
            deployment_name=settings.azure_openai_deployment,
            api_key=settings.azure_openai_api_key,
        )
        logger.info("Agent using Azure OpenAI with API key")
    else:
        # No API key — try Azure credential (Managed Identity in prod, CLI in dev)
        try:
            from azure.identity import DefaultAzureCredential, AzureCliCredential
            credential = AzureCliCredential() if settings.debug else DefaultAzureCredential()
        except ImportError:
            raise RuntimeError(
                "azure-identity is required for MSI authentication. "
                "Install it with: pip install azure-identity"
            )
        chat_client = AzureOpenAIChatClient(
            endpoint=settings.azure_openai_endpoint,
            deployment_name=settings.azure_openai_deployment,
            credential=credential,
        )
        logger.info("Agent using Azure OpenAI with %s", type(credential).__name__)

    agent = Agent(
        chat_client,
        instructions=SYSTEM_PROMPT,
        name="MITREThreatAnalyzer",
        tools=[search_techniques, get_technique_detail, get_all_tactics, find_mitigations],
    )
    logger.info("MAF Agent 'MITREThreatAnalyzer' created with %d tools", 4)
    return agent
