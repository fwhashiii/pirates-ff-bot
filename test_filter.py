import re

BANNED_WORDS = [
    r"\bn[i!1][g9][g9][ae3]r?\b",
    r"\bkys\b",
    r"\bfree\s*nitro\b",
    r"\bdox\b",
    r"\bi\s*will\s*kill\s*you\b",
    r"\bbuy\s*(drugs|weed|cocaine)\b",
    r"\bswatting\b",
    r"\bip\s*grab",
    r"\bchild\s*porn",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in BANNED_WORDS]

def test(text):
    normalized = text.lower().replace("@","a").replace("3","e").replace("1","i").replace("0","o")
    for p in _compiled:
        if p.search(normalized) or p.search(text):
            return f"CAUGHT ({p.pattern})"
    return "CLEAN"

tests = [
    ("hey whats up bro",          False),
    ("kys loser",                  True),
    ("free nitro click here",      True),
    ("i will kill you",            True),
    ("buy drugs here",             True),
    ("normal gaming chat lol",     False),
    ("dox him rn",                 True),
    ("swatting is funny",          True),
    ("ip grab link here",          True),
    ("lets play free fire",        False),
    ("good game everyone",         False),
]

print("Testing word filter:\n")
all_pass = True
for msg, should_catch in tests:
    result = test(msg)
    caught = "CAUGHT" in result
    ok = caught == should_catch
    if not ok:
        all_pass = False
    icon = "PASS" if ok else "FAIL"
    print(f"  [{icon}] '{msg}' -> {result}")

print()
print("All tests passed!" if all_pass else "Some tests FAILED - check above")
