"""LLM integration service supporting Gemini, OpenAI, Ollama, and offline fallback synthesis."""

import os
import logging
from typing import Optional, Dict, Any, List
import requests

from config.settings import settings
from models.research import ResearchProfile
from models.journal import JournalRecord, JournalRankingResult

logger = logging.getLogger(__name__)


class LLMService:
    """Provides grounded research summarization and publication advice with offline fallback."""

    def __init__(
        self,
        provider: Optional[str] = None,
        openai_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
        ollama_url: Optional[str] = None
    ):
        self.provider = (provider or settings.llm_provider).lower()
        self.openai_key = openai_key or settings.openai_api_key
        self.gemini_key = gemini_key or settings.gemini_api_key
        self.ollama_url = (ollama_url or settings.ollama_base_url).rstrip("/")
        self.gemini_model = settings.gemini_model
        self.openai_model = settings.openai_model
        self.ollama_model = settings.ollama_model

    def generate_research_summary(self, profile: ResearchProfile) -> str:
        """Produces a grounded executive summary of the research input."""
        if self.provider == "gemini" and self.gemini_key:
            res = self._call_gemini(self._summary_prompt(profile))
            if res:
                return res
        elif self.provider == "openai" and self.openai_key:
            res = self._call_openai(self._summary_prompt(profile))
            if res:
                return res
        elif self.provider == "ollama":
            res = self._call_ollama(self._summary_prompt(profile))
            if res:
                return res

        # Fallback heuristic summary
        return self._heuristic_summary(profile)

    def generate_journal_fit_advice(
        self,
        profile: ResearchProfile,
        ranking_result: JournalRankingResult
    ) -> str:
        """Generates customized submission advice and fit analysis for a ranked journal."""
        prompt = (
            f"Manuscript Title: {profile.title}\n"
            f"Discipline: {profile.domain}\n"
            f"Target Journal: {ranking_result.journal.title}\n"
            f"Publisher: {ranking_result.journal.publisher or 'Unknown'}\n"
            f"Open Access: {'Yes' if ranking_result.journal.is_open_access else 'No/Hybrid'}\n"
            f"APC Fee: ${ranking_result.journal.apc_usd:,.0f} USD\n" if ranking_result.journal.apc_usd is not None else "APC Fee: Not specified\n"
            f"Verification: {ranking_result.verification_status.value}\n"
            "Provide 2-3 concise bullet points advising the author on why this journal is appropriate, "
            "what aspects of the manuscript to highlight in their cover letter, and any submission considerations."
        )

        if self.provider == "gemini" and self.gemini_key:
            res = self._call_gemini(prompt)
            if res:
                return res
        elif self.provider == "openai" and self.openai_key:
            res = self._call_openai(prompt)
            if res:
                return res
        elif self.provider == "ollama":
            res = self._call_ollama(prompt)
            if res:
                return res

        # Grounded heuristic fallback
        return self._heuristic_journal_advice(profile, ranking_result)

    def _summary_prompt(self, profile: ResearchProfile) -> str:
        return (
            f"Analyze and synthesize this research paper into a crisp 3-sentence executive summary:\n"
            f"Title: {profile.title}\n"
            f"Domain: {profile.domain}\n"
            f"Abstract: {profile.abstract}\n"
            f"Keywords: {', '.join(profile.keywords)}"
        )

    def _call_gemini(self, prompt: str) -> Optional[str]:
        """Calls Google Gemini API via REST endpoint."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400}
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=15.0)
            if r.status_code == 200:
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            logger.warning(f"Gemini API returned status {r.status_code}: {r.text}")
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
        return None

    def _call_openai(self, prompt: str) -> Optional[str]:
        """Calls OpenAI Chat Completion API."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": "You are an expert academic publishing advisor."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 400
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=15.0)
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()
            logger.warning(f"OpenAI API returned status {r.status_code}: {r.text}")
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
        return None

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Calls local Ollama generate endpoint."""
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        try:
            r = requests.post(url, json=payload, timeout=20.0)
            if r.status_code == 200:
                return r.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama local call failed: {e}")
        return None

    def _heuristic_summary(self, profile: ResearchProfile) -> str:
        """Rule-based executive summary without external API dependency."""
        words = profile.abstract.split()
        first_sentence = profile.abstract.split(".")[0] if "." in profile.abstract else profile.abstract[:150]
        kw_str = ", ".join(profile.keywords[:4]) if profile.keywords else "core scientific principles"
        
        return (
            f"This paper explores **{profile.title}** within the domain of **{profile.domain}**. "
            f"The study primarily focuses on {first_sentence.lower().strip()}. "
            f"Key conceptual themes include {kw_str}."
        )

    def _heuristic_journal_advice(
        self,
        profile: ResearchProfile,
        result: JournalRankingResult
    ) -> str:
        """Generates grounded advice based on ranking metrics and verification."""
        j = result.journal
        advice = []

        advice.append(
            f"• **Scope Alignment**: Your work aligns strongly ({result.semantic_similarity * 100:.0f}% semantic similarity) with {j.title}'s published portfolio."
        )

        if j.is_open_access:
            if j.apc_usd == 0.0:
                advice.append("• **Fee Advantage**: Verified Diamond Open Access—no article processing charges required for authors.")
            elif j.apc_usd:
                advice.append(f"• **Publication Cost**: Budget ${j.apc_usd:,.0f} USD for open access processing.")

        if result.mismatch_warnings:
            advice.append(f"• **Consideration**: Note that {result.mismatch_warnings[0]}")
        else:
            advice.append("• **Cover Letter**: Highlight your novel contributions in relation to the journal's focus on " + (", ".join(j.subject_areas[:2]) if j.subject_areas else profile.domain) + ".")

        return "\n".join(advice)
