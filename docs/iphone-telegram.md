# Optional Telegram delivery directly from iPhone

Documentation checked **2026-10-25**; no phone installation, Bot API call, or real send was performed. Build [the local briefing](iphone-shortcuts.md) first. This workflow needs internet and Things on the phone, but no Mac.

Sending shares titles and briefing text with Telegram and the selected chat. Use a private chat and omit notes. A token embedded in a shortcut can be exposed when shared, screenshotted, backed up, or inspected by someone with access. Never publish the configured shortcut or a token-bearing URL. Revoke exposed tokens through BotFather.

As in [Guide A](iphone-shortcuts.md), **literal** means typed text and **token** means an inserted variable. JSON key names such as **chat_id** are literal; their values below are tokens. Select inputs explicitly: a new Text or dictionary action can otherwise replace the previous output automatically.

## Private bot and destination

1. Open official [@BotFather](https://t.me/BotFather), send **/newbot**, and follow the name and username prompts. Save the token privately. [Telegram: bot creation](https://core.telegram.org/bots/features#botfather).
2. Open your new bot's private conversation and press **Start**. Send a synthetic marker such as **Shortcut setup test**. The bot cannot initiate your first conversation.
3. Create a temporary, manual setup shortcut. Add **Text** containing the token privately; rename its output **BotToken**. Add **URL**: literal **https://api.telegram.org/bot**, then **BotToken** token, then literal **/getUpdates?timeout=0**. This is one setup request, not a listener.
4. **Get Contents of URL**, input the URL action's token, method **GET**. In this temporary setup shortcut only, add **Quick Look** on its output to inspect the dictionary privately. **ok** must be true. In **result**, locate the update whose **message.text** matches the marker you just sent and examine **message.chat**. Check **type** is **private** and the conversation is yours. Copy **message.chat.id** from that exact update into private configuration. If the match is ambiguous, stop and use a new unique synthetic marker. Do not use an arbitrary first result, update_id, the bot's ID, or a forwarded sender's ID.
5. Delete the temporary setup shortcut or remove response-inspection actions afterward. Do not share/export the response.

A pre-existing webhook prevents getUpdates; another polling listener may consume updates. Use a dedicated bot or coordinate with its owner. Do not delete a webhook as a troubleshooting shortcut. For empty results, check bot identity and send a fresh marker yourself; never guess the destination. [Telegram: getUpdates](https://core.telegram.org/bots/api#getupdates).

## Manual send and response check

First complete the offline length preflight below. Then create a separate shortcut named **Things — Telegram briefing**, unscheduled. For the initial send test, use only **Text** with literal **Shortcut Test — synthetic delivery check**, then **Set Variable**, name **BriefingText**, value that Text output. Connect the Things-reading actions only after the synthetic send is verified. A standalone synthetic test avoids reading or accidentally sending personal titles during setup.

Add these actions after **Set Variable BriefingText**, keeping that variable bound to the message, not to the credentials or encoded text:

1. **Text**: private token, output renamed **BotToken**. Another **Text**: intended numeric private chat ID, output **AllowedChatID**. This is fixed configuration, never supplied by task text or a reply.
2. **If** **BriefingText** has no value, show a local notification and stop. **Base64 Encode** the **BriefingText** token, in Encode mode, with no line breaks if offered. **Count** Characters in the encoded output, renamed **EncodedCount**. If the output/count is absent or **EncodedCount** is **0**, stop. If **EncodedCount** exceeds **4000**, **Show Notification**, literal **Briefing too long; nothing sent. View it locally.**, then **Stop This Shortcut** (or Stop and Output with no output). Only a count from 1 through 4000 proceeds. Do not send the encoded output.
3. **URL**: literal **https://api.telegram.org/bot** + **BotToken** token + literal **/sendMessage**.
4. **Get Contents of URL**, input that URL token, expand options, **POST**, Request Body **JSON**. Add text key **chat_id** with **AllowedChatID** token and text key **text** with original **BriefingText** token. Omit **parse_mode**. Add dictionary **link_preview_options**, boolean **is_disabled** true, to avoid link previews. Rename the HTTP output **Response**.
5. **Get Dictionary Value**, key literal **ok**, dictionary **Response** token; rename **ResponseOK**. Use **If** with the Boolean value **true**, not the text string “true”. Explicit false means rejected; a missing/unreadable value means unverified. On either failure, show a fixed local message and stop. Inside the true branch, extract the receipt using the table below; every row is a separate Get Dictionary Value action with its own explicit input.
6. Use nested noninteractive **If** actions to require **MessageID** to be a number greater than zero, **ReturnedChatType** to equal literal **private**, **ReturnedChatID** to equal **AllowedChatID** (both treated as Text without rounding), and **ReturnedText** to equal **BriefingText**. Only inside the innermost success branch use **Show Notification**, literal **Telegram accepted the briefing.** Each failure branch shows **Delivery unverified; inspect Telegram privately.** During the manual test, also confirm receipt in the intended chat. Never notify with the URL, token, whole response, or full error description. Missing/malformed fields are failure, not success; a receipt does not prove that a person saw the notification.

| Literal key | Dictionary input token | Rename output |
| --- | --- | --- |
| result | Response | Result |
| message_id | Result | MessageID |
| text | Result | ReturnedText |
| chat | Result | ReturnedChat |
| id | ReturnedChat | ReturnedChatID |
| type | ReturnedChat | ReturnedChatType |

Apple documents JSON request bodies, dictionary lookup, and variable values. [Apple: API requests](https://support.apple.com/guide/shortcuts/apd58d46713f/ios), [dictionary values](https://support.apple.com/guide/shortcuts/get-dictionary-value-action-apdf01294032/ios), [variables](https://support.apple.com/guide/shortcuts/apda36b9018b/ios). Keep Quick Look and other interactive inspection actions out of the saved sending path.

### Offline length preflight — required before adding HTTP

The Base64 guard is this project's conservative design, not a Telegram requirement. For UTF-8 input, Base64's ASCII length bounds the original byte count, which bounds Unicode character/UTF-16-unit count. A 4000-character encoded limit allows at most 3000 original bytes. This avoids relying on how Shortcuts counts visible emoji. Apple's web pages checked here do not establish the Base64 action's encoding behavior; **the following phone checks remain unverified**. If the action or options are unavailable, or a check fails, retain the local notification workflow.

In a temporary shortcut containing **no URL or HTTP action and no credentials**, add Text → Base64 Encode → Count Characters. Use Quick Look locally to inspect the encoded output and count. Check literal **A** produces **QQ==** (4), and literal **😀** produces **8J+YgA==** (8). Check multiline and combined-emoji text round-trips unchanged through a second Base64 action set to Decode. These are synthetic expectations, not captured device results.

Exercise the guard with an empty Text and with 3001 literal A characters: build the latter using **Repeat** 3001 times → Text literal A → End Repeat → **Combine Text**, custom separator empty. It should encode to 4004 characters and take the stop branch. Replace the eventual HTTP action with a local notification **Would send** during this test; that notification must never run for empty or oversized input. Small input should reach it. Do not add HTTP until this wiring is correct.

Telegram sendMessage permits 1–4096 characters after entity parsing. This phone recipe **rejects an oversized briefing entirely**, with a local notice; it never silently truncates titles or sends partial chunks. Plain text avoids Markdown/HTML formatting issues. [Telegram: sendMessage](https://core.telegram.org/bots/api#sendmessage).

A failed network action can stop Shortcuts before the If runs. A timeout is ambiguous: the message may have arrived. Check the chat before retrying. An explicit **ok=false**, error code **429** response can include **parameters.retry_after**; wait that interval before a deliberate manual retry. Do not add an automatic retry loop or claim exactly-once delivery. [Telegram: response parameters](https://core.telegram.org/bots/api#responseparameters).

The Shortcuts network action's timeout and error display are controlled by iOS; this recipe does not claim the Mac client's timeout or redaction guarantees. Treat any system error screen as potentially containing the token-bearing URL: do not share it. If authentication is rejected, check the token privately in BotFather; for a chat rejection, recheck the fixed destination and that you started the bot. Never fall back to another chat automatically.

## Scheduling only after verification

After the synthetic send, connect Guide A's final **Set Variable BriefingText** to this send path, review the real briefing locally, and explicitly choose whether to run it manually. Keep the length guard and receipt checks. Then perform the separate locked-phone test in [Guide A](iphone-shortcuts.md), first with synthetic text again. The unattended path must have no alerts, choices, Quick Look, or Ask Each Time. Grant first-run network permission while unlocked. Phone play/automation execution has no CLI-style dry-run flag: adding the HTTP action makes a run send, so keep the local-only shortcut separately.

Enable only one daily sender: iPhone Telegram **or** a future Mac scheduler. This repository installs neither. Keep completion separate. Outbound sendMessage does not implement reply-to-edit, polling, webhooks, remote MCP, or cloud-only access to Mac Things.

To disable delivery, remove/disable the automation trigger or remove the HTTP action; the local briefing remains useful. Revoke an exposed token in BotFather.
