"""
Seed reference dataset.

This is a small, hand-curated set of well-documented misinformation
narratives (vaccine/health, election, climate) with genuine variant
wording and a plausible chronological order for each narrative. It
exists so that:

  1. New/empty databases have *something* to compare against and
     cluster, so the evolution graph is never empty on first run.
  2. The similarity graph and timeline are grounded in real structured
     data rather than being decorative placeholders.

None of this is presented to the user as "live news" — it is labeled
in the UI/API responses with origin="reference" and source_name
"Reference dataset".
"""
from datetime import datetime, timezone

SEED_CLAIMS = [
    # --- Cluster: vaccines & fertility ---
    {
        "cluster_id": "cluster-fertility",
        "narrative_label": "Vaccines & Fertility",
        "text": "COVID-19 vaccines cause infertility in women who receive them.",
        "source_name": "Reference dataset",
        "published_at": datetime(2021, 2, 3, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-fertility",
        "narrative_label": "Vaccines & Fertility",
        "text": "Vaccination against COVID-19 negatively affects a woman's fertility and ability to have children.",
        "source_name": "Reference dataset",
        "published_at": datetime(2021, 5, 14, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-fertility",
        "narrative_label": "Vaccines & Fertility",
        "text": "The vaccine spike protein damages the placenta and causes miscarriages in pregnant women.",
        "source_name": "Reference dataset",
        "published_at": datetime(2021, 9, 2, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-fertility",
        "narrative_label": "Vaccines & Fertility",
        "text": "Vaccinated men and women are experiencing reproductive problems that were never disclosed by health officials.",
        "source_name": "Reference dataset",
        "published_at": datetime(2022, 3, 21, tzinfo=timezone.utc),
    },
    # --- Cluster: vaccine safety / danger ---
    {
        "cluster_id": "cluster-safety",
        "narrative_label": "Vaccine Safety Panic",
        "text": "The new vaccine is dangerous and unsafe and was rushed through testing without proper trials.",
        "source_name": "Reference dataset",
        "published_at": datetime(2020, 12, 10, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-safety",
        "narrative_label": "Vaccine Safety Panic",
        "text": "Vaccines are toxic and contain harmful chemicals that damage the immune system permanently.",
        "source_name": "Reference dataset",
        "published_at": datetime(2021, 4, 18, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-safety",
        "narrative_label": "Vaccine Safety Panic",
        "text": "Doctors are hiding the true number of vaccine injuries and deaths from the public.",
        "source_name": "Reference dataset",
        "published_at": datetime(2021, 11, 30, tzinfo=timezone.utc),
    },
    # --- Cluster: election fraud ---
    {
        "cluster_id": "cluster-election",
        "narrative_label": "Election Fraud Claims",
        "text": "Thousands of fraudulent mail-in ballots were counted for the opposing candidate in the election.",
        "source_name": "Reference dataset",
        "published_at": datetime(2020, 11, 5, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-election",
        "narrative_label": "Election Fraud Claims",
        "text": "Voting machines were manipulated to switch votes from one candidate to another during the election.",
        "source_name": "Reference dataset",
        "published_at": datetime(2020, 11, 9, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-election",
        "narrative_label": "Election Fraud Claims",
        "text": "Election officials illegally destroyed ballots to cover up widespread voter fraud.",
        "source_name": "Reference dataset",
        "published_at": datetime(2021, 1, 6, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-election",
        "narrative_label": "Election Fraud Claims",
        "text": "Dead people were registered and voted in the election, proving the results were rigged.",
        "source_name": "Reference dataset",
        "published_at": datetime(2021, 2, 12, tzinfo=timezone.utc),
    },
    # --- Cluster: climate denial ---
    {
        "cluster_id": "cluster-climate",
        "narrative_label": "Climate Change Denial",
        "text": "Global warming is a hoax invented by scientists to secure research funding.",
        "source_name": "Reference dataset",
        "published_at": datetime(2019, 6, 1, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-climate",
        "narrative_label": "Climate Change Denial",
        "text": "Climate change is a natural cycle and human activity has nothing to do with rising temperatures.",
        "source_name": "Reference dataset",
        "published_at": datetime(2020, 3, 15, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-climate",
        "narrative_label": "Climate Change Denial",
        "text": "Scientists are exaggerating sea level rise data to push a climate change agenda.",
        "source_name": "Reference dataset",
        "published_at": datetime(2022, 8, 9, tzinfo=timezone.utc),
    },
    # --- Cluster: general health misinformation ---
    {
        "cluster_id": "cluster-health",
        "narrative_label": "Miracle Cure Claims",
        "text": "A common household remedy can cure cancer but pharmaceutical companies suppress this information.",
        "source_name": "Reference dataset",
        "published_at": datetime(2020, 5, 20, tzinfo=timezone.utc),
    },
    {
        "cluster_id": "cluster-health",
        "narrative_label": "Miracle Cure Claims",
        "text": "Doctors do not want you to know about a natural treatment that cures disease without medicine.",
        "source_name": "Reference dataset",
        "published_at": datetime(2021, 7, 7, tzinfo=timezone.utc),
    },
]
