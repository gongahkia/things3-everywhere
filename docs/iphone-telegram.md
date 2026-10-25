# Optional Telegram delivery directly from iPhone

Documentation checked **2026-10-25**; no phone installation, Bot API call, or real send was performed. Build [the local briefing](iphone-shortcuts.md) first. This workflow needs internet and Things on the phone, but no Mac.

Sending shares titles and briefing text with Telegram and the selected chat. Use a private chat and omit notes. A token embedded in a shortcut can be exposed when shared, screenshotted, backed up, or inspected by someone with access. Never publish the configured shortcut or a token-bearing URL. Revoke exposed tokens through BotFather.

## Private bot and destination

1. Open official [@BotFather](https://t.me/BotFather), send **/newbot**, and follow the name and username prompts. Save the token privately. [Telegram: bot creation](https://core.telegram.org/bots/features#botfather).
2. Open your new bot's private conversation and press **Start**. Send a synthetic marker such as **Shortcut setup test**. The bot cannot initiate your first conversation.
3. Create a temporary, manual setup shortcut. Add **Text** containing the token privately; rename its output **BotToken**. Add **URL**: literal **https://api.telegram.org/bot**, then **BotToken** token, then literal **/getUpdates?timeout=0**. This is one setup request, not a listener.
4. **Get Contents of URL**, **GET**. Inspect the dictionary locally: **ok** must be true. In **result**, locate your marker's update and examine **message.chat**. Check **type** is **private** and the conversation is yours. Copy **message.chat.id** from that exact update into private configuration. Do not use an arbitrary first result, update_id, the bot's ID, or a forwarded sender's ID.
5. Delete the temporary setup shortcut or remove response-inspection actions afterward. Do not share/export the response.

A pre-existing webhook prevents getUpdates; another polling listener may consume updates. Use a dedicated bot or coordinate with its owner. Do not delete a webhook as a troubleshooting shortcut. For empty results, check bot identity and send a fresh marker yourself; never guess the destination. [Telegram: getUpdates](https://core.telegram.org/bots/api#getupdates).

## Manual send and response check

Duplicate the briefing as **Things — Telegram briefing**, unscheduled. Initially replace the final BriefingText with literal **Shortcut Test — synthetic delivery check**; restore the actual briefing token after testing.

Add these actions after its final Text action:

1. **Text**: private token, output renamed **BotToken**. Another **Text**: intended numeric private chat ID, output **AllowedChatID**. This is fixed configuration, never supplied by task text or a reply.
2. **Base64 Encode** the **BriefingText** token. Choose no line breaks if offered. **Count** Characters in the encoded output. If count exceeds **4000**, **Show Notification**, literal **Briefing too long; nothing sent. View it locally.**, then **Stop This Shortcut**. Do not send the encoded output.
3. **URL**: literal **https://api.telegram.org/bot** + **BotToken** token + literal **/sendMessage**.
4. **Get Contents of URL**, expand options, **POST**, Request Body **JSON**. Add text key **chat_id** with **AllowedChatID** token and text key **text** with original **BriefingText** token. Omit **parse_mode**. Optionally add dictionary **link_preview_options**, boolean **is_disabled** true.
5. **Get Dictionary Value**, key literal **ok**, dictionary the HTTP action's output token; rename **ResponseOK**. Get key **result** from the same response; rename **Result**. From Result get **message_id** and **text** into **MessageID** and **ReturnedText**. From Result get **chat**, then its **id**, into **ReturnedChatID**.
6. Use nested noninteractive **If** actions: ResponseOK is true, MessageID has a value, ReturnedChatID equals AllowedChatID (as text), and ReturnedText equals BriefingText. Only inside the innermost success branch use **Show Notification**, literal **Telegram accepted the briefing.** Each failure branch shows **Delivery unverified; inspect Telegram privately.** During the manual test, also confirm receipt in the intended chat. Never notify with the URL, token, whole response, or full error description. Missing/malformed fields are failure, not success.

Apple documents JSON request bodies and variable values in Get Contents of URL. [Apple: API requests](https://support.apple.com/guide/shortcuts/apd58d46713f/ios), [Apple: variables](https://support.apple.com/guide/shortcuts/apda36b9018b/ios).

The Base64 check is a conservative design choice: its ASCII length bounds original UTF-8 byte count, which bounds Unicode character/UTF-16-unit count. It avoids ambiguous emoji counting in Shortcuts. Verify the action's Unicode behavior with synthetic emoji on your device; if unavailable or uncertain, retain local-only delivery.

Telegram sendMessage permits 1–4096 characters after entity parsing. This phone recipe **rejects an oversized briefing entirely**, with a local notice; it never silently truncates titles or sends partial chunks. Plain text avoids Markdown/HTML formatting issues. [Telegram: sendMessage](https://core.telegram.org/bots/api#sendmessage).

A failed network action can stop Shortcuts before the If runs. A timeout is ambiguous: the message may have arrived. Check the chat before retrying. An explicit **ok=false**, error code **429** response can include **parameters.retry_after**; wait that interval before a deliberate manual retry. Do not add an automatic retry loop or claim exactly-once delivery. [Telegram: response parameters](https://core.telegram.org/bots/api#responseparameters).

## Scheduling only after verification

Restore BriefingText, review locally, run manually, then perform the separate locked-phone test in [Guide A](iphone-shortcuts.md). The unattended path must have no alerts, choices, or Ask Each Time. Grant first-run network permission while unlocked.

Enable only one daily sender: iPhone Telegram **or** a future Mac scheduler. This repository installs neither. Keep completion separate. Outbound sendMessage does not implement reply-to-edit, polling, webhooks, remote MCP, or cloud-only access to Mac Things.

To disable delivery, remove/disable the automation trigger or remove the HTTP action; the local briefing remains useful. Revoke an exposed token in BotFather.
