"""Score preditivo do lead — versão heurística v1.

Calculado na entrada e recalculado a cada evento relevante.
Quando houver volume de dados, substituir por modelo treinado (scikit-learn).
"""
from app.models.lead import Lead
from app.models.tracking import TrackSession


def compute_score(lead: Lead, sessions: list[TrackSession] | None = None) -> float:
    score = 20.0  # base

    # Completude de dados
    if lead.email:
        score += 10
    if lead.phone:
        score += 10
    if lead.company:
        score += 8
    if lead.cpf_cnpj:
        score += 7

    # Canal de origem
    source_weight = {
        "meta_ads": 8, "google_ads": 10, "website": 12,
        "import": 3, "manual": 5, "tiktok": 6,
    }
    score += source_weight.get(lead.source, 5)

    # Enriquecimento concluído = dado confiável
    if lead.enrichment_status == "done":
        score += 10

    # Comportamento no site (o "tempo de namoro")
    if sessions:
        n = len(sessions)
        total_time = sum(s.duration_seconds or 0 for s in sessions)
        total_pages = sum(s.pages_count or 0 for s in sessions)
        score += min(n * 3, 12)              # recorrência
        score += min(total_time / 120, 10)   # tempo total (cap 10)
        score += min(total_pages * 1.5, 8)   # profundidade
        # acesso desktop em horário comercial = perfil B2B
        if any(s.device_type == "desktop" for s in sessions):
            score += 3

    return round(min(score, 100.0), 1)


def propensity_from_score(score: float) -> str:
    if score >= 70:
        return "alta"
    if score >= 40:
        return "media"
    return "baixa"


def refresh_lead_score(db, lead: Lead) -> None:
    sessions = (
        db.query(TrackSession).filter(TrackSession.lead_id == lead.id).all()
        if lead.id else []
    )
    lead.score = compute_score(lead, sessions)
    lead.propensity = propensity_from_score(lead.score)
