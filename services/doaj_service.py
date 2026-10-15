"""Directory of Open Access Journals (DOAJ) API integration for OA and APC verification."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import requests
from config.settings import settings
from utils.retry import retry_with_backoff
from utils.caching import cache
from utils.deduplication import normalize_issn

logger = logging.getLogger(__name__)

DOAJ_SEARCH_BASE_URL = "https://doaj.org/api/search/journals"


class DOAJService:
    """Client for querying the DOAJ public API for open access and APC verification."""

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ResearchJournalFinderAI/1.0",
            "Accept": "application/json"
        })

    @retry_with_backoff(retries=3, initial_delay=1.0, max_delay=6.0, exceptions=(requests.RequestException,))
    def _execute_get(self, query: str, page_size: int = 10) -> Dict[str, Any]:
        """Executes GET query against DOAJ search API with caching."""
        url = f"{DOAJ_SEARCH_BASE_URL}/{query}"
        params = {"pageSize": min(page_size, 20)}
        cache_key = cache.hash_key("doaj", {"url": url, "params": params})
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        cache.set(cache_key, data)
        return data

    def search_by_title_or_query(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches DOAJ for journals matching title or topic terms."""
        if not query or not query.strip():
            return []

        clean_query = " ".join(query.strip().split())
        try:
            res = self._execute_get(clean_query, page_size=limit)
            results = res.get("results", [])
            extracted: List[Dict[str, Any]] = []

            for item in results:
                parsed = self._parse_doaj_record(item)
                if parsed:
                    extracted.append(parsed)

            return extracted
        except Exception as e:
            logger.error(f"DOAJ search failed for query '{query}': {e}")
            return []

    def get_journal_by_issn(self, issn: str) -> Optional[Dict[str, Any]]:
        """Verifies journal open access status and fetches official APC fee by ISSN."""
        norm_issn = normalize_issn(issn)
        if not norm_issn:
            return None

        # Query DOAJ by exact ISSN
        query = f'issn:"{norm_issn}"'
        try:
            res = self._execute_get(query, page_size=1)
            results = res.get("results", [])
            if not results:
                # Also try without quotes
                res = self._execute_get(norm_issn, page_size=1)
                results = res.get("results", [])

            if not results:
                return None

            return self._parse_doaj_record(results[0])
        except Exception as e:
            logger.error(f"DOAJ ISSN lookup failed for {issn}: {e}")
            return None

    def _parse_doaj_record(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extracts canonical attributes, APC fees, and peer review details from DOAJ record."""
        bibjson = item.get("bibjson", {})
        title = bibjson.get("title")
        if not title:
            return None

        pissn = normalize_issn(bibjson.get("pissn"))
        eissn = normalize_issn(bibjson.get("eissn"))
        issns = [i for i in (pissn, eissn) if i]

        publisher_data = bibjson.get("publisher", {})
        publisher_name = publisher_data.get("name") if isinstance(publisher_data, dict) else str(publisher_data)

        # APC fees
        apc_info = bibjson.get("apc", {})
        has_apc = apc_info.get("has_apc", False)
        apc_usd: Optional[float] = None
        apc_currency: Optional[str] = None

        if has_apc:
            prices = apc_info.get("max", [])
            if prices and isinstance(prices, list):
                # Look for USD price first, or first given price
                usd_price = next((p for p in prices if p.get("currency") == "USD"), None)
                chosen = usd_price or prices[0]
                try:
                    apc_usd = float(chosen.get("price", 0))
                    apc_currency = chosen.get("currency", "USD")
                    # If not USD, keep as rough estimate or tag currency
                except (ValueError, TypeError):
                    apc_usd = None
        else:
            # Explicitly no APC (Diamond / Platinum OA)
            apc_usd = 0.0
            apc_currency = "USD"

        # Peer review details
        editorial = bibjson.get("editorial", {})
        review_process = editorial.get("review_process", [])
        peer_review_str = ", ".join(review_process) if review_process else "Peer reviewed"

        # Links
        links = bibjson.get("link", [])
        homepage_url = None
        aims_url = None
        for link in links:
            ltype = link.get("type")
            if ltype == "homepage":
                homepage_url = link.get("url")
            elif ltype == "aims_scope":
                aims_url = link.get("url")

        # DOAJ Seal
        has_seal = bibjson.get("seal", False)

        # Subject areas
        subjects = [s.get("term") for s in bibjson.get("subject", []) if s.get("term")]

        # Licenses
        licenses = [lic.get("type") for lic in bibjson.get("license", []) if lic.get("type")]

        return {
            "journal_name": title,
            "issn_print": pissn,
            "issn_electronic": eissn,
            "issns": issns,
            "publisher": publisher_name,
            "homepage_url": homepage_url,
            "aims_url": aims_url,
            "is_open_access": True,  # Listed in DOAJ guarantees OA
            "has_apc": has_apc,
            "apc_usd": apc_usd,
            "apc_currency": apc_currency,
            "has_doaj_seal": has_seal,
            "peer_review_type": peer_review_str,
            "subject_areas": subjects,
            "licenses": licenses,
            "doaj_id": item.get("id"),
            "source_url": f"https://doaj.org/toc/{pissn or eissn}" if (pissn or eissn) else f"https://doaj.org/article/{item.get('id')}",
            "retrieved_at": datetime.now(timezone.utc).isoformat()
        }

    # Alias for compatibility
    check_journal_by_issn = get_journal_by_issn

