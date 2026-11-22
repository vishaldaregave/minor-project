"""efsa_database.py — High performance EFSA OpenFoodTox retrieval engine.

Provides fast substance lookups, ADI limit queries, and scientific safety context
from the EFSA OpenFoodTox dataset of 3,175+ substances.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from backend.app.services.food_safety.e_number_map import normalise_e_number

logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = CURRENT_DIR / "data" / "efsa_food_substances.json"
FALLBACK_DATA_PATH = Path("D:/Development/Minor Projezt/LabelLens/data/efsa_food_substances.json")


class EFSADatabase:
    """In-memory indexed database of EFSA food substances and additives."""

    _instance: Optional["EFSADatabase"] = None

    def __init__(self, data_path: Optional[Path] = None) -> None:
        self.data_path = data_path or (DEFAULT_DATA_PATH if DEFAULT_DATA_PATH.exists() else FALLBACK_DATA_PATH)
        self.substances: List[Dict[str, Any]] = []
        self._name_index: Dict[str, Dict[str, Any]] = {}
        self._token_index: Dict[str, List[int]] = {}
        self._is_loaded = False
        self._load()

    @classmethod
    def get_instance(cls) -> "EFSADatabase":
        """Singleton accessor for EFSA database."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self) -> None:
        """Load and index EFSA substances from JSON."""
        if not self.data_path.exists():
            logger.warning("EFSA food substances file not found at %s", self.data_path)
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                self.substances = json.load(f)

            for idx, item in enumerate(self.substances):
                name = item.get("name", "").strip().lower()
                if name:
                    self._name_index[name] = item

                # Index tokens for keyword search
                tokens = set(re.findall(r"[a-z0-9]{3,}", name))
                cat = item.get("category", "").lower()
                tokens.update(re.findall(r"[a-z0-9]{3,}", cat))

                for token in tokens:
                    if token not in self._token_index:
                        self._token_index[token] = []
                    self._token_index[token].append(idx)

            self._is_loaded = True
            logger.info("Loaded %d EFSA substances from %s", len(self.substances), self.data_path)
        except Exception as exc:
            logger.error("Failed to load EFSA substances database: %s", exc)

    def search_substance(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search EFSA substances by name, E-number, or keywords."""
        if not self._is_loaded or not query:
            return []

        cleaned = query.strip()
        lowered = cleaned.lower()

        # Check for E-number normalization first
        e_match = normalise_e_number(cleaned)
        if e_match:
            canonical_name = e_match["name"].lower()
            if canonical_name in self._name_index:
                sub = self._name_index[canonical_name].copy()
                sub["matched_e_number"] = e_match["e_number"]
                return [sub]

        # Direct name match
        if lowered in self._name_index:
            return [self._name_index[lowered]]

        # Token-based search
        query_tokens = re.findall(r"[a-z0-9]{3,}", lowered)
        if not query_tokens:
            return []

        score_map: Dict[int, int] = {}
        for token in query_tokens:
            indices = self._token_index.get(token, [])
            for idx in indices:
                score_map[idx] = score_map.get(idx, 0) + 1

        sorted_indices = sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)
        results: List[Dict[str, Any]] = []
        for idx, score in sorted_indices[:limit]:
            results.append(self.substances[idx])

        return results

    def get_safety_context_for_ingredients(self, ingredients: List[str], max_chunks: int = 8) -> str:
        """Produce formatted EFSA context text for an ingredient list to inject into LLM prompts."""
        found_chunks: List[str] = []
        seen_names = set()

        for ing in ingredients:
            hits = self.search_substance(ing, limit=1)
            for hit in hits:
                name = hit.get("name", "")
                if name in seen_names:
                    continue
                seen_names.add(name)

                rag_doc = hit.get("rag_document") or ""
                adi_str = ""
                if hit.get("adi_lower") is not None:
                    adi_str = f"ADI: {hit.get('adi_lower')} {hit.get('adi_unit', '')}".strip()

                chunk = f"Substance: {name}\nCategory: {hit.get('category', '')}\n{adi_str}\n{rag_doc[:350]}"
                found_chunks.append(chunk.strip())

                if len(found_chunks) >= max_chunks:
                    break
            if len(found_chunks) >= max_chunks:
                break

        if not found_chunks:
            return "No specific EFSA substance records matched."
        return "\n\n".join(found_chunks)
