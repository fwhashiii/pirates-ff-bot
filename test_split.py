"""Test split-message bypass detection."""
import re
from collections import deque

BANNED_WORDS = [
    r"\bhooyada\s*was\b",
    r"\bhoyada\s*was\b",
    r"\bkys\b",
    r"\bsharmuta\b",
    r"\bdhilo\b",
    r"\bwas\s*(hooyo|aabo|abahaa|hooyada|naag)\b",
    r"\b(hooyo|aabo|abahaa|hooyada|naag)\s*was\b",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in BANNED_WORDS]

def check(text):
    normalized = text.lower().replace("@","a").replace("3","e").replace("1","i").replace("0","o")
    for p in _compiled:
        if p.search(text) or p.search(normalized):
            return f"CAUGHT ({p.pattern})"
    return "CLEAN"

# Simulate the 5-message buffer
buffer = deque(maxlen=5)

def send_message(msg):
    buffer.append(msg)
    combined = " ".join(buffer)
    single = check(msg)
    combined_result = check(combined)
    result = single if single != "CLEAN" else combined_result
    print(f"  Msg: '{msg}' | Single: {single} | Combined: {combined_result} | FINAL: {result}")
    return result

print("Test 1: Normal split bypass (hooyada + was in separate messages)")
buffer.clear()
send_message("hey guys")
send_message("hooyada")
r = send_message("was")
print(f"  -> {'CAUGHT ✅' if r != 'CLEAN' else 'MISSED ❌'}\n")

print("Test 2: Single message (should catch)")
buffer.clear()
r = send_message("hooyada was")
print(f"  -> {'CAUGHT ✅' if r != 'CLEAN' else 'MISSED ❌'}\n")

print("Test 3: Normal conversation (should NOT catch)")
buffer.clear()
send_message("lets play free fire")
send_message("good game")
r = send_message("nice shot")
print(f"  -> {'CLEAN ✅' if r == 'CLEAN' else 'FALSE POSITIVE ❌'}\n")

print("Test 4: kys split across messages")
buffer.clear()
send_message("bro")
r = send_message("kys")
print(f"  -> {'CAUGHT ✅' if r != 'CLEAN' else 'MISSED ❌'}\n")
