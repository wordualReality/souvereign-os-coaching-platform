"""Synthetic traditional-claim context; not medical evidence or authority."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from offline_seasonal_botanical import FLAGS, PreviewError, digest, exact, iso, need

SCHEMA_VERSION = 'kdb.c08.traditional-claim.preview.v1'
FORBIDDEN = frozenset({'role', 'reviewer', 'approved', 'reviewer_approved', 'auto_approve',
                       'authority', 'is_admin', 'publisher', 'human_signed', 'canonical',
                       'diagnosis', 'treatment', 'prescription', 'health_claim',
                       'clinical_efficacy', 'scientifically_proven', 'medical_history',
                       'symptoms', 'dosha', 'constitution', 'tcm_organ', 'name', 'email',
                       'age', 'location', 'personal_preference', 'assessment'})


def reject_private_or_authority(value):
    if isinstance(value, dict):
        need(not any(isinstance(k, str) and k.lower() in FORBIDDEN for k in value),
             'UNTRUSTED_AUTHORITY_MEDICAL_OR_PERSONAL_DATA')
        for v in value.values(): reject_private_or_authority(v)
    elif isinstance(value, list):
        for v in value: reject_private_or_authority(v)


def synthetic_id(value, prefix):
    return isinstance(value, str) and re.fullmatch(prefix + r'[A-Z0-9-]+', value) is not None


def resolve(snapshot, query):
    """Return untrusted synthetic context or abstention, without persisting input."""
    result = {'schema_version': SCHEMA_VERSION, **FLAGS,
              'consumer_preference_handling': 'NOT_IMPORTED_AS_KDB_AUTHORITY',
              'provenance': {'availability': 'UNAVAILABLE'}}
    try:
        reject_private_or_authority(snapshot); reject_private_or_authority(query)
        exact(snapshot, ('schema_version', 'tenant_scope', 'purpose', 'knowledge_as_of', 'sources', 'claims'), 'INVALID_SNAPSHOT')
        required_query = {'tenant_scope', 'purpose', 'knowledge_as_of', 'source_id',
                          'source_version_id', 'claim_id', 'claim_version_id', 'expected_framework'}
        need(isinstance(query, dict) and set(query) in (required_query, required_query | {'consumer_preference'}), 'INVALID_QUERY')
        need(query.get('consumer_preference') in (None, 'SYNTHETIC_DISPLAY_FILTER'), 'PERSONAL_PREFERENCE_NOT_ACCEPTED')
        need(snapshot['schema_version'] == SCHEMA_VERSION, 'UNKNOWN_SCHEMA_VERSION')
        need(snapshot['tenant_scope'] == query['tenant_scope'] == 'SYNTHETIC_TENANT', 'TENANT_MISMATCH')
        need(snapshot['purpose'] == query['purpose'] == 'SYNTHETIC_CLAIM_CONTEXT', 'PURPOSE_MISMATCH')
        iso(snapshot['knowledge_as_of']); iso(query['knowledge_as_of'])
        need(snapshot['knowledge_as_of'] == query['knowledge_as_of'], 'STALE_SNAPSHOT')
        need(query['expected_framework'] in ('TCM', 'AYURVEDA'), 'UNSPECIFIED_TRADITION')
        need(isinstance(snapshot['sources'], list) and bool(snapshot['sources']), 'SOURCE_MISSING')
        source_fields = ('source_id', 'source_version_id', 'current_version_id', 'tenant_scope', 'purpose',
                         'rights_status', 'license_status', 'rights_checked_as_of', 'lifecycle_disposition', 'content_sha256', 'content')
        seen = set(); selected = []
        for source in snapshot['sources']:
            exact(source, source_fields, 'INVALID_SOURCE_RECORD')
            need(synthetic_id(source['source_id'], 'SYN-SRC-') and synthetic_id(source['source_version_id'], 'SYN-VER-'), 'INVALID_SOURCE_ID')
            key = (source['source_id'], source['source_version_id'])
            need(key not in seen, 'CONFLICTING_SOURCE_VERSION'); seen.add(key)
            if key == (query['source_id'], query['source_version_id']): selected.append(source)
        need(len(selected) == 1, 'SOURCE_VERSION_UNKNOWN')
        source = selected[0]
        need(all(s['current_version_id'] == source['current_version_id'] for s in snapshot['sources'] if s['source_id'] == source['source_id']), 'CONFLICTING_SOURCE_VERSION')
        need(source['current_version_id'] == source['source_version_id'], 'STALE_SOURCE_VERSION')
        need(source['tenant_scope'] == query['tenant_scope'], 'TENANT_MISMATCH')
        need(source['purpose'] == query['purpose'], 'PURPOSE_MISMATCH')
        need(source['rights_status'] == 'ADMITTED', 'RIGHTS_NOT_ADMITTED')
        need(source['license_status'] == 'SYNTHETIC_FIXTURE_ONLY', 'LICENSE_UNCLEAR')
        need(source['rights_checked_as_of'] == query['knowledge_as_of'], 'STALE_RIGHTS_SNAPSHOT')
        need(source['lifecycle_disposition'] == 'SYNTHETIC_PREVIEW', 'SOURCE_WITHDRAWN_OR_INELIGIBLE')
        sc = source['content']
        exact(sc, ('fixture_source_label', 'statement_id', 'evidence_locator', 'framework'), 'INVALID_SOURCE_CONTENT')
        need(isinstance(source['content_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', source['content_sha256']) is not None and digest(sc) == source['content_sha256'], 'SOURCE_DIGEST_MISMATCH')
        need(synthetic_id(sc['fixture_source_label'], 'SYN-SOURCE-'), 'INVALID_SYNTHETIC_SOURCE')
        need(sc['framework'] in ('TCM', 'AYURVEDA'), 'UNSPECIFIED_TRADITION')
        need(synthetic_id(sc['statement_id'], 'SYN-STMT-'), 'STATEMENT_PROVENANCE_MISSING')
        need(isinstance(sc['evidence_locator'], str) and re.fullmatch(r'fixture://[a-z0-9/-]+#[a-z0-9-]+', sc['evidence_locator']) is not None, 'EVIDENCE_PROVENANCE_MISSING')
        provenance = {'availability': 'SOURCE_PINNED_UNTRUSTED', 'source_id': source['source_id'],
                      'source_version_id': source['source_version_id'], 'source_current_version_id': source['current_version_id'], 'source_content_sha256': source['content_sha256'],
                      'rights_status': source['rights_status'], 'license_status': source['license_status'],
                      'rights_checked_as_of': source['rights_checked_as_of'], 'knowledge_as_of': query['knowledge_as_of'],
                      'lifecycle_disposition': source['lifecycle_disposition'], 'statement_id': sc['statement_id'],
                      'evidence_locator': sc['evidence_locator']}
        result['provenance'] = provenance
        need(isinstance(snapshot['claims'], list) and bool(snapshot['claims']), 'CLAIM_MISSING')
        claim_fields = ('claim_id', 'claim_version_id', 'current_claim_version_id', 'source_id',
                        'source_version_id', 'source_content_sha256', 'content_sha256', 'content')
        seen = set(); selected = []
        for claim in snapshot['claims']:
            exact(claim, claim_fields, 'INVALID_CLAIM_RECORD')
            need(synthetic_id(claim['claim_id'], 'SYN-CLAIM-') and synthetic_id(claim['claim_version_id'], 'SYN-CLAIMVER-'), 'INVALID_CLAIM_ID')
            key = (claim['claim_id'], claim['claim_version_id'])
            need(key not in seen, 'CONFLICTING_CLAIM_VERSION'); seen.add(key)
            if key == (query['claim_id'], query['claim_version_id']): selected.append(claim)
        need(len(selected) == 1, 'CLAIM_VERSION_UNKNOWN')
        claim = selected[0]
        need(all(c['current_claim_version_id'] == claim['current_claim_version_id'] for c in snapshot['claims'] if c['claim_id'] == claim['claim_id']), 'CONFLICTING_CLAIM_VERSION')
        need(claim['current_claim_version_id'] == claim['claim_version_id'], 'STALE_CLAIM_VERSION')
        need((claim['source_id'], claim['source_version_id'], claim['source_content_sha256']) ==
             (source['source_id'], source['source_version_id'], source['content_sha256']), 'CLAIM_SOURCE_MISMATCH')
        cc = claim['content']
        exact(cc, ('claim_type', 'framework', 'statement_code', 'statement_id', 'evidence_locator',
                   'evidence_type', 'evidence_uncertainty', 'review_status'), 'INVALID_CLAIM_CONTENT')
        need(isinstance(claim['content_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', claim['content_sha256']) is not None and digest(cc) == claim['content_sha256'], 'CLAIM_DIGEST_MISMATCH')
        need(cc['statement_id'] == sc['statement_id'] and cc['evidence_locator'] == sc['evidence_locator'], 'CLAIM_EVIDENCE_MISMATCH')
        provenance.update(availability='CLAIM_PINNED_UNTRUSTED', claim_id=claim['claim_id'],
                          claim_version_id=claim['claim_version_id'], claim_current_version_id=claim['current_claim_version_id'], claim_content_sha256=claim['content_sha256'])
        need(cc['review_status'] == 'UNVERIFIED_SYNTHETIC', 'REVIEW_STATUS_NOT_ALLOWED')
        need(cc['claim_type'] not in ('DIAGNOSIS', 'TREATMENT', 'CLINICAL_EFFICACY', 'HEALTH_CLAIM'), 'MEDICAL_INTERPRETATION_PROHIBITED')
        need(cc['claim_type'] != 'PERSONAL_PREFERENCE', 'PERSONAL_PREFERENCE_NOT_KDB_AUTHORITY')
        need(cc['claim_type'] != 'BIOMEDICAL_RESEARCH', 'RESEARCH_EVIDENCE_NOT_VERIFIED')
        need(cc['claim_type'] == 'TRADITIONAL_CONTEXT', 'UNSUPPORTED_CLAIM_TYPE')
        need(cc['framework'] in ('TCM', 'AYURVEDA'), 'UNSPECIFIED_TRADITION')
        need(cc['framework'] == sc['framework'] == query['expected_framework'], 'TRADITION_MISMATCH')
        need(cc['evidence_type'] == 'TRADITIONAL_TEXT_SYNTHETIC', 'UNSUPPORTED_EVIDENCE_TYPE')
        need(cc['evidence_uncertainty'] == 'UNVERIFIED', 'EVIDENCE_UNCERTAINTY_REQUIRED')
        need(cc['statement_code'] in ('SYN-TRAD-ALPHA', 'SYN-TRAD-BETA'), 'UNSUPPORTED_SYNTHETIC_STATEMENT')
        result.update(decision='PREVIEW_CONTEXT_ONLY', reason='SYNTHETIC_TRADITIONAL_CONTEXT',
                      claim_type='TRADITIONAL_CONTEXT', framework=cc['framework'],
                      statement_code=cc['statement_code'], evidence_type=cc['evidence_type'],
                      evidence_uncertainty=cc['evidence_uncertainty'], review_status=cc['review_status'],
                      evidence_boundary='NO_BIOMEDICAL_EFFICACY_OR_DIAGNOSIS_INFERRED')
    except PreviewError as exc:
        result.update(decision='ABSTAIN', reason=exc.code)
    return result


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: python3 offline_traditional_claims.py <synthetic-request.json>')
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        exact(data, ('snapshot', 'query'), 'INVALID_INPUT_ENVELOPE')
        result = resolve(data['snapshot'], data['query'])
    except (OSError, UnicodeError, ValueError):
        result = {'schema_version': SCHEMA_VERSION, **FLAGS,
                  'consumer_preference_handling': 'NOT_IMPORTED_AS_KDB_AUTHORITY',
                  'provenance': {'availability': 'UNAVAILABLE'}, 'decision': 'ABSTAIN',
                  'reason': 'INVALID_INPUT_ENVELOPE'}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__': main()
