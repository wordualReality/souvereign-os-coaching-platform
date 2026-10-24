package com.projectb.api.json;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Small JSON subset for the local journey service. No third-party parser. */
public final class JsonMini {
  private JsonMini() {}

  public static Object parse(String text) {
    Parser parser = new Parser(text);
    Object value = parser.value();
    parser.skip();
    if (!parser.end()) throw new IllegalArgumentException("trailing JSON");
    return value;
  }

  @SuppressWarnings("unchecked")
  public static Map<String, Object> object(Object value) {
    if (!(value instanceof Map<?, ?> map)) throw new IllegalArgumentException("JSON object required");
    return (Map<String, Object>) map;
  }

  public static String text(Object value) {
    if (!(value instanceof String text) || text.isBlank()) throw new IllegalArgumentException("JSON string required");
    return text;
  }

  public static long integer(Object value) {
    if (!(value instanceof Long number)) throw new IllegalArgumentException("JSON integer required");
    return number;
  }

  public static String quote(String value) {
    StringBuilder out = new StringBuilder(value.length() + 2).append('"');
    for (int i = 0; i < value.length(); i++) {
      char c = value.charAt(i);
      switch (c) {
        case '"' -> out.append("\\\"");
        case '\\' -> out.append("\\\\");
        case '\n' -> out.append("\\n");
        case '\r' -> out.append("\\r");
        case '\t' -> out.append("\\t");
        default -> {
          if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
          else out.append(c);
        }
      }
    }
    return out.append('"').toString();
  }

  private static final class Parser {
    private final String text;
    private int index;

    Parser(String text) { this.text = text; }

    boolean end() { return index >= text.length(); }

    Object value() {
      skip();
      if (end()) throw new IllegalArgumentException("incomplete JSON");
      char c = text.charAt(index);
      if (c == '{') return object();
      if (c == '[') return array();
      if (c == '"') return string();
      if (c == 't' || c == 'f') return bool();
      if (c == 'n') return nil();
      if (c == '-' || (c >= '0' && c <= '9')) return number();
      throw new IllegalArgumentException("unexpected JSON");
    }

    private Map<String, Object> object() {
      index++;
      Map<String, Object> map = new LinkedHashMap<>();
      skip();
      if (peek('}')) { index++; return map; }
      while (true) {
        skip();
        String key = string();
        skip();
        if (!peek(':')) throw new IllegalArgumentException("missing colon");
        index++;
        map.put(key, value());
        skip();
        if (peek('}')) { index++; return map; }
        if (!peek(',')) throw new IllegalArgumentException("missing comma");
        index++;
      }
    }

    private List<Object> array() {
      index++;
      List<Object> list = new ArrayList<>();
      skip();
      if (peek(']')) { index++; return list; }
      while (true) {
        list.add(value());
        skip();
        if (peek(']')) { index++; return list; }
        if (!peek(',')) throw new IllegalArgumentException("missing comma");
        index++;
      }
    }

    private String string() {
      if (!peek('"')) throw new IllegalArgumentException("string required");
      index++;
      StringBuilder out = new StringBuilder();
      while (!end()) {
        char c = text.charAt(index++);
        if (c == '"') return out.toString();
        if (c == '\\') {
          if (end()) throw new IllegalArgumentException("bad escape");
          char escaped = text.charAt(index++);
          out.append(switch (escaped) {
            case '"', '\\', '/' -> escaped;
            case 'b' -> '\b';
            case 'f' -> '\f';
            case 'n' -> '\n';
            case 'r' -> '\r';
            case 't' -> '\t';
            case 'u' -> unicode();
            default -> throw new IllegalArgumentException("bad escape");
          });
        } else if (c < 0x20) {
          throw new IllegalArgumentException("raw control character");
        } else {
          out.append(c);
        }
      }
      throw new IllegalArgumentException("unterminated string");
    }

    private char unicode() {
      if (index + 4 > text.length()) throw new IllegalArgumentException("bad unicode");
      int code = Integer.parseInt(text.substring(index, index + 4), 16);
      index += 4;
      return (char) code;
    }

    private Boolean bool() {
      if (text.startsWith("true", index)) { index += 4; return Boolean.TRUE; }
      if (text.startsWith("false", index)) { index += 5; return Boolean.FALSE; }
      throw new IllegalArgumentException("bad boolean");
    }

    private Object nil() {
      if (!text.startsWith("null", index)) throw new IllegalArgumentException("bad null");
      index += 4;
      return null;
    }

    private Long number() {
      int start = index;
      if (peek('-')) index++;
      if (end() || text.charAt(index) < '0' || text.charAt(index) > '9')
        throw new IllegalArgumentException("bad number");
      while (!end() && text.charAt(index) >= '0' && text.charAt(index) <= '9') index++;
      if (!end() && (text.charAt(index) == '.' || text.charAt(index) == 'e' || text.charAt(index) == 'E'))
        throw new IllegalArgumentException("only integers are accepted");
      return Long.parseLong(text.substring(start, index));
    }

    private void skip() {
      while (!end()) {
        char c = text.charAt(index);
        if (c != ' ' && c != '\n' && c != '\r' && c != '\t') return;
        index++;
      }
    }

    private boolean peek(char expected) {
      return !end() && text.charAt(index) == expected;
    }
  }
}
