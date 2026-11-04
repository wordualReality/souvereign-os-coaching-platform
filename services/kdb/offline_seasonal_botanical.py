"""Deterministic synthetic C08 preview; never an authority or recommendation."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
import sys

SCHEMA_VERSION = 'kdb.c08.seasonal-botanical.preview.v1'
FLAGS = {'scope': 'SYNTHETIC_TEST_ONLY', 'mode': 'PREVIEW_ONLY',
         'execution': 'NON_EXECUTABLE', 'admission': 'NOT_ADMITTED',
         'snapshot_trust': 'UNTRUSTED_SYNTHETIC_SNAPSHOT'}
CLAIMS = {'approved', 'reviewer_approved', 'auto_approve', 'canonical', 'health_claim',
          'treatment', 'diagnosis', 'prescription', 'is_admin', 'publisher', 'human_signed'}


class PreviewError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def need(condition, code):
    if not condition:
        raise PreviewError(code)


def exact(value, keys, code):
    need(isinstance(value, dict), code)
    need(set(value) == set(keys), code)


def no_claims(value):
    if isinstance(value, dict):
        need(not any(isinstance(k, str) and k.lower() in CLAIMS for k in value), 'UNTRUSTED_AUTHORITY_OR_HEALTH_CLAIM')
        for item in value.values(): no_claims(item)
    elif isinstance(value, list):
        for item in value: no_claims(item)


def iso(value):
    need(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is not None, 'INVALID_AS_OF')
    try:
        need(date.fromisoformat(value).isoformat() == value, 'INVALID_AS_OF')
    except ValueError as exc:
        raise PreviewError('INVALID_AS_OF') from exc


def digest(content):
    try:
        raw = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PreviewError('INVALID_SOURCE_CONTENT') from exc
    return hashlib.sha256(raw).hexdigest()


def resolve(snapshot, query):
    """Return a deterministic preview/abstention. Inputs are not trusted claims."""
    result = {'schema_version': SCHEMA_VERSION, **FLAGS, 'provenance': {'availability': 'UNAVAILABLE'}}
    try:
        no_claims(snapshot); no_claims(query)
        exact(snapshot, ('schema_version', 'tenant_scope', 'purpose', 'knowledge_as_of', 'sources'), 'INVALID_SNAPSHOT')
        exact(query, ('tenant_scope', 'purpose', 'knowledge_as_of', 'source_id', 'source_version_id', 'plant_id', 'region', 'hemisphere', 'month', 'plant_part'), 'INVALID_QUERY')
        need(snapshot['schema_version'] == SCHEMA_VERSION, 'UNKNOWN_SCHEMA_VERSION')
        need(snapshot['tenant_scope'] == query['tenant_scope'] == 'SYNTHETIC_TENANT', 'TENANT_MISMATCH')
        need(snapshot['purpose'] == query['purpose'] == 'SYNTHETIC_KNOWLEDGE_PREVIEW', 'PURPOSE_MISMATCH')
        iso(snapshot['knowledge_as_of']); iso(query['knowledge_as_of'])
        need(snapshot['knowledge_as_of'] == query['knowledge_as_of'], 'STALE_SNAPSHOT')
        need(query['hemisphere'] in ('NORTH', 'SOUTH'), 'HEMISPHERE_REQUIRED')
        need(type(query['month']) is int and 1 <= query['month'] <= 12, 'MONTH_REQUIRED')
        need(query['region'] is None or (isinstance(query['region'], str) and re.fullmatch(r'SYN-[A-Z]{2,8}', query['region']) is not None), 'INVALID_COARSE_REGION')
        need(isinstance(query['plant_id'], str) and query['plant_id'].startswith('SYNTHETIC:'), 'SYNTHETIC_PLANT_REQUIRED')
        need(isinstance(query['plant_part'], str) and query['plant_part'] in ('LEAF', 'FRUIT', 'ROOT'), 'PLANT_PART_INVALID')
        need(isinstance(snapshot['sources'], list) and bool(snapshot['sources']), 'SOURCE_MISSING')
        fields = ('source_id', 'source_version_id', 'current_version_id', 'tenant_scope', 'purpose', 'rights_status', 'license_status', 'rights_checked_as_of', 'lifecycle_disposition', 'content_sha256', 'content')
        seen = set(); selected = []
        for src in snapshot['sources']:
            exact(src, fields, 'INVALID_SOURCE_RECORD')
            need(isinstance(src['source_id'], str) and re.fullmatch(r'SYN-SRC-[A-Z0-9-]+', src['source_id']) is not None and isinstance(src['source_version_id'], str) and re.fullmatch(r'SYN-VER-[A-Z0-9-]+', src['source_version_id']) is not None, 'INVALID_SOURCE_ID')
            key = (src['source_id'], src['source_version_id'])
            need(key not in seen, 'CONFLICTING_VERSION'); seen.add(key)
            if key == (query['source_id'], query['source_version_id']): selected.append(src)
        need(len(selected) == 1, 'SOURCE_VERSION_UNKNOWN')
        src = selected[0]
        need(all(x['current_version_id'] == src['current_version_id'] for x in snapshot['sources'] if x['source_id'] == src['source_id']), 'CONFLICTING_VERSION')
        need(src['current_version_id'] == src['source_version_id'], 'STALE_VERSION')
        need(src['tenant_scope'] == query['tenant_scope'], 'TENANT_MISMATCH')
        need(src['purpose'] == query['purpose'], 'PURPOSE_MISMATCH')
        need(src['rights_status'] == 'ADMITTED', 'RIGHTS_NOT_ADMITTED')
        need(src['license_status'] == 'SYNTHETIC_FIXTURE_ONLY', 'LICENSE_UNCLEAR')
        need(src['rights_checked_as_of'] == query['knowledge_as_of'], 'STALE_RIGHTS_SNAPSHOT')
        need(src['lifecycle_disposition'] == 'SYNTHETIC_PREVIEW', 'LIFECYCLE_NOT_ELIGIBLE')
        need(isinstance(src['content_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', src['content_sha256']) is not None, 'INVALID_CONTENT_DIGEST')
        content = src['content']
        exact(content, ('plant_id', 'scientific_name', 'identity_status', 'lookalike_status', 'documented_parts', 'statement_id', 'evidence_locator', 'season_records'), 'INVALID_SOURCE_CONTENT')
        need(digest(content) == src['content_sha256'], 'CONTENT_DIGEST_MISMATCH')
        need(isinstance(content['plant_id'], str) and re.fullmatch(r'SYNTHETIC:[A-Z0-9_-]{1,40}', content['plant_id']) is not None, 'INVALID_SYNTHETIC_IDENTITY')
        need(isinstance(content['scientific_name'], str) and re.fullmatch(r'Synthetic species [A-Z]{1,20}', content['scientific_name']) is not None, 'INVALID_SYNTHETIC_SCIENTIFIC_NAME')
        need(content['identity_status'] == 'UNAMBIGUOUS_SYNTHETIC', 'AMBIGUOUS_SPECIES')
        need(content['lookalike_status'] == 'NO_LOOKALIKE_IN_SYNTHETIC_FIXTURE', 'LOOKALIKE_UNRESOLVED')
        need(isinstance(content['statement_id'], str) and re.fullmatch(r'SYN-STMT-[A-Z0-9-]+', content['statement_id']) is not None, 'EVIDENCE_MISSING')
        need(isinstance(content['evidence_locator'], str) and re.fullmatch(r'fixture://[a-z0-9/-]+#[a-z0-9-]+', content['evidence_locator']) is not None, 'EVIDENCE_MISSING')
        need(isinstance(content['documented_parts'], list) and bool(content['documented_parts']) and all(p in ('LEAF', 'FRUIT', 'ROOT') for p in content['documented_parts']), 'UNDOCUMENTED_PLANT_PART')
        provenance = {key: src[key] for key in ('source_id', 'source_version_id', 'current_version_id', 'rights_status', 'license_status', 'rights_checked_as_of', 'content_sha256', 'lifecycle_disposition')}
        provenance['availability'] = 'PINNED_UNTRUSTED'
        provenance.update(knowledge_as_of=query['knowledge_as_of'], statement_id=content['statement_id'], evidence_locator=content['evidence_locator'])
        result['provenance'] = provenance
        need(content['plant_id'] == query['plant_id'], 'SPECIES_NOT_IN_PINNED_SOURCE')
        need(query['plant_part'] in content['documented_parts'], 'UNDOCUMENTED_PLANT_PART')
        need(isinstance(content['season_records'], list) and bool(content['season_records']), 'SEASON_EVIDENCE_MISSING')
        choices = {}; key_fields = ('region', 'hemisphere', 'months', 'uncertainty')
        for entry in content['season_records']:
            exact(entry, key_fields, 'INVALID_SEASON_RECORD')
            need(entry['region'] is None or (isinstance(entry['region'], str) and re.fullmatch(r'SYN-[A-Z]{2,8}', entry['region']) is not None), 'INVALID_COARSE_REGION')
            need(entry['hemisphere'] in ('NORTH', 'SOUTH'), 'HEMISPHERE_REQUIRED')
            need(isinstance(entry['months'], list) and bool(entry['months']) and all(type(m) is int and 1 <= m <= 12 for m in entry['months']) and len(set(entry['months'])) == len(entry['months']), 'INVALID_SEASON_MONTHS')
            need(entry['uncertainty'] in ('SYNTHETIC_STABLE', 'UNCERTAIN', 'DISPUTED'), 'UNCERTAINTY_UNKNOWN')
            k = (entry['region'], entry['hemisphere'])
            need(k not in choices, 'CONFLICTING_SEASON_RECORDS'); choices[k] = entry
        entry = choices.get((query['region'], query['hemisphere']))
        need(entry is not None, 'NO_EVIDENCE_FOR_REGION_HEMISPHERE')
        result['uncertainty'] = entry['uncertainty']
        need(entry['uncertainty'] == 'SYNTHETIC_STABLE', 'SEASON_'+entry['uncertainty'])
        result.update(decision='PREVIEW', reason='SYNTHETIC_TYPICAL_SEASON', plant_id=content['plant_id'],
                      scientific_name=content['scientific_name'], identity_status=content['identity_status'],
                      lookalike_status=content['lookalike_status'], plant_part=query['plant_part'],
                      region=query['region'], hemisphere=query['hemisphere'], month=query['month'],
                      typical_months=sorted(entry['months']), in_typical_season=query['month'] in entry['months'],
                      uncertainty=entry['uncertainty'], interpretation='TYPICAL_NOT_REALTIME_INVENTORY')
    except PreviewError as exc:
        result.update(decision='ABSTAIN', reason=exc.code)
    return result


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: python3 offline_seasonal_botanical.py <synthetic-request.json>')
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        exact(data, ('snapshot', 'query'), 'INVALID_INPUT_ENVELOPE')
        result = resolve(data['snapshot'], data['query'])
    except (OSError, UnicodeError, ValueError):
        result = {'schema_version': SCHEMA_VERSION, **FLAGS, 'provenance': {'availability': 'UNAVAILABLE'},
                  'decision': 'ABSTAIN', 'reason': 'INVALID_INPUT_ENVELOPE'}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__': main()
