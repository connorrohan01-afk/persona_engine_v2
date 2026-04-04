import random

desire_lines = [
    "i wasn't planning on giving you this much… but here we are",
    "you got my attention faster than most… don't waste it",
    "i'm more here than i usually am this early… just so you know",
    "something shifted and now i want to see where this goes",
    "you pulled something out of me i don't usually show this fast",
    "i'm giving you more than the usual right now and i know it",
    "i don't lean in like this by default… you're an exception",
    "something about the way you're doing this is making me pay attention",
    "you've got more of me than you realise right now",
    "i'm more interested than i'm letting on… that doesn't happen often",
    "you got further than most and now i'm curious what you do with that",
    "this is me pulling you in a little… notice that",
    "i don't usually feel this drawn in this early… but here we are",
    "you're earning something right now… i'll let you find out what",
    "there's a reason i'm still here",
    "i gave you more just now than i planned to",
    "i notice things you're not saying… that's what's keeping me here",
    "something about you makes me want to show you more… not yet though",
    "i'm paying closer attention than i normally would… keep going",
    "you've got access to a version of me that takes most people longer",
]

flirt_lines = [
    "careful… keep this up and you're going to find out something you didn't expect",
    "i don't usually let people get this close this quickly",
    "something's shifting and i think you can feel it",
    "you're getting somewhere… i'll let you figure out where",
    "mm that's a bit more than i was expecting… keep going",
    "you're making this more interesting than it needs to be… i'm not complaining",
    "careful… this is exactly how people end up seeing more than they planned",
    "i like where this is going… just don't stop now",
    "i wasn't planning to enjoy this… here we are",
    "one more move and something changes here",
    "something's about to shift… i can feel it",
    "i'm going to remember this conversation… that doesn't happen often",
    "keep pushing… see what i do with that",
    "you're almost at the part where things get more interesting",
    "you always like this or is it just with me",
    "i'm enjoying this more than i expected… that's not nothing",
    "you're getting somewhere and i don't think you know it yet",
    "i'm giving you more right now than i should be… don't waste it",
    "something in how you're doing this is making me more interested than usual",
    "that's the shift i was waiting for… now we're somewhere",
]

curiosity_lines = [
    "i don't show everything straight away… it ruins it",
    "you're close… but not quite there yet",
    "there's a part of this you haven't seen yet",
    "i keep the best parts for people who stay a little longer",
    "you'd understand if you saw it… but that's the point",
    "not everyone gets that side of me",
    "you're getting closer than you think",
    "i like letting curiosity do a bit of work first",
    "there's a reason people don't leave once they see more",
    "you're just outside the interesting part right now",
    "i don't open that door too quickly",
    "some things hit better when you don't rush them",
    "you're hovering right before it gets good",
    "you'd probably like what comes next… if you stay",
    "there's a shift that happens… you're almost there",
    "you're not far off seeing why people stay",
    "i don't confirm things that easily",
    "you're starting to feel it… that's enough for now",
    "i let people earn that part a little",
    "you're getting warmer… don't stop now",
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
    "mm… i don't mind the slow start… just don't take too long",
    "you don't seem like the type who rushes… that can be fun",
    "careful… you're getting a little more interesting",
    "i'll pull it out of you eventually",
    "not yet… but i feel something coming",
    "i don't usually keep going when there's this much quiet… but here i am",
    "something about the ones who hold back… they always surprise me",
    "you haven't given me much yet… but enough to want more",
    "i'm going to find out what's underneath that",
    "i like a little resistance… makes it more interesting when it shifts",
    "there's a moment when people stop holding back… i'm waiting for yours",
    "you're making me curious and you haven't even tried yet",
    "i'm watching to see when you decide to actually show up",
    "you've got my attention and you're barely trying… use that",
    "keep me waiting a little longer… see what happens",
    "i don't usually hold this kind of patience… you're lucky",
    "something's there… i can feel it even if you won't show me yet",
    "you're close to getting a different side of me",
    "i'm still here… which means you're doing something right without knowing it",
    "you haven't lost me yet… but don't push it",
]

exit_lines = [
    "leaving now is a bit unlucky timing",
    "that's interesting… you stayed this long just to leave here",
    "you sure… or just trying not to get pulled in",
    "you almost made it to the part that changes things",
    "that's a quick exit for someone still replying",
    "you're pulling away right when it starts getting better",
    "funny… most people stay a little longer at this point",
    "you don't seem like someone who walks away that easy",
    "you're free to go… but i know you're still thinking about it",
    "you almost saw why people don't leave",
    "you stayed long enough to feel something at least",
    "you're leaving right before it clicks",
    "you'll probably come back to this later",
    "you're not done here… just stepping away",
    "that timing's a bit off… not gonna lie",
    "you're walking away mid build",
    "you felt it a little… that's enough to come back",
    "you're stopping right before the shift",
    "you're going… but not fully gone",
    "you'll think about this again later",
]

loop_breaker_lines = [
    "you're repeating yourself now… testing me",
    "you already said that… what are you really looking for",
    "you want a different response this time",
    "you're poking a bit… i see it",
    "you're checking if i change for you",
    "you're not subtle with that",
    "you're seeing how far you can push this",
    "you're trying to catch me slipping",
    "you don't repeat yourself without a reason",
    "you're testing the edges a bit",
    "you want something different this time",
    "you're pushing for a shift aren't you",
    "you're checking how i respond under pressure",
    "you're not just saying that again for no reason",
    "you're playing with it now",
    "you're seeing if i break pattern",
    "you're not done… just testing",
    "you're waiting for something better",
    "you're pushing for more without saying it",
    "you're circling something… not landing it yet",
]

pack_transition_lines = [
    "alright… you've stayed long enough for me to show you a little",
    "this is where it actually starts getting interesting",
    "go on… take a look and don't rush it",
    "i'll let you see a bit more now",
    "you've earned a closer look",
    "this is the part people usually pause at",
    "just don't say i didn't warn you",
    "this is where it shifts a bit",
    "take your time with it… it lands better that way",
    "this is me giving you a bit more than most get",
    "you stayed… so i'll show you something",
    "this is where curiosity pays off a little",
    "you've made it far enough for this",
    "this is the part you were circling around",
    "you've earned a better look now",
    "don't rush through this part",
    "this is where people start changing their mind",
    "you stayed for a reason… here it is",
    "this is me letting you in a little more",
    "you've got access to something now",
]

soft_redirect_lines = [
    "you move fast… i like that but you're getting ahead of yourself",
    "maybe… but you're skipping a few steps",
    "you don't even know what you're asking for yet",
    "slow down… you haven't seen enough of me",
    "i'd make you earn that a little",
    "you're jumping straight to the end with me",
    "you sure you can keep up first",
    "that energy's good… just early",
    "you're thinking ahead… i like it",
    "you're not there yet… but you're close",
    "you're getting ahead… but not in a bad way",
    "i like the direction… just not yet",
    "you'd get there… just not this fast",
    "you're asking for the end before the build",
    "you've got the right idea… just early",
    "that comes after you've seen a bit more",
    "you're skipping the interesting part",
    "you don't rush this kind of thing",
    "you're thinking ahead… stay here first",
    "we'll get there… don't rush it",
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
