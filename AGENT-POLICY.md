<!-- ai-generated: 70% - Claude drafted the justifications, I reviewed each denial -->
# Agent policy: the `reviewer` sub-agent

The reviewer reads and comments. Each denied tool is a blast-radius decision: what could go wrong if a review
agent did it by mistake, and who should own that action instead.

- Bash(rm *): the reviewer reads and comments; deleting files is the author's decision, and a wrong delete of specs/ or DECISIONS.md destroys graded evidence.
- Bash(git push *): publishing changes the public repository the grader clones; only the author pushes, after running the checker on the committed tree.
- Bash(git tag *): tags are submissions and must never move after a receipt; a tag created or moved by an agent can void an attempt that still counts.
- Bash(docker *): containers, volumes and images live on the host; a review needs none of them, and a stray prune or down -v wipes local data and build cache.
- WebFetch: a review works from the repository and the published contract only; fetching arbitrary pages lets untrusted content steer the reviewer.
