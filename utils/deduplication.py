"""Deduplication and canonicalization logic for academic journals."""

import re
from typing import Optional, Dict, Any, List
from models.journal import JournalRecord, RepresentativePublication


def normalize_issn(issn_raw: Optional[str]) -> Optional[str]:
    """Normalizes an ISSN string to standard XXXX-XXXX format with uppercase check digit."""
    if not issn_raw:
        return None
    
    # Strip spaces and punctuation except alphanumeric
    cleaned = re.sub(r"[^0-9X-]", "", str(issn_raw).upper())
    digits_only = cleaned.replace("-", "")
    
    if len(digits_only) == 8:
        return f"{digits_only[:4]}-{digits_only[4:]}"
    elif len(digits_only) == 7:
        # Prepend missing leading zero if dropped by integer parsers
        digits_only = "0" + digits_only
        return f"{digits_only[:4]}-{digits_only[4:]}"
    return None


def canonical_title_slug(title: Optional[str]) -> str:
    """Generates a standardized title slug for fallback matching while retaining uniqueness."""
    if not title:
        return ""
    
    lowered = title.lower().strip()
    # Remove leading common articles
    lowered = re.sub(r"^(the\s+|an\s+|a\s+)", "", lowered)
    # Remove subtitles or parenthetical remarks like "(Online)" or "(Print)"
    lowered = re.sub(r"\s*\((online|print|electronic|open access)\)", "", lowered)
    # Remove non-alphanumeric
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    # Collapse multiple whitespaces
    slug = "_".join(cleaned.split())
    return slug


def get_canonical_journal_key(journal: JournalRecord) -> str:
    """Returns the primary unique key for deduplication.
    
    Prefers standardized ISSN (linking, electronic, or print).
    Falls back to canonical title slug only when no ISSN exists.
    """
    for issn in (journal.issn_linking, journal.issn_electronic, journal.issn_print):
        norm = normalize_issn(issn)
        if norm:
            return f"issn:{norm}"
    
    # Fallback slug
    slug = canonical_title_slug(journal.title)
    return f"title:{slug}" if slug else f"id:{journal.journal_id}"


def can_merge_journals(j1: JournalRecord, j2: JournalRecord) -> bool:
    """Checks whether two journal records refer to the exact same publication.
    
    Rule: Never merge distinct journals if both have known ISSNs and their ISSNs do not overlap.
    """
    j1_issns = {
        normalize_issn(x) for x in (j1.issn_linking, j1.issn_electronic, j1.issn_print) if x
    } - {None}
    j2_issns = {
        normalize_issn(x) for x in (j2.issn_linking, j2.issn_electronic, j2.issn_print) if x
    } - {None}

    # If both have ISSN sets and there is an intersection -> same journal
    if j1_issns and j2_issns:
        return len(j1_issns.intersection(j2_issns)) > 0
    
    # If one or both lack ISSNs, compare exact canonical title slugs
    slug1 = canonical_title_slug(j1.title)
    slug2 = canonical_title_slug(j2.title)
    if slug1 and slug2 and slug1 == slug2:
        return True
    
    return False


def merge_journal_records(primary: JournalRecord, secondary: JournalRecord) -> JournalRecord:
    """Merges complementary data from secondary record into primary record without overwriting verified values."""
    # Alternate titles
    for title in [secondary.title] + secondary.alternate_titles:
        if title and title != primary.title and title not in primary.alternate_titles:
            primary.alternate_titles.append(title)
            
    # ISSNs
    if not primary.issn_print and secondary.issn_print:
        primary.issn_print = normalize_issn(secondary.issn_print)
    if not primary.issn_electronic and secondary.issn_electronic:
        primary.issn_electronic = normalize_issn(secondary.issn_electronic)
    if not primary.issn_linking and secondary.issn_linking:
        primary.issn_linking = normalize_issn(secondary.issn_linking)

    # Publisher
    if not primary.publisher and secondary.publisher:
        primary.publisher = secondary.publisher
        
    # Homepage URL
    if not primary.homepage_url and secondary.homepage_url:
        primary.homepage_url = secondary.homepage_url
        
    # Aims & Scope
    if not primary.aims_and_scope and secondary.aims_and_scope:
        primary.aims_and_scope = secondary.aims_and_scope
    elif primary.aims_and_scope and secondary.aims_and_scope:
        # Keep the more detailed one
        if len(secondary.aims_and_scope) > len(primary.aims_and_scope):
            primary.aims_and_scope = secondary.aims_and_scope

    # Subject areas (union)
    primary_subjects_lower = {s.lower() for s in primary.subject_areas}
    for sub in secondary.subject_areas:
        if sub.lower() not in primary_subjects_lower:
            primary.subject_areas.append(sub)
            primary_subjects_lower.add(sub.lower())

    # Open access & fees
    if primary.is_open_access is None and secondary.is_open_access is not None:
        primary.is_open_access = secondary.is_open_access
    if primary.apc_usd is None and secondary.apc_usd is not None:
        primary.apc_usd = secondary.apc_usd
        primary.apc_currency = secondary.apc_currency or "USD"
        primary.apc_source = secondary.apc_source
        
    # Peer review
    if not primary.peer_review_type and secondary.peer_review_type:
        primary.peer_review_type = secondary.peer_review_type
        
    # Frequency
    if not primary.publication_frequency and secondary.publication_frequency:
        primary.publication_frequency = secondary.publication_frequency

    # Metrics
    for k, v in secondary.metrics.items():
        if k not in primary.metrics:
            primary.metrics[k] = v

    # Representative publications (deduplicate by DOI or title)
    existing_dois = {p.doi for p in primary.representative_publications if p.doi}
    existing_titles = {canonical_title_slug(p.title) for p in primary.representative_publications}
    for pub in secondary.representative_publications:
        if pub.doi and pub.doi in existing_dois:
            continue
        if canonical_title_slug(pub.title) in existing_titles:
            continue
        primary.representative_publications.append(pub)

    # Provenance tracking
    for url in secondary.source_urls:
        if url not in primary.source_urls:
            primary.source_urls.append(url)
            
    for k, v in secondary.retrieval_timestamps.items():
        if k not in primary.retrieval_timestamps:
            primary.retrieval_timestamps[k] = v
            
    for src in secondary.sources_contributed:
        if src not in primary.sources_contributed:
            primary.sources_contributed.append(src)

    # Recompute missing fields
    primary.compute_missing_fields()
    return primary
