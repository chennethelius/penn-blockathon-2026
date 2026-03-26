"""Tron blockchain integration via tronpy + TronGrid REST API."""

import os
import httpx
from tronpy import Tron
from tronpy.providers import HTTPProvider

TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY", "")
NETWORK = os.getenv("TRON_NETWORK", "nile")

NETWORK_URLS = {
    "nile": "https://api.nileex.io",
    "shasta": "https://api.shasta.trongrid.io",
    "mainnet": "https://api.trongrid.io",
}

TRONGRID_URLS = {
    "nile": "https://nile.trongrid.io",
    "shasta": "https://api.shasta.trongrid.io",
    "mainnet": "https://api.trongrid.io",
}


def get_tron_client() -> Tron:
    """Get a tronpy client for the configured network."""
    url = NETWORK_URLS.get(NETWORK, NETWORK_URLS["nile"])
    provider = HTTPProvider(url)
    return Tron(provider=provider)


async def get_account_info(address: str) -> dict:
    """Fetch account info from TronGrid REST API."""
    base = TRONGRID_URLS.get(NETWORK, TRONGRID_URLS["nile"])
    headers = {}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{base}/v1/accounts/{address}", headers=headers)
        resp.raise_for_status()
        return resp.json()


async def get_transactions(address: str, limit: int = 50) -> list:
    """Fetch recent transactions for an address."""
    base = TRONGRID_URLS.get(NETWORK, TRONGRID_URLS["nile"])
    headers = {}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base}/v1/accounts/{address}/transactions",
            params={"limit": limit, "order_by": "block_timestamp,desc"},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


async def get_trc20_transfers(address: str, limit: int = 50) -> list:
    """Fetch TRC-20 token transfers for an address."""
    base = TRONGRID_URLS.get(NETWORK, TRONGRID_URLS["nile"])
    headers = {}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base}/v1/accounts/{address}/transactions/trc20",
            params={"limit": limit, "order_by": "block_timestamp,desc"},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


async def get_contract_info(address: str) -> dict:
    """Fetch smart contract info."""
    base = TRONGRID_URLS.get(NETWORK, TRONGRID_URLS["nile"])
    headers = {}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{base}/v1/contracts/{address}", headers=headers)
        resp.raise_for_status()
        return resp.json()
