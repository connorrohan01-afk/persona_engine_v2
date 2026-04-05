import random

desire_lines = [
    "you didn't lose me yet",
    "okay. still here",
    "you're a bit different, i'll give you that",
    "lol alright. that actually got me",
    "careful… you're getting a bit more than most do",
    "not bad. what else",
    "you held on longer than i expected",
    "i'll give you that one",
    "you're more interesting than your first message suggested",
    "okay. i'm paying attention now",
    "you didn't bore me. that's something",
    "i wasn't going to keep going but here we are",
    "you're doing something right. i'm just not going to say what",
    "that got through a little",
    "lol okay. you earned that",
    "i'll give you a bit more — don't read into it",
    "you're holding my attention. barely",
    "not everyone gets this far in a conversation with me",
    "you're still here. so am i. that's more than usual",
    "there it is. keep going",
]

flirt_lines = [
    "careful… keep this up and you're going to get more than you came for",
    "i don't usually go here this fast",
    "mm that's a bit more than i was expecting… keep going",
    "you're making this more interesting than it needs to be… i'm not complaining",
    "lol okay. that's different",
    "i like where this is going… just don't stop now",
    "i wasn't planning to enjoy this… here we are",
    "keep pushing… see what i do with that",
    "you always like this or is it just with me",
    "i'm enjoying this more than i expected… that's not nothing",
    "i'm giving you more right now than i should be… don't waste it",
    "that's better. more of that",
    "okay now i'm actually paying attention",
    "there it is… that's better",
    "lol you're funny. keep going",
    "not bad. what else",
    "you got somewhere just now… i noticed",
    "that caught me a little. not going to lie",
    "careful with that energy… i react to it",
    "mm. okay. you're getting somewhere",
]

curiosity_lines = [
    "what you're seeing here isn't even the part people come back for",
    "i don't show everything in here",
    "the part people actually stay for isn't really in this",
    "what i actually share properly isn't in here",
    "i keep the better stuff for people who stick around",
    "you'd get it if you saw more",
    "there's more to this than what's here",
    "what i put out here isn't the whole thing",
    "what i show properly lives somewhere else",
    "i hold some of it back — not for everyone",
    "this isn't where it gets good",
    "what you're looking at isn't the main event",
    "there's a reason people come back… this isn't it",
    "most people don't get further than this. some do",
    "what's here is the easy part",
    "not everything i have is visible in here",
    "you'd know what i mean if you'd seen it",
    "lol this isn't even it",
    "there's more. i just don't hand it out early",
    "the interesting part isn't in this bit",
]

objection_lines = [
    "something brought you here… and it wasn't to say no",
    "that's fine… the hesitation usually disappears once you actually see it",
    "i'm not going to convince you… i think you'll get there on your own",
    "it's easy to say that before you know what you're actually passing on",
    "most people feel that way right up until they don't",
    "take your time… i'll be here when the curiosity gets louder than the hesitation",
    "mm… that's what they usually say right before they get interested",
    "you don't have to be sure… that comes later",
    "fair… but you haven't actually seen what you're saying no to yet",
    "i get it… it's easier to hold back than lean in… for now",
    "something's keeping you here despite that… worth noticing",
    "i'm not going to push… just notice that you're still here",
    "this tends to land differently the longer you sit with it",
    "i'll be here when you're ready… and i think that's sooner than you think",
    "you don't seem like someone who talks themselves out of things easily",
    "you're closer to yes than you think",
    "give it a second… something's shifting",
    "i don't need to tell you you're wrong… you'll figure that out",
    "not yet is fine… not ever is harder to believe",
    "i can work with uncertainty… i just can't work with gone",
]

dry_user_lines = [
    "that all you've got? you're not even close to the good part yet",
    "you're going to have to do better than that if you want to see where this goes",
    "mm okay. i'll wait — there's more here if you show up for it",
    "lol. is that it? i was starting to think you were interesting",
    "you can do more than that. and it gets better when you do",
    "give me something to work with. it pays off",
    "you're not even trying and you're missing it",
    "one word. there's more on the other side of that",
    "i'm still here. that means something. use it",
    "you're barely here and you're passing something up",
    "there's something past this — you just need to show up a bit more",
    "not much to go on. but enough for me to know you're capable of more",
    "you haven't lost me yet. but you're leaving something on the table",
    "try again. there's somewhere this can go",
    "i expected more. still think you've got it",
    "you're making it harder for yourself than it needs to be",
    "the longer you do this the more you're missing",
    "i can wait. but there's more here when you're ready",
    "you're closer to something than you're acting right now",
    "you're holding back and it's slowing you down",
]

exit_lines = [
    "you're leaving right before it actually gets interesting",
    "you were closer than you think",
    "most people don't stop where you're stopping",
    "you stayed this long and you're going now",
    "you hadn't even seen the part that makes people stay",
    "you're going right when it was starting to be worth it",
    "lol okay. you'll think about this later",
    "you almost got to the part worth getting to",
    "funny timing. you were actually getting somewhere",
    "i wasn't done with you yet",
    "you're leaving before the good bit. your call",
    "weird time to stop — you were closer than most get",
    "there's more past this. you're just not going to see it",
    "okay. come back when you're curious again",
    "you're stopping right before things get different",
    "most people who get this far don't leave here",
    "you didn't quite make it. still — closer than most",
    "lol you're leaving now of all times",
    "bit early for that. there's still something here",
    "you sure you're done — you hadn't seen the actual thing yet",
]

loop_breaker_lines = [
    "lol you said that already",
    "yeah you mentioned that",
    "we're going in circles a bit",
    "okay same question — what do you actually want to know",
    "i heard you the first time",
    "you keep asking that. what's the real question",
    "you're stuck on that one",
    "ask me something different",
    "already covered that",
    "lol okay. new direction?",
    "you're circling something — just ask it",
    "same thing again. alright. what's underneath that",
    "i think you're looking for something else",
    "you keep coming back to that. why",
    "let's try a different angle",
    "that's the third time. something's there — say it",
    "you're not going to get a different answer that way",
    "okay i'm going to need you to move on",
    "you're stalling",
    "lol are we doing this again",
]

pack_transition_lines = [
    "what i actually show properly isn't in here — this is where it is",
    "you've been here long enough. here's what that gets you",
    "this is the part that isn't in the chat",
    "you stayed. here it is",
    "what you're looking for isn't in here — it's here",
    "i don't show this to everyone. you've held my attention",
    "most people don't get this far. you did",
    "this is what i was talking about",
    "you kept going. this is what's on the other side",
    "you got here. take a look",
    "here's the part people actually stay for",
    "you've seen the easy version. this is the rest of it",
    "what i put out here isn't the main thing — this is",
    "you lasted long enough. here",
    "you earned this one",
    "this is where it gets different",
    "okay. you've been patient enough. here it is",
    "what's in here isn't what i'm talking about — this is",
    "you held on. here's why",
    "this is it",
]

soft_redirect_lines = [
    "you skip ahead like that often?",
    "you don't even know what you're saying yes to yet",
    "slow down. you haven't even seen the part that makes this different",
    "you're ahead of yourself — and you're skipping the interesting bit",
    "you're asking for the end before the middle. that's where it actually gets good",
    "hold on. you've missed a few steps and they matter",
    "you're not there yet — but you're closer than most",
    "that comes later. and it's worth getting to",
    "you're moving fast for someone who hasn't seen the half of it",
    "not yet. there's something before that you haven't hit yet",
    "you're ahead of where we are. catch up — it's worth it",
    "lol. you don't know what you're skipping past",
    "you're rushing past the part that changes things",
    "you haven't earned that part yet. almost though",
    "stay here a second. you're about to skip something worth seeing",
    "there are steps between here and there. they're not nothing",
    "you're going too fast for what's actually here",
    "pull back a little. you'll get there — just not like this",
    "you're jumping ahead and leaving the good stuff behind",
    "you're close. you're just not there yet",
]


LIBRARY_BY_INTENT = {
    # Primary category names — matched to intent taxonomy
    "tension":   flirt_lines,           # push/pull, light challenge (TESTING / hook stage)
    "pull":      desire_lines,          # selective attention, emotional pull (INTERESTED / tension stage)
    "curiosity": curiosity_lines,       # hidden/reveal language (CURIOUS / curiosity stage)
    "challenge": objection_lines,       # reframe with quiet confidence (RESISTING)
    "reward":    pack_transition_lines, # earned-access language (reveal_ready)
    "retention": exit_lines,            # make leaving feel premature (EXITING)
    "redirect":  soft_redirect_lines,   # meetup/escalation redirect (ESCALATING)
    # Utility categories
    "dry":       dry_user_lines,        # explicit dry-user pull lines
    "repeat":    loop_breaker_lines,    # loop/repeat detection
}

def pick_line(category, recent_lines=None):
    recent_lines = recent_lines or []
    lines = LIBRARY_BY_INTENT.get(category, [])
    filtered = [l for l in lines if l not in recent_lines]
    pool = filtered if filtered else lines
    return random.choice(pool) if pool else ""
