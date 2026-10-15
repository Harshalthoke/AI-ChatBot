"""OpenAlex scholarly works and sources API integration."""

import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import requests
from config.settings import settings
from utils.retry import retry_with_backoff
from utils.caching import cache
from utils.deduplication import normalize_issn, canonical_title_slug

logger = logging.getLogger(__name__)

OPENALEX_BASE_URL = "https://api.openalex.org"


class OpenAlexService:
    """Client for OpenAlex API covering scholarly works and publication venues."""

    def __init__(self, email: Optional[str] = None, timeout: float = 12.0):
        self.email = email or settings.openalex_email
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"ResearchJournalFinderAI/1.0 (mailto:{self.email})"
        })

    @retry_with_backoff(retries=3, initial_delay=1.0, max_delay=6.0, exceptions=(requests.RequestException,))
    def _execute_get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes GET request with polite parameters, caching, and error handling."""
        params_with_mail = dict(params)
        if self.email and "mailto" not in params_with_mail:
            params_with_mail["mailto"] = self.email

        url = f"{OPENALEX_BASE_URL}/{endpoint.lstrip('/')}"
        cache_key = cache.hash_key("openalex", {"url": url, "params": params_with_mail})
        cached_val = cache.get(cache_key)
        if cached_val is not None:
            return cached_val

        response = self.session.get(url, params=params_with_mail, timeout=self.timeout)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 2))
            logger.warning(f"OpenAlex rate limit (429). Backing off for {retry_after}s.")
            time.sleep(retry_after)
            response = self.session.get(url, params=params_with_mail, timeout=self.timeout)

        response.raise_for_status()
        data = response.json()
        cache.set(cache_key, data)
        return data

    def search_works(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Searches works matching query and extracts publication venues (journals) and paper metadata."""
        if not query or not query.strip():
            return []

        clean_query = " ".join(query.strip().split())
        params = {
            "search": clean_query,
            "per_page": min(limit, 25),
            "filter": "type:article"
        }

        try:
            res = self._execute_get("works", params)
            results = res.get("results", [])
            extracted_works: List[Dict[str, Any]] = []
            retrieval_time = datetime.now(timezone.utc).isoformat()

            for item in results:
                primary_loc = item.get("primary_location") or {}
                source = primary_loc.get("source") or {}
                
                # We only want academic journals or conferences
                source_type = source.get("type")
                venue_name = source.get("display_name")
                if not venue_name:
                    continue

                extracted_works.append({
                    "work_title": item.get("title") or "Untitled",
                    "doi": item.get("doi"),
                    "publication_year": item.get("publication_year"),
                    "cited_by_count": item.get("cited_by_count", 0),
                    "venue_name": venue_name,
                    "venue_id": source.get("id"),
                    "venue_issn_l": normalize_issn(source.get("issn_l")),
                    "venue_issns": [normalize_issn(i) for i in source.get("issn", []) if normalize_issn(i)],
                    "venue_publisher": source.get("host_organization_name"),
                    "is_oa": source.get("is_oa"),
                    "apc_usd": source.get("apc_usd"),
                    "source_url": item.get("id"),
                    "retrieved_at": retrieval_time,
                })
            return extracted_works

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAlex works search failed for query '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in OpenAlex search_works: {e}")
            return []

    def search_sources(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Directly searches OpenAlex sources (journals) by title or topic."""
        if not query or not query.strip():
            return []

        clean_query = " ".join(query.strip().split())
        params = {
            "search": clean_query,
            "per_page": min(limit, 20),
            "filter": "type:journal"
        }

        try:
            res = self._execute_get("sources", params)
            results = res.get("results", [])
            extracted_sources: List[Dict[str, Any]] = []
            retrieval_time = datetime.now(timezone.utc).isoformat()

            for item in results:
                display_name = item.get("display_name")
                if not display_name:
                    continue

                issn_l = normalize_issn(item.get("issn_l"))
                issns = [normalize_issn(i) for i in item.get("issn", []) if normalize_issn(i)]
                
                # Concepts/subjects
                concepts = [c.get("display_name") for c in item.get("x_concepts", []) if c.get("display_name")]
                
                summary_stats = item.get("summary_stats", {})
                
                extracted_sources.append({
                    "journal_name": display_name,
                    "alternate_titles": item.get("alternate_titles", []),
                    "issn_l": issn_l,
                    "issns": issns,
                    "publisher": item.get("host_organization_name"),
                    "homepage_url": item.get("homepage_url"),
                    "is_oa": item.get("is_oa"),
                    "apc_usd": item.get("apc_usd"),
                    "apc_prices": item.get("apc_prices"),
                    "subject_areas": concepts[:6],
                    "metrics": {
                        "2yr_mean_citedness": summary_stats.get("2yr_mean_citedness"),
                        "h_index": summary_stats.get("h_index"),
                        "works_count": item.get("works_count"),
                        "source": "OpenAlex"
                    },
                    "source_id": item.get("id"),
                    "source_url": item.get("id"),
                    "retrieved_at": retrieval_time,
                })
            return extracted_sources

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAlex sources search failed for query '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in OpenAlex search_sources: {e}")
            return []

    def get_source_by_issn(self, issn: str) -> Optional[Dict[str, Any]]:
        """Retrieves authoritative source details by ISSN from OpenAlex."""
        norm_issn = normalize_issn(issn)
        if not norm_issn:
            return None

        params = {"filter": f"issn:{norm_issn}"}
        try:
            res = self._execute_get("sources", params)
            results = res.get("results", [])
            if not results:
                return None
            
            item = results[0]
            summary_stats = item.get("summary_stats", {})
            return {
                "journal_name": item.get("display_name"),
                "issn_l": normalize_issn(item.get("issn_l")),
                "issns": [normalize_issn(i) for i in item.get("issn", []) if normalize_issn(i)],
                "publisher": item.get("host_organization_name"),
                "homepage_url": item.get("homepage_url"),
                "is_oa": item.get("is_oa"),
                "apc_usd": item.get("apc_usd"),
                "subject_areas": [c.get("display_name") for c in item.get("x_concepts", []) if c.get("display_name")][:6],
                "metrics": {
                    "2yr_mean_citedness": summary_stats.get("2yr_mean_citedness"),
                    "h_index": summary_stats.get("h_index"),
                    "source": "OpenAlex"
                },
                "source_url": item.get("id"),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to lookup ISSN {issn} on OpenAlex: {e}")
            return None
