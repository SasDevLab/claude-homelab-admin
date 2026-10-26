---
name: homelab-end-session
description: Collects the session's lessons and files each in the right place before the conversation disappears. Use at the end of a session, before `/clear` ("end of session", "what did you learn?", "let's close").
---

# End of session

Run it **before** `/clear`: afterwards the conversation is gone and there
is nothing left to learn from.

Reread the session and answer four questions. For each, **make** the
change, do not propose it. If the answer is "nothing", say so in one line.

1. **What did I learn?** Mistakes paid for, measurements that disproved a
   written sentence, the owner's corrections. Only what would change
   behaviour in a future session: the summary of the work is in git.
2. **Do the documents need updating?**
   - `CLAUDE.md`: only the owner's rules, refusals and the way of working,
     in one or two lines with the date and a "Why". Keep it under ~20 KB:
     the session and every agent reread it on every turn. Stories go in
     the README. A sentence the session disproved is **corrected**, not
     contradicted by a new one beside it.
   - memory: facts that are not in the repository.
   - the generated inventory documents are never edited by hand: if the
     house changed, regenerate them.
3. **Do skills need updating or creating?** A repeated procedure or a
   trap goes into the skill of its piece (the "before touching" table of
   `CLAUDE.md`), not into `CLAUDE.md`. A new skill only for a procedure
   that will come back. **Before creating one, search whether it already
   exists in public**: `DISABLE_TELEMETRY=1 npx -y skills find <words>`.
   Search only: a skill found is **proposed** to the owner with name,
   author and installs, after reading its `SKILL.md`. It is not installed
   on your own.
4. **Does it need a hook?** Only for a mistake that a written rule failed
   to prevent twice: a hook is run by the machine, a rule has to be
   remembered. A new hook is **proposed** to the owner, not installed on
   your own.

At the end: `git add` with file names, one commit, and the push of the
repositories this session is allowed to push (`git status -sb` shows
commits not sent; check the visibility with `gh api repos/<owner>/<repo>
--jq .visibility` before pushing). A repository the owner keeps out of
this session stays out: its push is theirs, and no other road is looked
for.

Then a few lines to the owner: what was written and where, and what was
pushed.
