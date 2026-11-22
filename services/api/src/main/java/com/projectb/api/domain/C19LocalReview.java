package com.projectb.api.domain;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import com.projectb.api.domain.JourneyKernel.CanonicalPin;
import com.projectb.api.domain.JourneyKernel.DomainException;
import com.projectb.api.domain.JourneyKernel.DraftView;
import com.projectb.api.domain.JourneyKernel.ErrorCode;
import com.projectb.api.domain.JourneyKernel.Step;
import com.projectb.api.json.JsonMini;

/**
 * Deterministic TEST_LOOPBACK_ONLY digest for a persisted C19 draft.
 * Canonical bytes are UTF-8, LF-separated, no trailing newline, domain-separated.
 * String fields use JsonMini JSON quoting. Step order is persisted ordinal order.
 * Candidate id and version are taken from the stored pin {@code id@version}.
 * Content hashes are lowercase hex. Review never accepts a client-supplied digest.
 */
public final class C19LocalReview {
  public static final String ORIGIN = "C19_GOAL_DRAFT";
  public static final String DOMAIN = "c19-local-review-v1";
  public static final String STATE_NONE = "NONE";
  public static final String STATE_ACCEPTED = "ACCEPTED";
  public static final String STATE_INEFFECTIVE = "INEFFECTIVE";

  public record Receipt(UUID draftId, long revision, String digest, String tenantId,
                        String reviewerId, String key, boolean testOnly) {}

  private C19LocalReview() {}

  public static String canonical(DraftView draft) {
    return canonical(draft.draftId(), draft.revision(), draft.title(), draft.steps());
  }

  public static String canonical(UUID draftId, long revision, String title, List<Step> steps) {
    if (draftId == null || title == null || steps == null || steps.isEmpty())
      throw new DomainException(ErrorCode.INVALID, "persisted C19 draft required for digest");
    StringBuilder out = new StringBuilder(DOMAIN);
    out.append('\n').append("draft_id=").append(draftId.toString().toLowerCase(Locale.ROOT));
    out.append('\n').append("revision=").append(revision);
    out.append('\n').append("title=").append(JsonMini.quote(title));
    for (int i = 0; i < steps.size(); i++) {
      Step step = steps.get(i);
      CanonicalPin pin = step.canonicalPin();
      String ref = pin.publishedVersionRef();
      int at = ref.lastIndexOf('@');
      if (at <= 0)
        throw new DomainException(ErrorCode.INVALID, "C19 source pin required");
      out.append('\n').append("step.").append(i).append(".id=").append(step.stepId());
      out.append('\n').append("step.").append(i).append(".title=").append(JsonMini.quote(step.title()));
      out.append('\n').append("step.").append(i).append(".candidate_id=").append(ref.substring(0, at));
      out.append('\n').append("step.").append(i).append(".version=").append(ref.substring(at + 1));
      out.append('\n').append("step.").append(i).append(".content_hash=")
          .append(pin.receiptSha256().toLowerCase(Locale.ROOT));
    }
    return out.toString();
  }

  public static String digest(DraftView draft) {
    return sha256(canonical(draft));
  }

  public static String sha256(String canonical) {
    try {
      byte[] digest = MessageDigest.getInstance("SHA-256").digest(canonical.getBytes(StandardCharsets.UTF_8));
      return HexFormat.of().formatHex(digest);
    } catch (Exception ex) {
      throw new IllegalStateException("SHA-256 is unavailable");
    }
  }
}
