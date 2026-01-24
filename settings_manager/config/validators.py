"""
IL-2 Settings Manager - Validators

Validation logic for all editable settings.
"""

import re
from typing import List, Optional, Tuple


class BracketValidator:
    """Validates rank scaling brackets like '1-10', '71+'"""
    
    PATTERN_RANGE = re.compile(r'^(\d+)-(\d+)$')
    PATTERN_PLUS = re.compile(r'^(\d+)\+$')
    PATTERN_EXACT = re.compile(r'^(\d+)$')
    
    @classmethod
    def parse(cls, bracket: str) -> Tuple[int, Optional[int]]:
        """
        Parse bracket string.
        
        Returns:
            (start, end) where end is None for 'N+' format
        
        Raises:
            ValueError if format invalid
        """
        bracket = bracket.strip()
        
        # Try "A-B" format
        match = cls.PATTERN_RANGE.match(bracket)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if start > end:
                raise ValueError(f"Start ({start}) must be <= end ({end})")
            if start < 1:
                raise ValueError("Start must be >= 1")
            return (start, end)
        
        # Try "N+" format
        match = cls.PATTERN_PLUS.match(bracket)
        if match:
            start = int(match.group(1))
            if start < 1:
                raise ValueError("Value must be >= 1")
            return (start, None)
        
        # Try exact number "N" format
        match = cls.PATTERN_EXACT.match(bracket)
        if match:
            val = int(match.group(1))
            if val < 1:
                raise ValueError("Value must be >= 1")
            return (val, val)
        
        raise ValueError("Invalid format. Use 'A-B', 'N+', or 'N'")
    
    @classmethod
    def check_overlap(cls, new_bracket: str, existing_brackets: List[str]) -> Optional[str]:
        """
        Check if new bracket overlaps with existing ones.
        
        Returns:
            Overlapping bracket string, or None if no overlap
        """
        try:
            new_start, new_end = cls.parse(new_bracket)
        except ValueError:
            return None  # Invalid format, separate error
        
        for existing in existing_brackets:
            if existing == new_bracket:
                continue
            
            try:
                ex_start, ex_end = cls.parse(existing)
            except ValueError:
                continue
            
            # Check overlap
            new_end_val = new_end if new_end is not None else float('inf')
            ex_end_val = ex_end if ex_end is not None else float('inf')
            
            # Ranges overlap if: start1 <= end2 AND start2 <= end1
            if new_start <= ex_end_val and ex_start <= new_end_val:
                return existing
        
        return None
    
    @classmethod
    def validate_factor(cls, factor: float, min_val: float = 0.1, max_val: float = 10.0) -> bool:
        """Validate factor is within acceptable range."""
        return min_val <= factor <= max_val


class ScoreValidator:
    """Validates rank score values."""
    
    @classmethod
    def validate_ascending(cls, scores: List[int]) -> Tuple[bool, Optional[int]]:
        """
        Check if scores are monotonically ascending.
        
        Returns:
            (is_valid, first_invalid_index)
        """
        for i in range(1, len(scores)):
            if scores[i] < scores[i-1]:
                return (False, i)
        return (True, None)
    
    @classmethod
    def validate_score(cls, score: int) -> bool:
        """Validate single score value."""
        return isinstance(score, int) and score >= 0


class OffsetValidator:
    """Validates starting_rank_offset values."""
    
    MIN_OFFSET = 0
    MAX_OFFSET = 5  # Per requirement: 0-5
    
    @classmethod
    def validate(cls, offset: int) -> bool:
        """Validate offset is within acceptable range."""
        return isinstance(offset, int) and cls.MIN_OFFSET <= offset <= cls.MAX_OFFSET
    
    @classmethod
    def get_range(cls) -> Tuple[int, int]:
        """Return valid range for offsets."""
        return (cls.MIN_OFFSET, cls.MAX_OFFSET)
