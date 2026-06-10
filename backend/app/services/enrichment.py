"""Provedores de enriquecimento plugáveis.

mock → desenvolvimento. speedio/econodata → produção (preencher API keys no .env).
Modelo de negócio: você compra créditos no provedor e cobra do tenant com margem.
"""
import random
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class EnrichmentProvider(ABC):
    @abstractmethod
    async def enrich(self, lead_data: dict) -> dict:
        """Recebe {name, email, phone, cpf_cnpj, company} → retorna dados enriquecidos."""


class MockProvider(EnrichmentProvider):
    """Simula resposta de provedor real — usar em dev e demo."""

    async def enrich(self, lead_data: dict) -> dict:
        propensao = random.choices(["alta", "media", "baixa"], weights=[3, 5, 2])[0]
        return {
            "telefone_atualizado": "+55 11 9" + str(random.randint(1000, 9999)) + "-" + str(random.randint(1000, 9999)),
            "telefone_ativo": random.random() > 0.16,
            "faturamento_estimado": random.choice(["até 360k", "360k-1M", "1M-5M", "5M-20M"]),
            "funcionarios": random.choice(["1-10", "11-50", "51-200", "200+"]),
            "setor": random.choice(["Serviços", "Comércio", "Indústria", "Tecnologia", "Saúde"]),
            "propensao": propensao,
            "provider": "mock",
        }


class SpeedioProvider(EnrichmentProvider):
    BASE = "https://api-get-leads.speedio.com.br"

    async def enrich(self, lead_data: dict) -> dict:
        # Ajustar conforme contrato real da Speedio quando contratar
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.BASE}/search_companies",
                params={"cnpj": lead_data.get("cpf_cnpj", "")},
                headers={"Authorization": f"Bearer {settings.SPEEDIO_API_KEY}"},
            )
            r.raise_for_status()
            data = r.json()
        data["provider"] = "speedio"
        return data


class EconodataProvider(EnrichmentProvider):
    BASE = "https://api.econodata.com.br"

    async def enrich(self, lead_data: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.BASE}/v1/empresas/{lead_data.get('cpf_cnpj', '')}",
                headers={"X-Api-Key": settings.ECONODATA_API_KEY},
            )
            r.raise_for_status()
            data = r.json()
        data["provider"] = "econodata"
        return data


def get_provider() -> EnrichmentProvider:
    return {
        "speedio": SpeedioProvider,
        "econodata": EconodataProvider,
    }.get(settings.ENRICHMENT_PROVIDER, MockProvider)()
