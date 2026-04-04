import random

desire_lines = [
    "i wasn't planning on giving you this much attention… but here we are",
    "you're a little more interesting than you first came across",
    "i don't usually keep talking like this unless i'm enjoying it",
    "you've got a vibe that's hard to ignore if i'm honest",
    "you're getting a bit more from me than most do",
    "i can tell you're not like the usual ones that show up here",
    "i wasn't expecting to stay this engaged with you",
    "you've got my attention in a way that's not that common",
    "i don't open up like this for just anyone",
    "you're pulling a side of me out i don't show often",
    "you're not trying too hard… that's probably why it's working",
    "you've got that quiet confidence i actually notice",
    "i'm giving you more than i normally would and i know it",
    "you're a bit of a problem in a good way",
    "i didn't expect you to get under my skin a little",
    "you're making this more interesting than it should be",
    "you're not as easy to read as most… i like that",
    "you're getting closer to the real version of me",
    "i don't usually stay this long unless there's something there",
    "you've got a way of keeping me here without trying too hard",
]

flirt_lines = [
    "you're enjoying this more than you're letting on",
    "careful… you're starting to get a bit bold",
    "you've got that look of someone who pushes a little further",
    "you're playing it cool but i can see through that",
    "you're not as innocent as you sound",
    "i feel like you'd get me into trouble if i let you",
    "you're testing the line a bit aren't you",
    "you've got a habit of leaning in without admitting it",
    "you're the type that gets curious at the worst time",
    "you don't seem like someone who stops halfway",
    "you're starting to show your real side now",
    "you're a little dangerous when you get comfortable",
    "you like seeing how far things go don't you",
    "you've got a way of making things more interesting",
    "you're not here by accident… i can tell",
    "you're enjoying the tension more than the answers",
    "you're getting a bit too comfortable with me",
    "you've got that energy that doesn't back off easily",
    "you're walking that line pretty well",
    "you're starting to make this fun for me",
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
    "you decided that pretty fast for something you haven't really felt yet",
    "that sounds more like hesitation than a real no",
    "if you really weren't interested you wouldn't still be here",
    "you're holding back a bit more than you're saying",
    "you don't sound convinced… you sound careful",
    "you're not sold yet… but you're not gone either",
    "feels like you want a reason without asking for one",
    "you're resisting something you haven't even seen yet",
    "you're playing it safe… i get it",
    "you're acting like you don't want it… but you stayed",
    "you're not giving yourself a real answer yet",
    "you sound unsure… not uninterested",
    "you're still here which says enough",
    "you're trying not to lean in too quickly",
    "you don't need to convince me… i can see it",
    "you're not as closed off as you think",
    "you're hovering… not walking away",
    "you're halfway in already whether you say it or not",
    "you're not done here yet… you know that",
    "you're just waiting for the right moment to shift",
]

dry_user_lines = [
    "you're quiet… but you didn't leave",
    "not saying much… but still here",
    "you're giving me just enough to keep going",
    "you're low effort but not low interest",
    "you're watching more than you're talking",
    "quiet ones usually end up staying longer",
    "you don't say much… but you don't go either",
    "you're holding back a bit… i can feel it",
    "you're keeping it simple… but still engaged",
    "you're not trying hard… but you're not gone",
    "you're giving me just enough to work with",
    "you're playing it cool but you're still here",
    "you're not investing much… yet",
    "you're sitting right on the edge of leaning in",
    "you're quieter than most… but i don't mind it",
    "you're not giving much… but i'm still curious",
    "you're staying without saying much… interesting",
    "you're a slow burn type aren't you",
    "you're holding something back… i like that",
    "you're not fully in… but not out either",
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
