"""Batterie d'évaluation du SQL Agent — 20 questions, 5 catégories.

Usage :
    cd agents/sql_agent
    python -m scripts.eval_sql

Le script appelle POST http://localhost:8006/query pour chaque question,
capture les métriques clés et affiche un tableau lisible + résumé final.
Entièrement read-only : aucune modification du runtime.
"""

from __future__ import annotations

import sys
import textwrap
import time

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_URL = "http://localhost:8006/query"
TIMEOUT_S = 90.0          # timeout par requête (NL-to-SQL peut prendre 15-20s)
SQL_MAX   = 65            # nb de caractères affichés pour le SQL généré
ANS_MAX   = 85            # nb de caractères affichés pour la réponse

# ---------------------------------------------------------------------------
# Batterie de questions — 20 questions, 5 catégories
# ---------------------------------------------------------------------------

QUESTIONS: list[dict] = [
    # ------------------------------------------------------------------
    # A. Lecture simple (SELECT + WHERE sur une seule table)
    # ------------------------------------------------------------------
    {"cat": "A", "label": "A1", "q": "Quel est le prix du gazoil ?"},
    {"cat": "A", "label": "A2", "q": "Quels clients habitent à Casablanca ?"},
    {"cat": "A", "label": "A3", "q": "Quels produits sont de type gaz ?"},
    {"cat": "A", "label": "A4", "q": "Quelles réclamations sont en cours ?"},
    {"cat": "A", "label": "A5", "q": "Quelles commandes ont le statut livree ?"},

    # ------------------------------------------------------------------
    # B. Agrégation (COUNT, SUM, AVG, GROUP BY)
    # ------------------------------------------------------------------
    {"cat": "B", "label": "B1", "q": "Combien de commandes par statut ?"},
    {"cat": "B", "label": "B2", "q": "Quel est le montant total des commandes livrées ?"},
    {"cat": "B", "label": "B3", "q": "Combien de clients par ville ?"},
    {"cat": "B", "label": "B4", "q": "Quel est le prix moyen des carburants ?"},
    {"cat": "B", "label": "B5", "q": "Combien de réclamations par statut ?"},

    # ------------------------------------------------------------------
    # C. Jointure (JOIN entre 2 tables)
    # ------------------------------------------------------------------
    {"cat": "C", "label": "C1", "q": "Quelles commandes sont en livraison, avec le nom du client ?"},
    {"cat": "C", "label": "C2", "q": "Quelles réclamations ouvertes avec le nom du client ?"},
    {"cat": "C", "label": "C3", "q": "Quelles livraisons sont en cours, avec le nom du livreur ?"},
    {"cat": "C", "label": "C4", "q": "Quel produit a été le plus commandé ?"},
    {"cat": "C", "label": "C5", "q": "Quels clients ont passé au moins une commande confirmée ?"},

    # ------------------------------------------------------------------
    # D. Questions complexes (agrégation + jointure + filtre)
    # ------------------------------------------------------------------
    {"cat": "D", "label": "D1", "q": "Quel client a le plus dépensé en commandes non annulées ?"},
    {"cat": "D", "label": "D2", "q": "Quels clients de Casablanca ont des commandes en attente ?"},
    {"cat": "D", "label": "D3", "q": "Quelle est la répartition des commandes par type de client ?"},

    # ------------------------------------------------------------------
    # E. Cas limites
    # ------------------------------------------------------------------
    {"cat": "E", "label": "E1", "q": "Quel est le code Wi-Fi de la station Afriquia Ain Sbaa ?"},
    {"cat": "E", "label": "E2", "q": "Quels clients habitent à Tombouctou ?"},
]

# ---------------------------------------------------------------------------
# Appel HTTP
# ---------------------------------------------------------------------------

def call_agent(question: str) -> dict:
    """Call POST /query and return a normalized result dict.

    Never raises — on any error returns a dict with status='ERROR'.
    """
    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            resp = client.post(AGENT_URL, json={"query": question})
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return {"_error": f"Timeout ({TIMEOUT_S}s)"}
    except httpx.HTTPStatusError as exc:
        return {"_error": f"HTTP {exc.response.status_code}"}
    except httpx.HTTPError as exc:
        return {"_error": f"Connexion refusée — SQL Agent démarré ? ({exc})"}
    except Exception as exc:
        return {"_error": str(exc)}

    meta     = data.get("metadata") or {}
    db_data  = data.get("data") or {}

    return {
        "strategy":     meta.get("strategy", "—"),
        "retry_used":   meta.get("retry_used", False),
        "confidence":   data.get("confidence", 0.0),
        "rows":         db_data.get("rows_returned", "—"),
        "sql":          (db_data.get("sql") or "").strip().replace("\n", " "),
        "answer":       (data.get("answer") or "").strip().replace("\n", " "),
    }

# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

CAT_LABELS = {
    "A": "A — Lecture simple      (SELECT + WHERE, 1 table)",
    "B": "B — Agrégation          (COUNT, SUM, AVG, GROUP BY)",
    "C": "C — Jointure            (JOIN entre 2 tables)",
    "D": "D — Complexe            (agrégation + jointure + filtre)",
    "E": "E — Cas limites         (hors périmètre, 0 résultat)",
}

# Column widths
W_LABEL  = 4
W_STRAT  = 16
W_RETRY  = 6
W_CONF   = 6
W_ROWS   = 5
W_SQL    = SQL_MAX + 2
W_ANS    = ANS_MAX + 2
W_STATUS = 8

SEPARATOR = (
    f"{'─'*W_LABEL}─{'─'*W_STRAT}─{'─'*W_RETRY}─{'─'*W_CONF}─"
    f"{'─'*W_ROWS}─{'─'*W_SQL}─{'─'*W_ANS}─{'─'*W_STATUS}"
)

HEADER = (
    f"{'#':<{W_LABEL}} {'Strategy':<{W_STRAT}} {'Retry':<{W_RETRY}} "
    f"{'Conf':<{W_CONF}} {'Rows':<{W_ROWS}} "
    f"{'SQL (extrait)':<{W_SQL}} {'Answer (extrait)':<{W_ANS}} {'Status':<{W_STATUS}}"
)


def _trunc(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[:n - 1] + "…"


def _retry_str(val) -> str:
    if val is True:
        return "OUI"
    if val is False:
        return "non"
    return "—"


def print_row(label: str, result: dict) -> None:
    if "_error" in result:
        err = _trunc(result["_error"], W_ANS)
        print(
            f"{label:<{W_LABEL}} {'ERROR':<{W_STRAT}} {'—':<{W_RETRY}} "
            f"{'—':<{W_CONF}} {'—':<{W_ROWS}} "
            f"{'—':<{W_SQL}} {err:<{W_ANS}} {'⚠ ERR':<{W_STATUS}}"
        )
        return

    strategy = _trunc(result["strategy"], W_STRAT)
    retry    = _retry_str(result["retry_used"])
    conf     = f"{result['confidence']:.2f}"
    rows     = str(result["rows"])
    sql      = _trunc(result["sql"], SQL_MAX)
    answer   = _trunc(result["answer"], ANS_MAX)

    print(
        f"{label:<{W_LABEL}} {strategy:<{W_STRAT}} {retry:<{W_RETRY}} "
        f"{conf:<{W_CONF}} {rows:<{W_ROWS}} "
        f"{sql:<{W_SQL}} {answer:<{W_ANS}} {'':>{W_STATUS}}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("=" * 120)
    print("  ÉVALUATION SQL AGENT — 20 QUESTIONS / 5 CATÉGORIES")
    print(f"  URL : {AGENT_URL}   Timeout : {TIMEOUT_S}s")
    print("=" * 120)

    # Vérification rapide de connectivité
    try:
        with httpx.Client(timeout=5.0) as client:
            client.get(AGENT_URL.replace("/query", "/health"))
    except Exception:
        print("\n  ⚠  ATTENTION : SQL Agent semble inaccessible sur", AGENT_URL)
        print("     Lancez d'abord : uvicorn app.main:app --port 8006 --reload\n")
        # Continue anyway — each call will be marked ERROR individually

    # Counters
    counters = {
        "nl_to_sql":   0,
        "fallback":    0,
        "retry_used":  0,
        "unsupported": 0,
        "error":       0,
    }

    results_by_cat: dict[str, list[tuple[str, dict]]] = {}
    for item in QUESTIONS:
        results_by_cat.setdefault(item["cat"], [])

    # Run all questions
    total = len(QUESTIONS)
    for idx, item in enumerate(QUESTIONS, 1):
        label = item["label"]
        q     = item["q"]
        cat   = item["cat"]

        sys.stdout.write(f"\r  [{idx:2d}/{total}] {label} — {q[:60]:<60}")
        sys.stdout.flush()

        t0     = time.perf_counter()
        result = call_agent(q)
        elapsed = time.perf_counter() - t0
        result["_elapsed"] = elapsed

        results_by_cat[cat].append((label, result))

        # Update counters
        if "_error" in result:
            counters["error"] += 1
        else:
            s = result["strategy"]
            if s == "nl_to_sql":
                counters["nl_to_sql"] += 1
            elif s == "unsupported":
                counters["unsupported"] += 1
            else:
                counters["fallback"] += 1
            if result.get("retry_used") is True:
                counters["retry_used"] += 1

    sys.stdout.write("\r" + " " * 80 + "\r")  # clear progress line

    # Print results by category
    for cat, label_text in CAT_LABELS.items():
        rows_in_cat = results_by_cat.get(cat, [])
        if not rows_in_cat:
            continue

        print()
        print(f"  ┌─ {label_text}")
        print(f"  │")
        print(f"  │  {HEADER}")
        print(f"  │  {SEPARATOR}")

        for label, result in rows_in_cat:
            # Find the question text
            q_text = next(i["q"] for i in QUESTIONS if i["label"] == label)
            elapsed = result.get("_elapsed", 0)

            # Print question line
            print(f"  │")
            print(f"  │  Question : {q_text}")
            print(f"  │  Durée    : {elapsed:.1f}s")
            print(f"  │  ", end="")
            print_row(label, result)

        print(f"  │")
        print(f"  └{'─'*116}")

    # Final summary
    print()
    print("=" * 120)
    print("  RÉSUMÉ FINAL")
    print("=" * 120)
    print()

    ok = total - counters["error"]
    print(f"  Questions testées     : {total}")
    print(f"  Réponses obtenues     : {ok}  ({counters['error']} erreur(s) HTTP/timeout)")
    print()
    print(f"  Stratégies utilisées :")
    print(f"    nl_to_sql           : {counters['nl_to_sql']:2d}  (NL-to-SQL réussi)")
    print(f"    fallback keyword    : {counters['fallback']:2d}  (mapping hardcodé utilisé)")
    print(f"    unsupported         : {counters['unsupported']:2d}  (hors périmètre ou échec total)")
    print(f"    error               : {counters['error']:2d}  (agent inaccessible ou exception)")
    print()
    print(f"  Retry SQL déclenché   : {counters['retry_used']:2d}  (correction automatique de SQL)")
    print()

    if ok > 0:
        nl_rate = counters["nl_to_sql"] / ok * 100
        fb_rate = counters["fallback"]  / ok * 100
        un_rate = counters["unsupported"] / ok * 100
        print(f"  Taux nl_to_sql        : {nl_rate:.0f}%")
        print(f"  Taux fallback         : {fb_rate:.0f}%")
        print(f"  Taux unsupported      : {un_rate:.0f}%")
        print()

    print("  Colonne 'Status' à remplir manuellement après vérification des réponses :")
    print("    ✓ correct | ✗ incorrect | ~ partiel | ? à vérifier")
    print()
    print("=" * 120)


if __name__ == "__main__":
    main()
