"""Crossref REST API integration for journal discovery and metadata verification."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import requests
from config.settings import settings
from utils.retry import retry_with_backoff
from utils.caching import cache
from utils.deduplication import normalize_issn

logger = logging.getLogger(__name__)

CROSSREF_BASE_URL = "https://api.crossref.org"


class CrossrefService:
    """Client for the Crossref REST API polite pool."""

    def __init__(self, email: Optional[str] = None, timeout: float = 12.0):
        self.email = email or settings.crossref_email
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"ResearchJournalFinderAI/1.0 (mailto:{self.email})",
            "Accept": "application/json"
        })

    @retry_with_backoff(retries=3, initial_delay=1.0, max_delay=6.0, exceptions=(requests.RequestException,))
    def _execute_get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes GET request against Crossref API with caching and polite headers."""
        params_dict = dict(params or {})
        if self.email and "mailto" not in params_dict:
            params_dict["mailto"] = self.email

        url = f"{CROSSREF_BASE_URL}/{endpoint.lstrip('/')}"
        cache_key = cache.hash_key("crossref", {"url": url, "params": params_dict})
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        response = self.session.get(url, params=params_dict, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        cache.set(cache_key, data)
        return data

    def search_journals(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches Crossref for journals matching title or topic keywords."""
        if not query or not query.strip():
            return []

        clean_query = " ".join(query.strip().split())
        params = {
            "query": clean_query,
            "rows": min(limit, 20)
        }

        try:
            res = self._execute_get("journals", params)
            message = res.get("message", {})
            items = message.get("items", [])
            journals: List[Dict[str, Any]] = []
            retrieval_time = datetime.now(timezone.utc).isoformat()

            for item in items:
                title = item.get("title")
                if not title:
                    continue

                issns = [normalize_issn(i) for i in item.get("ISSN", []) if normalize_issn(i)]
                issn_l = normalize_issn(item.get("issn-l")) or (issns[0] if issns else None)

                # Publisher name
                publisher = item.get("publisher")

                # Subjects / categories
                subjects = item.get("subjects", [])

                journals.append({
                    "journal_name": title,
                    "issn_l": issn_l,
                    "issns": issns,
                    "publisher": publisher,
                    "subject_areas": [s.get("name") if isinstance(s, dict) else str(s) for s in subjects],
                    "total_dois": item.get("counts", {}).get("total-dois", 0),
                    "source_url": f"https://api.crossref.org/journals/{issn_l}" if issn_l else None,
                    "retrieved_at": retrieval_time
                })

            return journals

        except requests.exceptions.RequestException as e:
            logger.error(f"Crossref journal search failed for query '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in Crossref search_journals: {e}")
            return []

    def get_journal_by_issn(self, issn: str) -> Optional[Dict[str, Any]]:
        """Retrieves authoritative journal metadata by ISSN from Crossref."""
        norm_issn = normalize_issn(issn)
        if not norm_issn:
            return None

        try:
            res = self._execute_get(f"journals/{norm_issn}")
            item = res.get("message", {})
            if not item:
                return None

            issns = [normalize_issn(i) for i in item.get("ISSN", []) if normalize_issn(i)]
            issn_l = normalize_issn(item.get("issn-l")) or norm_issn
            subjects = item.get("subjects", [])

            return {
                "journal_name": item.get("title"),
                "issn_l": issn_l,
                "issns": issns,
                "publisher": item.get("publisher"),
                "subject_areas": [s.get("name") if isinstance(s, dict) else str(s) for s in subjects],
                "total_dois": item.get("counts", {}).get("total-dois", 0),
                "source_url": f"https://api.crossref.org/journals/{norm_issn}",
                "retrieved_at": datetime.now(timezone.utc).isoformat()
            }
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            logger.error(f"Crossref lookup failed for ISSN {issn}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Crossref get_journal_by_issn for {issn}: {e}")
            return None

    def search_works_by_query(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches Crossref works to extract publishing venues."""
        if not query or not query.strip():
            return []

        clean_query = " ".join(query.strip().split())
        params = {
            "query": clean_query,
            "rows": min(limit, 20),
            "filter": "type:journal-article",
            "sort": "relevance",
            "order": "desc"
        }

        try:
            res = self._execute_get("works", params)
            message = res.get("message", {})
            items = message.get("items", [])
            extracted_works: List[Dict[str, Any]] = []
            retrieval_time = datetime.now(timezone.utc).isoformat()

            for item in items:
                container_titles = item.get("container-title", [])
                if not container_titles or not container_titles[0]:
                    continue
                venue_name = container_titles[0]

                issns = [normalize_issn(i) for i in item.get("ISSN", []) if normalize_issn(i)]
                issn_l = normalize_issn(item.get("issn-l")) or (issns[0] if issns else None)

                # Year
                published_parts = item.get("published", {}).get("date-parts", [[None]])[0]
                pub_year = published_parts[0] if published_parts and len(published_parts) > 0 else None

                extracted_works.append({
                    "work_title": item.get("title", ["Untitled"])[0] if item.get("title") else "Untitled",
                    "doi": item.get("DOI"),
                    "publication_year": pub_year,
                    "venue_name": venue_name,
                    "venue_issn_l": issn_l,
                    "venue_issns": issns,
                    "venue_publisher": item.get("publisher"),
                    "source_url": f"https://doi.org/{item.get('DOI')}" if item.get("DOI") else None,
                    "retrieved_at": retrieval_time
                })

            return extracted_works
        except Exception as e:
            logger.error(f"Crossref search_works_by_query failed for '{query}': {e}")
            return []
