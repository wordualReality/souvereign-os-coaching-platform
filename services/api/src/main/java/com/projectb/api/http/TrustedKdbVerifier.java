package com.projectb.api.http;

import java.util.List;
import java.util.Map;
import com.projectb.api.json.JsonMini;

/**
 * No live KDB verifier is connected.
 * A caller pin is stored input. It is not a KDB publication approval.
 */
public final class TrustedKdbVerifier {
  public static final TrustedKdbVerifier NONE = new TrustedKdbVerifier();

  private TrustedKdbVerifier() {}

  public boolean verifiesLivePublication() { return false; }

  public boolean claimsApproval(String phasesJson) {
    return walk(JsonMini.parse(phasesJson));
  }

  private static boolean walk(Object node) {
    if (node instanceof Map<?, ?> map) {
      Object rights = map.get("rights_state");
      Object state = map.get("publication_state");
      if (rights != null && !"caller-supplied-not-verified".equals(rights)) return true;
      if (map.containsKey("canonical_ref") && "PUBLISHED".equals(state)) return true;
      for (Object value : map.values()) if (walk(value)) return true;
    } else if (node instanceof List<?> list) {
      for (Object value : list) if (walk(value)) return true;
    }
    return false;
  }
}
