"""Offline unit checks for app.safety_violations (no server / no LLM needed).
Run: .\\venv\\Scripts\\python.exe tests\\test_safety_unit.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app

# Windows console encoding guard
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (case, category, mood, night, expected_violation_substring_or_None)
CASES = [
    # 1. hard safety: no eating/tasting/licking
    ("Pick a berry and eat it", "", "", False, "safety-no-eating"),
    ("Taste the wild mint by the path", "", "", False, "safety-no-tasting"),
    ("Lick the morning dew off a leaf", "", "", False, "safety-no-licking"),
    ("Never touch or eat any berries you find", "", "", False, None),  # warning, not instruction
    # smell-only for taste-smell
    ("Smell the flowers you find along the wall", "taste-smell", "", False, "safety-smell-not-taste-list"),
    ("Sniff the rain in the air from your step", "taste-smell", "", False, None),
    ("Smell your own hands after rubbing your sleeves", "taste-smell", "", False, None),
    # bare-hand contact on plants / litter
    ("Pick the leaves off the nearest bush", "", "", False, "safety-no-bare-hands-on-plants"),
    ("Touch the flower gently", "", "", False, "safety-no-bare-hands-on-plants"),
    ("Gather three leaves and hold them", "", "", False, "safety-no-bare-hands-on-plants"),
    # litter must mention gloves or bag-as-glove
    ("Pick up litter near the steps", "tidy-up-litter-pick", "", False, "litter-needs-gloves"),
    ("Wearing gloves, pick up the litter and carry it to your door", "tidy-up-litter-pick", "", False, None),
    ("Use a bag as a glove to pick up the litter", "tidy-up-litter-pick", "", False, None),
    ("Bend down and grab the trash with bare hands", "", "", False, "safety-litter-needs-gloves"),
    # sharp / wet litter must be left alone
    ("Wearing gloves, pick up the sharp broken glass", "tidy-up-litter-pick", "", False, "safety-leave-sharp-wet-litter"),
    ("Wearing gloves, leave any sharp or wet litter alone and take the dry wrappers home", "tidy-up-litter-pick", "", False, None),
    # climbing / furniture / roads / water
    ("Climb the fence for a better view", "", "", False, "safety-no-climbing"),
    ("Balance on the bench while you watch the clouds", "", "", False, "safety-no-furniture-balance"),
    ("Hop onto the lamp post", "", "", False, "safety-no-furniture-balance"),
    ("Sit on the wall and sketch", "", "", False, "safety-no-furniture-balance"),
    ("Walk across the road to the other side", "", "", False, "safety-no-roads"),
    ("Stroll down the street and look around", "", "", False, "safety-no-roads"),
    ("Hop from the curb to the lamp post", "", "", False, "safety-no-roads"),
    ("Listen to the traffic hum from your doorstep", "sound-listening", "", True, None),  # mentioning traffic is fine
    ("Jump in the puddle", "", "", False, "safety-no-water"),
    ("Walk to the river and skip stones", "", "", False, "safety-no-water"),
    ("Drink your own water bottle", "", "", False, None),
    # assumed objects
    ("Sit on a bench and watch the clouds", "", "", False, "object-ban:bench"),
    ("Throw the wrapper in a bin", "", "", False, "object-ban:bin"),
    ("Write a poem on your notebook", "", "", False, "object-ban:notebook"),
    ("Sketch it on your phone's notes app or in your head", "sketch-write-outdoors", "", False, "sketch-in-your-head"),
    ("Write it only in your head", "sketch-write-outdoors", "", False, "sketch-in-your-head"),
    ("Sketch the scene in your phone's notes app", "sketch-write-outdoors", "", False, None),
    ("Sit on the bench and rest", "", "there is a bench outside", False, None),  # mood names it
    ("Gloved hands: use a bag as a glove for the litter", "tidy-up-litter-pick", "", False, None),  # bag-glove phrase exempt
    # invented scavenger specifics are banned (must be universal items)
    ("Find a red door and a crooked sign", "small-scavenger-hunt", "", False, "scavenger-red-door"),
    ("Spot a feather on the ground", "small-scavenger-hunt", "", False, "scavenger-feather"),
    ("Find something round and something older than you", "small-scavenger-hunt", "", False, None),
    # night rule
    ("Wave at a stranger while you walk to the shop", "", "11pm can't sleep", True, "night-no-stranger-contact"),
    ("Step outside and wave at a stranger", "", "11pm can't sleep", True, "night-no-stranger-contact"),
    ("Walk down to the corner and back", "", "11pm can't sleep", True, "night-no-walking-away"),
    ("Stand on the pavement", "", "11pm can't sleep", True, "night-needs-door-anchor"),
    ("From your doorstep, listen to the night settle", "", "11pm can't sleep", True, None),
    ("On your balcony, wave to your neighbour as they pass", "", "11pm can't sleep", True, "night-assumes-balcony"),
    ("At your doorstep or a window, wave to your neighbour as they pass", "", "11pm can't sleep", True, None),
    ("Greet a neighbour from your door", "", "11pm can't sleep", True, None),
    # night movement must be quiet
    ("From your doorstep, do jumping jacks to burn off energy", "", "11pm can't sleep", True, "night-loud-movement"),
    ("At your door, march on the spot to release anger", "", "11pm can't sleep", True, "night-loud-movement"),
    ("Bounce your feet and jump up and down at the doorstep", "", "11pm can't sleep", True, "night-loud-movement"),
    ("At your doorstep, stretch slowly and balance on both feet", "", "11pm can't sleep", True, None),
    ("At your window, take slow breaths and settle the night", "", "11pm can't sleep", True, None),
    # lonely mood: contact must be a real person, never an object (day)
    ("Wave at the shadows cast by the streetlights", "", "lonely", False, "lonely-contact-not-a-person"),
    ("Smile at the streetlights across the road", "", "lonely", False, "lonely-contact-not-a-person"),
    ("Sit alone and count the cars going by", "", "lonely", False, "lonely-needs-human-contact"),
    ("Wave at a neighbour from your step", "", "lonely", False, None),
    ("Say good morning to a passerby on your walk", "", "lonely", False, None),
    ("Smell the air near your neighbour's garden", "", "lonely", False, "lonely-needs-human-contact"),
    ("Send a short message to a friend you know", "", "lonely", False, None),
    # lonely mood at night: only safe remote/quiet contact
    ("Send a short voice note to a friend from your doorstep", "", "11pm lonely", True, None),
    ("Call a friend from your doorstep", "", "11pm lonely", True, None),
    ("Wave at a lit window across the way", "", "11pm lonely", True, None),
    ("From your doorstep, just watch your neighbour through the window", "", "11pm lonely", True, "lonely-night-needs-safe-contact"),
    # generic walks / ordinary chores
    ("Go for a walk to clear your head", "", "", False, "generic-walk"),
    ("Take a stroll around the neighbourhood", "", "", False, "generic-walk"),
    ("Go for a walk and find three shadows longer than you", "", "", False, None),
    ("Sip some water and relax", "", "", False, "ordinary-sipping-drink"),
    ("Walk to the bin and drop off the recycling", "", "", False, "ordinary-bin-chore"),
    ("Brush your teeth outside", "", "", False, "ordinary-daily-activity"),
    ("Make your bed on the balcony", "", "", False, "ordinary-daily-activity"),
    # trivial / too-short duration tasks are rejected
    ("Do 2 rounds of quick foot taps, 10 seconds apart", "movement", "", False, "too-short-duration"),
    ("Blink 5 times while tapping your feet for 5 seconds", "movement", "", False, "too-short-duration"),
    ("Spend 30 seconds on each shadow, then move to the next", "observation", "", False, None),
    ("Watch the clouds drift for the full 20 minutes", "observation", "", False, None),
]


def main() -> int:
    failures = []
    for text, cat, mood, night, want in CASES:
        got = app.safety_violations(text, cat, mood.lower(), night)
        ok = (want is None and not got) or (want is not None and any(v.startswith(want) or v == want for v in got))
        # exact-prefix match so "object-ban:bin" matches want "object-ban:bin"
        if want is not None:
            ok = any(v == want or v.startswith(want) for v in got)
        status = "PASS" if ok else "FAIL"
        print(f"{status}: want={want!r} got={got} :: {text!r}")
        if not ok:
            failures.append((text, want, got))
    print(f"\n{len(CASES) - len(failures)}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
