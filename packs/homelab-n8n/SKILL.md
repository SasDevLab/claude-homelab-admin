---
name: homelab-n8n
description: Traps paid for in n8n 2.x. Use before creating or changing an n8n workflow, a Code node, a Telegram node, or a workflow that calls a local model.
---

# Changing an n8n workflow

Every line here cost hours once. Read the section that matches the change
before making it.

## The road: the MCP server

**Change workflows through the n8n MCP server**: `update_workflow`, then
`publish_workflow`. The change runs from the next execution, no restart.
A raw `PUT` with the API key on a workflow that writes was refused by
Claude Code's own action check ("Modify Shared Resources"), while the MCP
pair passed at once for the same change. Keep the API key for reading.

**n8n runs the version it holds in memory.** A change written into the
database runs only after `docker restart n8n`. Once a node was removed in
the database, checked gone, reported as done, and it ran all night.

If the database is the only road, n8n 2.x needs three writes:
`workflow_entity.nodes`/`connections`, a new row in `workflow_history`, and
`workflow_entity.activeVersionId` pointing at it. A new workflow also needs
a row in `shared_workflow`, or the UI does not show it.

**`test_workflow` tests the saved draft, not the active version**, and it
pins HTTP and Telegram nodes instead of running them. It proves the text
is built right, not that the message leaves. Send a real test message
apart, and tell the owner the real send is "not tested" until the first
real execution.

**A workflow that writes goes live in two steps**: `DRY_RUN=true`,
published, one real dry run; then `false`. Going straight to `false` was
refused as "Blind Apply"; the two steps passed.

**A one-line fix in a Code node does not need an agent** (an agent on a
30-node workflow costs 100-180k tokens). `GET` the workflow with the API
key, replace an **exact** string in `jsCode` (assert it appears once),
`PUT` with only `name`, `nodes`, `connections`, `settings`. A `403
insufficient_api_key_scope` is expected: the key lacks
`workflow:activate`, the draft is saved and the answer carries the
`versionId`. Then `publish_workflow` from MCP with that `versionId`.

**Stopping a running execution**: the API key gets `Forbidden` on
`/executions/<id>/stop` and the MCP server has no command for it. What is
left is `docker restart n8n`, only when nothing else runs; the execution
stays `crashed` and trips any "failed executions" alarm.

**Credentials through the API can only be created**: `POST
/api/v1/credentials` works, `PATCH`/`PUT`/`DELETE` give 403/405. A wrong
one is remade under another name, the old one removed by hand in the UI.

## Code nodes

- **A Code node that waits stays under the task runner timeout**
  (`N8N_RUNNERS_TASK_TIMEOUT`, 300 s by default in the compose here).
- **A Code node with real logic carries its own test**: a reserved input
  (`{"test": "deadline"}`) runs the cases and throws if one fails. Before
  publishing, run it outside n8n: paste the code into a function and pipe
  it to `docker exec -i n8n node`. A syntax error published breaks the
  branch for everyone. Every sentence the owner finds wrong becomes a case.
- **Attached files are not in the data**: `items[i].binary[k].data` is a
  13-character reference. The bytes: `await
  this.helpers.getBinaryDataBuffer(i, key)`.
- **Backslashes do not survive** heredoc to file to n8n: write
  `String.fromCharCode(10)` instead of `'\n'`.
- **Long prompts do not go into expressions.** A 687-character role inside
  `jsonBody` made a malformed body (`invalid syntax` from the model
  server). Keep the text in a Code node and pass it by reference.
- **Sums, dates and "fits or not" are done by code**, not asked of the
  model. Small local models get the sum right and the conclusion wrong.

## Nodes and items

- **Renaming a node breaks whoever cites it**: every `$('Name')` changes
  with it, or *"Node 'X' hasn't been executed"*.
- **An HTTP node returns only its own response.** Fields from before are
  taken back with `$('Previous').all()[i].json`. Forgetting this once sent
  empty strings to a model, which then described a photo it never saw.
- **Match by origin, never by position** after an `if` or a node that can
  fail: `$('Node').itemMatching(i)`, not `$('Node').all()[i]`. And an API
  answer that is a list (one result per photo) is split into one item per
  entry: the `id` you read is the photo's, not the album's.
- **A query that returns no rows does not stop the workflow**: n8n sends
  one empty item on, and the next nodes run. A model was queried on
  nothing every ten minutes, 43 s each. Filter:
  `return items.filter(i => i.json && i.json.key_field);`
- **Branches of a shared trigger interleave**, they do not run one after
  the other.
- **`executeOnce` on a summary node gives it one item**: a report said "1
  changed" out of 90. A Code node in `runOnceForAllItems` already sees
  everything; keep `executeOnce` for a real single pass (a DELETE before an
  INSERT).
- **An HTTP node with several items sends them together.** When order
  matters (creating nested folders over WebDAV), the child arrives before
  its parent and gets 409. Set `options.batching.batch.batchSize: 1`.
- **A `%` in a query built with Python's `%` operator breaks it**, even
  inside an SQL comment (`TypeError: %o format`). Write `%%`.

## Reading what happened

- **"success" does not mean it worked.** With error branches
  (`continueErrorOutput`, `continueRegularOutput`) a run ends `success`
  when the query failed: once in half a second, with a broken query. Look
  at which nodes ran, what they produced, and how long it took.
- **Log the real error, not an explanation.** "the model saw nothing"
  covered a `socket hang up` for a week: 124 items given up after three
  tries because of the network. Save the message that comes back, and a
  network fault does not use up the retries.
- **A workflow that runs often does not save successful executions**
  (`saveDataSuccessExecution: none`). Its executions still sit as
  `running` in `execution_entity` for a few minutes and then vanish: a
  "busy?" check counts them as work in progress, so exclude it by id. A
  successful run leaves no trace: prove the schedule restarted by its
  effect, not by its executions.
- **Large executions**: `get_workflow_execution` with `includeData`
  overflows even with `nodeNames`; the result lands in a file, read it
  with `python3` (`data.resultData.runData.<node>[0].data.main[0]`).
- **Which nodes call a service is told by the live workflow**, not the
  exported copy: copies fall behind. Read the database with `mode=ro`.

## Telegram

- **No Telegram Trigger node, ever** if anything else reads the bot: on
  publish it registers a webhook and takes the bot away from its reader.
  One bot, one reader; that reader hands updates to n8n.
- **The HTTP Request node cannot use the `telegramApi` credential**: the
  token goes in the URL. For methods the Telegram node lacks
  (`setMyCommands`, `getUpdates`) work outside n8n, token from the vault.
- **The inline keyboard does not take an expression** (neither the block
  nor `rows`): the message goes out without buttons. One node per number
  of buttons.
- **`answerCallbackQuery` first, with "continue on fail"**: after a few
  seconds, or with a fake test id, Telegram answers "query is too old".
- **Text with file names goes in HTML, not Markdown**: the underscores of
  `IMG_..._098.jpg` break Markdown (`can't parse entities`) and nothing
  is sent. `parse_mode: HTML`, escape `<`, `>`, `&`.
- **Every Telegram node gets `retryOnFail`** and cannot stop the rest of
  the workflow or fall into the error branch: from a home line delivery
  failed about one time in three.

## A local model on another device (Ollama)

Measured with Ollama on a 5.6 GB Android phone; the shape holds for any
small host.

- **Every call carries `options.num_thread`.** Without it Ollama used 8
  threads on a big.LITTLE CPU and wrote 0.5 tokens/s; with 2-6, 3-5
  tokens/s. A photo went from 210 s to ~80. Slow model? Look at the
  `llama-server` process first, not load average (on Android it reads
  0.00 under full load).
- **`keep_alive: 0` on each call** when memory is tight: otherwise the
  server keeps past prompts, 150 MB per photo, until it is killed.
- **A run ends before the next starts**: size batches to the trigger.
  Overlapping runs never unload the model. Two workflows on the same
  device take turns: write "BUSY"/"FREE" in a log the other reads first.
- **Read the model's weight before pulling it**: sum the `layers` in the
  manifest (`registry.ollama.ai/v2/library/<name>/manifests/<tag>`); the
  web page may leave out the vision projector. Near the device's limit it
  saturates or reboots. Announce a load test to the owner first.
- **A model can echo the instruction as its answer.** A prompt with a
  `<placeholder>` example got the placeholder back 4 times in 20, saved as
  good. Reject it like an empty answer. A working prompt changes only
  after a test on real data.
- **Compare models with the current one first**, in the same conditions:
  measured last after ten hours, the incumbent turned out the best. And a
  multiple-choice benchmark alone misleads: repeat conversational traps
  three times, answers change.

## Other services seen from n8n

- **From the n8n container**, services on other compose networks are
  reached by container name once their network is joined in n8n's
  compose; the host is the Docker bridge gateway (`host.docker.internal`
  timed out here).
- **SearXNG returns 0 results for ~5 minutes** after many quick searches
  (engines rate-limit it): pause a few seconds between searches.
- **`claude -p` from a workflow costs ~10k tokens per call**, even for
  "ok": batch the texts into one call a day.
- **Google People API**: `updateContactPhoto` wants **PATCH** (POST gives
  404 and writes nothing). An OAuth app "in testing" gives tokens that
  expire in 7 days; after "Publish app" the credential must be
  **reconnected** in n8n. `people/me/connections` returns only contacts
  saved to Google, not the phone's local ones: match by id or phone
  number, never by name.

## After the change

1. `docker restart n8n` only if the database was the road, and only with
   no execution running.
2. Export **from the live workflow** into the repository; stale copies
   once kept the wrong chat id for weeks.
3. If what the workflow does changed, update the automation inventory.
4. Wait for a real execution and look at it.
