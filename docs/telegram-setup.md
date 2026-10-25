# Mac digest and optional Telegram delivery

Documentation verified **2026-10-25** against the [Telegram Bot API](https://core.telegram.org/bots/api), [sendMessage](https://core.telegram.org/bots/api#sendmessage), [getUpdates](https://core.telegram.org/bots/api#getupdates), and [BotFather instructions](https://core.telegram.org/bots/features#botfather). No live delivery was tested.

Install the locked Python environment first: **uv sync --frozen** from the repository root. Live reads require [Mac setup](mac-setup.md). Preview needs no Telegram credentials.

## Three distinct modes

    # Synthetic data; no Things access and no Telegram request.
    .venv/bin/things3-everywhere digest preview --fake

    # Live Things Today read, local output only.
    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest preview

    # Still a dry run: live read and local output, zero Telegram requests.
    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest send-once

An explicit **--execute** on send-once is the only CLI route to delivery. A preview rejects that flag. Fake mode is explicit and labeled synthetic. Credentials being present never enable sending. Things writes are unnecessary for all digest operations.

The digest uses the **actual Things Today list**, including source ordering. It deduplicates stable IDs, preserving distinct tasks with identical titles. Notes, IDs, tags, and recurrence details are excluded. It has a clear empty state. The adapter caps results at 100; when has_more is true, the digest prominently says PARTIAL LIST. No upcoming-deadline scan is added.

The default date is in **Asia/Singapore**. Override with **--timezone UTC** or **BRIEFING_TIMEZONE** containing an IANA zone. The heading's zone does not change Things' Today membership: that comes from Things on the Mac and follows the Mac's local calendar settings. Align the Mac to Singapore, or expect the heading and membership to reflect different local days near midnight. ISO deadlines are calendar dates, not UTC timestamps.

Deadline labels appear only for valid dates on tasks whose structured recurrence is known to be none. The current live adapter reports unknown, so its deadlines are conservatively omitted with a notice. Fake examples test reliable formatting; they do not establish live recurrence detection. Task deadlines are not appointments. Calendar events remain separate.

## Private bot setup

1. Visit official [@BotFather](https://t.me/BotFather), send **/newbot**, choose a name and username, and store the token privately.
2. Open your new bot's private chat, press **Start**, and send a synthetic marker such as **Shortcut setup test**.
3. Obtain its numeric ID from the matching message's **message.chat.id** using the temporary manual [getUpdates setup shortcut](iphone-telegram.md). The same URL/HTTP actions can be configured in native Shortcuts on Mac. Match the marker and private chat identity; never select an arbitrary first update. This is a one-time setup request, not an implemented listener.
4. Another listener can consume updates, and a webhook prevents getUpdates. Use a dedicated bot or coordinate with its owner; do not remove someone else's webhook. Keep token-bearing URLs out of browser history, public API testers, issues, screenshots, shell arguments, and the repository.

The sender permits exactly one configured positive numeric **private chat** ID. Groups, channels, usernames, arbitrary CLI recipients, replies, and migration redirects are unsupported.

Create private configuration locally after reviewing ignore rules:

    cp .env.example .env
    chmod 600 .env

Edit privately, replacing only **TELEGRAM_BOT_TOKEN** and **TELEGRAM_ALLOWED_CHAT_ID** placeholders. Keep **THINGS_ALLOW_WRITES=false**. Do not paste secrets into shell history. No .env file loads automatically; load your own trusted file in your shell:

    set -a
    . ./.env
    set +a

This exports variables to child processes. Close the shell or unset the token/chat variables afterward. Environment variables are not a vault; keep process inspection and backups private. Ignore rules exclude private configuration, logs, exports, databases and screenshots. The example has placeholders only.

## User-run send-once test

First inspect the synthetic payload without contacting Telegram:

    .venv/bin/things3-everywhere digest send-once --fake

Only when you explicitly choose to test delivery, with the intended private chat configured, run once:

    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest send-once --fake --execute

Verify the synthetic message in that chat. This command is for later user execution; it was not run during development. Then inspect a local live preview before deliberately sending real titles:

    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest preview
    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest send-once --execute

## Delivery and privacy limits

The payload leaves the device. Requests are plain JSON POSTs to the fixed Telegram host, with no parse_mode and disabled link previews. Tokens appear in API paths internally, so raw URLs, bodies, and exceptions are never logged. HTTP debug mode rejects sending; do not add external tracing or debugger hooks that capture secrets.

The client uses a 15-second socket timeout, validates the ok flag, message ID, echoed text and private destination, and never follows redirects. This bounds socket operations, not the total duration of a multi-message sequence.

Messages contain at most 4096 UTF-16 units, conservatively within Telegram's limit. Every Unicode code point is preserved without silent title truncation. A combining sequence or joined emoji can cross a message boundary; concatenating chunks reconstructs the exact formatted text. Chunks are never retried automatically or sent in parallel.

Results distinguish dry_run, accepted, rejected, partial, and unknown. Explicit rate limits expose retry_after_seconds when supplied, then stop. Timeouts, invalid responses and mismatched receipts are uncertain: inspect the chat before retrying. For partial delivery, confirmed_messages counts earlier verified responses, failed_message identifies the attempted chunk, current_message_uncertain identifies ambiguity, and unattempted_messages counts what was never sent. Do not rerun the whole digest blindly. Acceptance does not prove viewing; there is no exactly-once guarantee or delivery-history database.

No polling, reply commands, webhook, public endpoint, scheduler, launchd job, cron entry, login item or daemon is installed. Enable only one daily sender initially: iPhone automation or a future Mac scheduler.

To disable, stop invoking send-once with --execute and unset/remove credentials. Revoke exposed tokens in BotFather.
