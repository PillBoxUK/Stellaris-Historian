"""Safe game-text publishing: do not display broken substitution tokens as prose."""
from __future__ import annotations
import re


def clean_game_description(description: str | None, empire_name: str = '') -> str:
    if not description:return ''
    text=' '.join(str(description).split())
    text=re.sub(r'§[A-Za-z0-9!]|£[A-Za-z_]+£?', '', text)
    # A missing scripted object can leave a superficially printable yet
    # nonsensical sentence ('on have', 'on, Researchers'). Do not replace an
    # unknown target with a guessed world or publish such fragments.
    if re.search(r'\b(?:on|at|from|in|of|near|around|within)\s+(?:have|has|will|was|were|are|is|should|must|could|can|may|might)\b|\b(?:on|at|from|in|of|near|around|within)\s*[,\.]',text,re.I):
        return ''
    # Reject sentences that only make sense with a missing scripted location.
    text=re.sub(r'\b(?:on|at|from|in|of|around|within|near|across|to)\s*\.', '.', text, flags=re.I)
    text=re.sub(r'\s+([,;.!?])',r'\1', text)
    text=re.sub(r'\.{2,}', '.',text)
    # Never publish raw unfilled game variables or player instructions.
    if re.search(r'\$[^ $]+\$|\[[^]]+\]|\{[^}]+\}',text):return ''
    # A fragile line of dialogue that addresses the player is not historical narration.
    if re.search(r'\b(?:click|select an option|press the button|you have chosen)\b',text,re.I):return ''
    text=re.sub(r'\bOur (scientists|researchers|crews|explorers)\b',r'The \1',text,flags=re.I)
    text=re.sub(r'\bOur (sensors|scans)\b',r'The \1',text,flags=re.I)
    text=re.sub(r'\bWe have detected\b','Investigators detected',text,flags=re.I)
    text=re.sub(r'\bWe have discovered\b','Explorers discovered',text,flags=re.I)
    text=re.sub(r'\bWe are confident\b','Researchers believed',text,flags=re.I)
    text=re.sub(r'\bWe need to\b','The authorities sought to',text,flags=re.I)
    text=re.sub(r'\bOur are our\b','The combined',text,flags=re.I)
    text=re.sub(r'\b(we|our|us|you|your)\b', '', text, flags=re.I) if re.search(r'\b(?:we|our|us|you|your)\b',text,re.I) else text
    text=' '.join(text.split()).strip()
    if len(text)<24 or text.startswith('.') or '  ' in text:return ''
    return text.rstrip('.')+'.'
