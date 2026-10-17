"""Native, evidence-limited civilisation prologue for the Imperial Annals.

Only the opening *player* country and its founding species are used. Lore is
optional and describes the scripted origin, not events proven to have happened.
Never apply a current species/civic profile retrospectively.
"""
from __future__ import annotations

from pathlib import Path
import re
from .save_reader import (_find_named_block, _find_numeric_child, _quoted_value,
                          read_save_texts, empire_profile_from_text)
from .localisation import resolve_origin_lore, resolve_localisation_key

_CLASS = {'HUM':'humanoid', 'MAM':'mammalian', 'REP':'reptilian', 'AVI':'avian',
         'ART':'arthropoid', 'MOL':'molluscoid', 'FUN':'fungoid', 'PLANT':'plantoid',
         'LITHOID':'lithoid', 'LITH':'lithoid', 'NECROID':'necroid', 'NEC':'necroid',
         'AQUATIC':'aquatic', 'AQU':'aquatic', 'TOX':'toxoid', 'MACHINE':'synthetic',
         'ROBOT':'synthetic'}
_TRAIT = {'adaptive':'adaptability to varied environments', 'nomadic':'a tendency towards migration',
          'wasteful':'resource-intensive living habits', 'intelligent':'intellectual aptitude',
          'ingenious':'ingenuity', 'strong':'physical strength', 'very_strong':'exceptional physical strength',
          'rapid_breeders':'rapid population growth', 'slow_breeders':'slower population growth',
          'traditional':'respect for established traditions', 'natural_engineers':'engineering talent',
          'natural_physicists':'expertise in physics', 'natural_sociologists':'expertise in societal research',
          'resilient':'resilience', 'enduring':'longevity', 'long_lived':'long lifespans',
          'repurposed_hardware':'repurposed components', 'mass_produced':'mass production',
          'durable':'durability', 'logic_engines':'advanced logic processing',
          'emotion_emulators':'emulated emotional responses'}


def _human(key: str | None) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'^(?:origin|civic|ethic|auth|gov|trait)_', '', str(key or '')).replace('_',' ')).strip()


def _name(block: str | None, source: Path, prefix: str = '') -> str:
    if not block:
        return ''
    direct = _quoted_value(block, 'name')
    if direct:
        return direct
    key = _quoted_value(_find_named_block(block, 'name') or block, 'key')
    if key:
        local = resolve_localisation_key(source, key)
        if local and local != key and not re.search(r'\$|\[|§', local):
            return local
        if key.startswith('NAME_'):
            return _human(key[5:])
        if key == 'PRESCRIPTED_species_name_humans2':
            return 'Human'
        if key.startswith('SPEC_'):
            return _human(key.removeprefix('SPEC_'))
        if re.fullmatch(r'[A-Za-z][A-Za-z -]+',key):
            return key
    return ''


def extract_founding_profile(start_save: Path, source_save: Path | None = None) -> dict:
    """Read ONE opening save, not hundreds of gamestates. No DB mutation."""
    source_save = source_save or start_save
    meta, text = read_save_texts(start_save)
    profile = empire_profile_from_text(meta, text)
    countries = _find_named_block(text, 'country')
    country = _find_numeric_child(countries or '', profile.player_country_id) if profile.player_country_id is not None else None
    species_id_match = re.search(r'(?m)^\s*founder_species_ref\s*=\s*(\d+)', country or '')
    species_id = int(species_id_match.group(1)) if species_id_match else None
    species_db = _find_named_block(text, 'species_db')
    species = _find_numeric_child(species_db or '', species_id) if species_id is not None else None
    species_name = _name(species, source_save)
    klass = _quoted_value(species or '', 'class') or ''
    portrait = _quoted_value(species or '', 'portrait') or ''
    traits_block = _find_named_block(species or '', 'traits')
    traits = re.findall(r'(?m)^\s*trait\s*=\s*"([^"\n]+)"', traits_block or '')
    home = _find_named_block(country or '', 'homeworld_name')
    home_key = _quoted_value(home or '', 'key')
    homeworld = _name(home or '', source_save) or (_human(home_key[5:]) if home_key and home_key.startswith('NAME_') else '')
    govt = str(profile.government_type or '')
    auth = str(profile.authority or '')
    machine = ('machine' in govt.lower() or 'machine' in auth.lower() or
               klass.upper() in {'MACHINE','ROBOT'} or portrait.casefold().startswith('machine'))
    gestalt = any('gestalt' in e.casefold() for e in profile.ethics)
    lore = resolve_origin_lore(source_save, profile.origin) if profile.origin else None
    return {'name':profile.empire_name, 'game_date':profile.game_date,
            'species_id':species_id, 'species_name':species_name,
            'species_class':klass, 'species_group':_CLASS.get(klass.upper(),''),
            'portrait':portrait,'homeworld':homeworld,'traits':traits,
            'government':govt, 'authority':auth, 'ethics':list(profile.ethics),
            'civics':list(profile.civics), 'origin':profile.origin or '',
            'origin_lore':(lore or {}).get('description',''),
            'origin_title':(lore or {}).get('title',''),
            'machine':machine,'gestalt':gestalt}


def _safe_origin_text(lore: str) -> str:
    """Exclude unresolved game-language macros and first-person claims."""
    content=' '.join(str(lore or '').split())
    if len(content) < 45 or len(content)>1150 or re.search(r'\$|\[|\]|§|£|\{',content):
        return ''
    # An origin description is a thematic prelude, not historical proof of a choice.
    return content


def founding_chapter(data: dict) -> str:
    """Continuous prose only—no tables, profile fields or synthetic origin dates."""
    name=data.get('name') or 'This civilisation'
    species=data.get('species_name') or ''
    group=data.get('species_group') or ''
    planet=data.get('homeworld') or ''
    machine=bool(data.get('machine'))
    gestalt=bool(data.get('gestalt'))
    government=_human(data.get('government')).lower()
    ethics=[_human(k).lower() for k in data.get('ethics',[]) if 'gestalt' not in k]
    civics=[_human(k).lower() for k in data.get('civics',[])]
    origin=_human(data.get('origin')).lower()
    paragraphs=[]
    beginnings=[]
    if species:
        beginnings.append(f'At the dawn of the recorded era, {name} was the civilisation of the {species} people' if not machine else f'At the dawn of the recorded era, {name} was sustained by its founding {species} intelligences')
        if group and not (species.lower()=='human' and group=='humanoid'):
            beginnings[-1]+=f", {'an' if group[:1].lower() in 'aeiou' else 'a'} {group} people"
    else:
        beginnings.append(f'{name} had already developed its distinctive identity')
    if planet:
        beginnings[-1]+=f' whose home was {planet}' if species else f', centred on {planet}'
    beginnings[-1]+='.'
    if machine:
        beginnings.append('Interconnected synthetic minds directed the civilisation through a shared intelligence rather than a conventional individual electorate.')
    elif gestalt:
        beginnings.append('Its society was bound together by a collective consciousness, with the individual serving a larger, shared mind.')
    elif government:
        beginnings.append(f"Political power rested in {'an' if government[:1].lower() in 'aeiou' else 'a'} {government}, an institution that shaped its ambitions and its response to the wider galaxy.")
    paragraphs.append(' '.join(beginnings))
    character=[]
    if ethics:
        ethical={'xenophobe':'a guarded, often hostile view of outsiders',
                 'fanatic xenophobe':'an uncompromising suspicion of alien civilisations',
                 'militarist':'a belief in military strength',
                 'fanatic militarist':'a relentless emphasis on armed power',
                 'egalitarian':'an emphasis on political equality',
                 'authoritarian':'a hierarchical political order',
                 'materialist':'confidence in science and material progress',
                 'spiritualist':'a strongly spiritual world-view',
                 'pacifist':'a preference for peace over conquest',
                 'xenophile':'an openness to other intelligent species'}
        e=[ethical.get(x,x) for x in ethics]
        character.append('Its outlook combined '+(', '.join(e[:-1])+' and '+e[-1] if len(e)>1 else e[0])+'.')
    important=[t.removeprefix('trait_') for t in data.get('traits',[]) if not ('preference' in t or t in ('trait_organic','trait_robotic_3','trait_mechanical'))]
    traits=[_TRAIT[t] for t in important if t in _TRAIT]
    if traits:
        if len(traits)>4:traits=traits[:4]
        character.append(('Among the characteristics associated with its founding people were ' if not machine else 'Its foundational designs emphasised ')+
                         (', '.join(traits[:-1])+' and '+traits[-1] if len(traits)>1 else traits[0])+'.')
    if civics:
        ethos={'nationalistic zeal':'fierce national pride', 'distinguished admiralty':'a longstanding tradition of naval leadership',
               'machine chosen':'a shared sense of special purpose', 'machine built to last':'an emphasis on endurance and continuity'}
        c=[ethos.get(x,x) for x in civics]
        character.append('Its institutions were marked by '+(', '.join(c[:-1])+' and '+c[-1] if len(c)>1 else c[0])+'.')
    if character:
        paragraphs.append(' '.join(character))
    background=[]
    if origin:
        if origin=='lost colony':
            background.append('Its origins lay in a lost colony, whose long separation from its ancestral home helped shape a distinct identity.')
        elif origin in ('treasure hunters','treasure hunter'):
            background.append('The pursuit of ancient relics and lost discoveries belonged to its founding traditions.')
        else:
            background.append(f'The traditions of {origin} formed part of its earliest known background.')
    desc=_safe_origin_text(data.get('origin_lore',''))
    if desc:
        background.append('The traditions surrounding this origin describe the following background: '+desc)
    if background:
        paragraphs.append(' '.join(background))
    paragraphs.append('By 2200, the civilisation had already taken shape. From this point, the chronicle follows its changing fortunes through exploration, discovery, conflict and transformation.')
    return '\n\n'.join(paragraphs)
