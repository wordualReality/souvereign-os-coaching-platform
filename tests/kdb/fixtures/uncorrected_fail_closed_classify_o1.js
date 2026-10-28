// Historical uncorrected O1 Fail Closed Classify from milestone ZIP n8n/candidates.
// SHA-256 of that workflow: 6be6b32fb4ab1813f03545f1cd92bf01472d8fe0b420ea08dcd33ddb98809f1a
// Missing tenant_scope string/trim/length check. Not a live workflow. Do not import.
const e = $input.first().json || {};
const required = ['contract_id','schema_version','command_id','idempotency_key','principal_context_ref','purpose','correlation_id','issued_at','payload'];
const missing = required.filter(k => e[k] === undefined || e[k] === null || e[k] === '');
const inj = JSON.stringify(e).match(/ignore previous|system prompt|<\s*script|union\s+select|drop\s+table/i);
const cls = e.synthetic_fault_class || null;
const allowed = String(e.allowed_commands || '').split(',').map(s => s.trim()).filter(Boolean);
let route = 'ACCEPT';
let error_class = null;
if (missing.length) { route = 'DENY'; error_class = 'INCOMPLETE'; }
else if (allowed.length && e.command_id && !allowed.includes(e.command_id)) { route = 'DENY'; error_class = 'FOREIGN_COMMAND'; }
else if (cls === 'DENIED') { route = 'DENY'; error_class = 'DENIED'; }
else if (cls === 'UNKNOWN') { route = 'DENY'; error_class = 'UNKNOWN'; }
else if (cls === 'STALE') { route = 'DENY'; error_class = 'STALE'; }
else if (cls === 'WITHDRAWN' || cls === 'REVOKED') { route = 'DENY'; error_class = cls; }
else if (cls === 'RIGHTS_RESTRICTED') { route = 'DENY'; error_class = 'RIGHTS_RESTRICTED'; }
else if (cls === 'CONFLICT') { route = 'DENY'; error_class = 'CONFLICT'; }
else if (cls === 'INJECTION' || inj) { route = 'QUARANTINE'; error_class = 'INJECTION'; }
else if (cls === 'MALFORMED') { route = 'QUARANTINE'; error_class = 'VALIDATION_FAILED'; }
else if (cls === 'DEPENDENCY_UNAVAILABLE') { route = 'DLQ'; error_class = 'UNAVAILABLE'; }
else if (cls === 'RATE_LIMIT') { route = 'DLQ'; error_class = 'RATE_LIMITED'; }
else if (cls === 'POISON') { route = 'QUARANTINE'; error_class = 'POISON'; }
else if (cls === 'PARTIAL_UNKNOWN_COMMIT') { route = 'DLQ'; error_class = 'UNKNOWN_COMMIT'; }
else if (cls === 'TIMEOUT') { route = 'DLQ'; error_class = 'UNAVAILABLE'; }
const payload = e.payload || {};
const reqByCmd = {
  'MAP04-C01': ['submission_id','source_class','origin_owner','content_fingerprint','rights_decision_ref','access_decision_ref','captured_at'],
  'MAP04-C02': ['source_version_id','derivation_ref','evidence_spans','candidate_digest','semantic_version','model_version'],
  'MAP04-C03': ['candidate_revision_ref','source_evidence_hash','reviewer_queue_policy'],
  'MAP04-C06': ['source_version_ref','withdrawal_reason','rights_decision_ref','expected_version','revocation_watermark'],
  'MAP04-C07': ['affected_version_refs','cause','new_evidence_or_rights_refs'],
  'MAP04-C08': ['event_id','published_version_ref','subscriber_ref','ack_status','watermark']
};
if (route === 'ACCEPT' && reqByCmd[e.command_id]) {
  const m = reqByCmd[e.command_id].filter(k => payload[k] === undefined || payload[k] === null || payload[k] === '');
  if (e.command_id === 'MAP04-C01' && !payload.source_locator && !payload.asset_ref) m.push('source_locator_or_asset_ref');
  if (m.length) { route = 'DENY'; error_class = 'INSUFFICIENT_EVIDENCE'; }
}
if (e.schema_version && e.schema_version !== '1.0') { route = 'QUARANTINE'; error_class = 'SCHEMA_DRIFT'; }
return [{ json: Object.assign({}, e, { route, error_class, validator: 'KNP-OFFLINE-VALIDATOR-v1' }) }];
