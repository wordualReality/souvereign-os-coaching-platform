"""Synthetic creator preflight: local evidence only, no authorization."""
import json

SCHEMAS = {"kdb_canonical", "kdb_staging", "kdb_governance", "kdb_ops"}
ROLES = {"postgres", "kdb_schema_owner", "kdb_command_owner", "kdb_migrator"}
FUNCTIONS = {"a04_canonical_digest_v2", "security_context_ready", "jsonb_sha256",
             "canonical_command_digest", "canonical_digest_v2", "ingest_source",
             "propose_candidate", "request_review_handoff"}
SIGNATURES = {
    "a04_canonical_digest_v2":"kdb_ops.a04_canonical_digest_v2(jsonb)",
    "canonical_command_digest":"kdb_ops.canonical_command_digest(text,uuid,text,text,text,text,text,text,text,text,text,text,uuid)",
    "canonical_digest_v2":"kdb_ops.canonical_digest_v2(jsonb)",
    "ingest_source":"kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamp with time zone)",
    "jsonb_sha256":"kdb_ops.jsonb_sha256(jsonb)",
    "propose_candidate":"kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid)",
    "request_review_handoff":"kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid)",
    "security_context_ready":"kdb_ops.security_context_ready()",
}
DEFINITION_SHA256 = {
    "a04_canonical_digest_v2":"7ea734800d419b9e2810abf82b8ca07fdd71b6faa14e8d8366f2eab102577eeb",
    "canonical_command_digest":"8cd49e6f0a89ebd5d1d3a7f9f7ab43f23273a8ee54e403d771e8c21c290d794a",
    "canonical_digest_v2":"064cb1e354776e4ad2b2abf83fa820feeaa38bcc3fc0ab955813b607f798818e",
    "ingest_source":"949bf590653befb7665456f543be4b43cf6624660221344a3822504f251a725e",
    "jsonb_sha256":"67e357e1019bb405d89fa804da7a6d4f30166207e6ed9ff0850aeff49684671b",
    "propose_candidate":"4e6e897d50d07a25d02f7527a6b2cc5feb427748f4677e99312dffd1e32d0ea0",
    "request_review_handoff":"42f932ee49630a3a375a964e2c76f866d86d9fd9145255cb012fa1b8ac3bc8ce",
    "security_context_ready":"e38d2145b407ddeff18db47ae61e7331ad2cc2645a10eac2d8d63ed9ebd2d7ec",
}

def acl_matches(entries, grantor, expected):
    if not isinstance(entries, list) or len(entries) != len(expected):
        return False
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"grantor","grantee","privilege","grantable"} or entry["grantor"] != grantor or entry["grantable"] is not False:
            return False
        seen.add((entry["grantee"], entry["privilege"]))
    return seen == expected

def evaluate(evidence):
    result = {"status":"BLOCKED_CREATOR_AUTHORITY", "apply":"NOT_AUTHORIZED",
              "target":"AUTHORITATIVE_TARGET_NOT_VERIFIED",
              "postcommit_restore":"POSTCOMMIT_RESTORE_UNVERIFIED"}
    try:
        if not isinstance(evidence, dict) or set(evidence) != {"version","binding","source","session","restore","schemas","creators","memberships","functions"}:
            return result
        if evidence["version"] != "kdb.a04-r1.creator-evidence.v1" or evidence["binding"] != {"project_ref":"ujdzahwlximlmndexgmx","attestation":"SYNTHETIC_ONLY"}:
            return result
        if evidence["source"] != {"base_sha":"67e417a3ee65ffec2b01da2c3a53e92e7b31c07e","base_manifest_sha256":"235c6b9875a068a82db5c9d3c0bae4305d94fa952ad001bd0d5a2fc5eca6d65e","patch_sha256":"a6af6706ace9fb1d3b9226bf499db2911d2c80141b87faaacbe1fbb3e12e06e7"}:
            return result
        if evidence["session"] != {"session_user":"postgres","current_user":"postgres","identity":"SYNTHETIC_SESSION_ONLY_NOT_ATTESTED"}:
            return result
        if evidence["restore"] != {"backup":"UNVERIFIED","operator":"UNVERIFIED"} or evidence["memberships"] != []:
            return result
        schemas = evidence["schemas"]
        if not isinstance(schemas, list) or len(schemas) != 4 or {x.get("name") for x in schemas} != SCHEMAS:
            return result
        for item in schemas:
            expected = ["kdb_schema_owner","postgres"] if item["name"] != "kdb_ops" else ["kdb_migrator","kdb_schema_owner","postgres"]
            expected_acl = {("kdb_schema_owner","CREATE"), ("kdb_schema_owner","USAGE")}
            if item["name"] == "kdb_ops":
                expected_acl |= {("kdb_migrator","CREATE"), ("kdb_migrator","USAGE")}
            if set(item) != {"name","owner","public_create","creators","acl_safe","acl_entries"} or item["owner"] != "kdb_schema_owner" or item["public_create"] is not False or item["acl_safe"] is not True or item["creators"] != expected or not acl_matches(item["acl_entries"], "kdb_schema_owner", expected_acl):
                return result
        creators = evidence["creators"]
        if not isinstance(creators, list) or len(creators) != 4 or {x.get("role") for x in creators} != ROLES:
            return result
        for item in creators:
            if set(item) != {"role","login","superuser","inherit","bypassrls","global_default_raw","default_namespace","object_type","default_safe","scoped_defaults_safe","acl_entries"}:
                return result
            if item["global_default_raw"] != "{" + item["role"] + "=X/" + item["role"] + "}" or item["default_namespace"] != "GLOBAL" or item["object_type"] != "f" or item["default_safe"] is not True or item["scoped_defaults_safe"] is not True or not acl_matches(item["acl_entries"], item["role"], {(item["role"],"EXECUTE")}):
                return result
            if item["role"] != "postgres" and (item["login"] is not False or item["superuser"] is not False or item["inherit"] is not False or item["bypassrls"] is not False):
                return result
            if item["role"] == "postgres" and (item["login"] is not True or item["superuser"] is not True):
                return result
        functions = evidence["functions"]
        if not isinstance(functions, list) or len(functions) != len(FUNCTIONS) or {x.get("name") for x in functions} != FUNCTIONS:
            return result
        for item in functions:
            if set(item) != {"schema","name","signature","owner","raw_acl","public_execute","runtime_execute","acl_safe","acl_entries","definition_sha256"} or item["schema"] != "kdb_ops" or item["owner"] != "kdb_command_owner":
                return result
            if item["signature"] != SIGNATURES[item["name"]] or item["definition_sha256"] != DEFINITION_SHA256[item["name"]] or not isinstance(item["raw_acl"], str) or item["public_execute"] is not False or item["runtime_execute"] is not False or item["acl_safe"] is not True:
                return result
            expected_acl = {("kdb_command_owner","EXECUTE")}
            if item["name"] in ("jsonb_sha256", "canonical_digest_v2", "canonical_command_digest"):
                expected_acl.add(("kdb_migrator","EXECUTE"))
            if not acl_matches(item["acl_entries"], "kdb_command_owner", expected_acl):
                return result
            raw_expected = "{kdb_command_owner=X/kdb_command_owner"
            if len(expected_acl) == 2:
                raw_expected += ",kdb_migrator=X/kdb_command_owner"
            raw_expected += "}"
            if item["raw_acl"] != raw_expected:
                return result
        result["status"] = "LOCAL_CREATOR_SAFE_FOR_DISPOSABLE"
    except (KeyError, TypeError, AttributeError):
        pass
    return result

def parse_and_evaluate(text):
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj: raise ValueError("duplicate key")
            obj[k] = v
        return obj
    try:
        return evaluate(json.loads(text, object_pairs_hook=unique))
    except (ValueError, TypeError):
        return evaluate(None)
