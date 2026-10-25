# iPhone-only Things Shortcuts

Documentation checked **2026-10-25**. These are build instructions, not an installed or device-tested shortcut. No downloadable shortcut is supplied. Native Things actions run on the iPhone; a Mac, MCP server, bot, and Things Cloud are unnecessary for this local workflow. Cross-device sync is separate and has not been verified here.

Install Things for iPhone and Apple's Shortcuts app. These actions debuted in Things 3.17 with iOS 16; use a current compatible release. Action labels and automation screens vary with iOS, Things, and language. Select the matching iOS version in Apple's guide. [Things announcement](https://culturedcode.com/things/blog/2023/01/shortcuts-reloaded/), [Apple Shortcuts guide](https://support.apple.com/guide/shortcuts/welcome/ios).

**Literal** means type the text. **Token** means insert an action's output using Select Variable/Magic Variable; do not type its name. Tap a token to choose its property, such as Title or ID, or to rename it. Preserve a Things Item as an Item when it will later be edited: extracting Title produces text, not a task reference. [Apple: adjust variables](https://support.apple.com/guide/shortcuts/apda36b9018b/ios).

## A. Read-only briefing

Name the shortcut **Things — Today's date filters**. Its two sections are:

| Section label | Every filter must match |
| --- | --- |
| Scheduled today | Type is To-Do; Status is Open; Start Date is Today |
| Deadline field today | Type is To-Do; Status is Open; Deadline is Today |

These are independent native **Find Items** queries. Neither is the actual Things Today list. The documented filters do not expose that list; **Open List** displays it but does not retrieve its contents. These queries exclude earlier start dates, overdue deadlines, and anything without the corresponding date. A task matching both appears in both sections intentionally. Projects, completed tasks, and canceled tasks are excluded. Compare against these filters when testing, not against Today's row count. [Things actions and filters](https://culturedcode.com/things/support/articles/9596775/).

The Deadline property is not always the final deadline for repeating items that start early: Things documents that it can represent the instance's early appearance date; the template's deadline offset is unavailable. Keep the label **Deadline field today** and inspect recurring items in Things. Do not infer recurrence, appointments, or reminder times.

Build these actions in order. Search the Things app's action category for its actions.

1. **Find Items** (Things): add the Scheduled today filters above, joined by **All**. Sort by **Title**, ascending. Limit **50**. Ensure it is finding in Things, not filtering a previous action's input. Rename its output token **ScheduledItems**.
2. **Count** Items in the **ScheduledItems** token. Rename output **ScheduledCount**.
3. **If** the **ScheduledCount** token is **0** (literal number).
4. Inside If, **Text**: literal **No open tasks have a start date of today.** Then **Set Variable**, name **ScheduledBody**, value that Text action's token.
5. In Otherwise, **Repeat with Each**, input **ScheduledItems** token.
6. Inside Repeat, **Text**: type literal **•** and a space, then insert **Repeat Item** token. Tap that token and select the Things Item's **Title** property. Do not type the words “Repeat Item”.
7. After End Repeat, **Combine Text**: input that loop's **Repeat Results** token, separator **New Lines**. **Set Variable** **ScheduledBody** to the Combined Text token. End If.
8. **Find Items** again: use the Deadline field today filters, **All**, sort Title ascending, Limit **50**. Clear any inherited input so it searches Things independently. Rename output **DeadlineItems**.
9. **Count** Items in **DeadlineItems**; rename **DeadlineCount**.
10. **If** **DeadlineCount** is literal **0**: **Text** literal **No open tasks have a deadline field of today.** **Set Variable** **DeadlineBody** to that Text token.
11. Otherwise, **Repeat with Each** **DeadlineItems**. Inside, **Text** literal **•** and a space followed by **Repeat Item → Title** token. After the loop, **Combine Text** its **Repeat Results**, New Lines, then **Set Variable** **DeadlineBody** to Combined Text. End If.
12. **Current Date**, then **Format Date**, short date, Time Format **None**. Rename output **DisplayDate**. This string is only for display, never for a Things date filter.
13. **Text**, as below. Angle brackets stand for tokens to insert; headings and the limit notice are literal text:

        Things date filters — <DisplayDate>
        Scheduled today:
        <ScheduledBody>

        Deadline field today:
        <DeadlineBody>

        Up to 50 items per section. If a section reaches 50, more may exist.
        These filters exclude earlier dates; open Things for the full Today list.

14. **Set Variable** **BriefingText** to that final Text token.
15. **Show Notification**: body **BriefingText** token; expand options, Title literal **Things date-filter briefing**.

The configured limit is deliberate; Things' documented hard maximum is 500. The notice prevents a capped result from looking complete. Notification previews can visually shorten long text. Keep Show Alert, Quick Look, menus, Ask for Input, and confirmations out of this unattended path. **Show Notification** continues immediately; **Show Alert** waits. [Apple: notifications](https://support.apple.com/guide/shortcuts/use-the-show-notification-action-apd2175adcab/ios).

For Today equality, use native **is Today**. Things warns against using **is between** to emulate Today, and against **is in the last** date filters. If a later variant needs a boundary, pass native **Adjust Date → Get Start of Day** output; do not format query dates into text or use Ask Each Time for dates. [Things date caveats](https://culturedcode.com/things/support/articles/9596775/#working-with-dates).

### Manual test first

Run with the play button while unlocked. Grant only the Things/Shortcuts and notification permissions requested. Inspect the filter chips again after reopening the editor. Compare titles privately with Things. Verify no task changed.

Use a disposable, non-repeating **Shortcut Test** task that you create and control in Things. In a temporary test copy, add Title is **Shortcut Test** to both Find actions. Set its start date or deadline manually in Things to exercise each section. For the empty case, use Title is **Synthetic No Match** in that copy. Check each section's empty text. Remove test filters before real use. Keep screenshots and task output out of the repository.

### Daily 8:30 AM and a separate locked-phone test

Use **Time of Day**, **8:30 AM**, **Daily**, while the phone's time zone is **Singapore / Asia/Singapore**. This is a device-local schedule. Recheck after travel; this guide does not convert fixed Singapore time on a phone in another zone. Task date comparisons also follow the phone's local day.

On versions with an **Automation** tab, create a personal automation, select Time of Day, 8:30 AM, Daily, choose **Run Immediately** where offered, and select this shortcut (or use **Run Shortcut**). Older screens may instead require disabling **Ask Before Running**. Apple's current iOS 27 guide describes opening the shortcut, **Edit → Automation**, then choosing the trigger; **Edit → Info → Privacy → Allow Running When Locked** is version-specific. Match the guide to your installed OS. [Apple: event triggers](https://support.apple.com/guide/shortcuts/apd932ff833f/ios), [Apple: automation setup](https://support.apple.com/guide/shortcuts/apdfbdbd7123/ios).

First set the trigger a few minutes ahead. Close the editor, lock the phone, and wait without touching it. Record privately whether a notification arrives, its time, and whether an unlock/permission prompt blocks it. Repeat under your usual Focus and notification settings. Restore 8:30 AM and check the next morning. A successful manual run does not establish locked-device delivery; timing remains unverified until tested.

Enable only one daily sender initially. The local-notification workflow stands alone; avoid enabling both an iPhone Telegram sender and a future Mac digest schedule. Nothing is scheduled by this repository.

## B. Complete one disposable task, manually

Create a separate shortcut named **Things — Complete one test task**. Do not automate it or call it from the briefing. Personally create or identify a non-repeating **Shortcut Test** to-do in Things first; do not use a repeating template or an instance whose effects are uncertain.

1. **Find Items** (Things), **All**: Type is **To-Do**, Status is **Open**, Title is literal **Shortcut Test**. Sort Title, limit 20. These are candidates, not mutation targets.
2. **If** Find output has no value: **Show Notification**, literal **No matching test task.** Then **Stop This Shortcut** (Stop and Output on some versions, no output). End If.
3. **Choose from List**: input the **Find Items** token as Things Items. **Select Multiple OFF**. Prompt literal **Choose the disposable task to complete**.
4. **Set Variable** **SelectedTask** to **Chosen Item**. Preserve the whole Things Item; do not select Title here.
5. **If** **SelectedTask** has no value, stop the shortcut. Canceling selection must not proceed to editing.
6. **Show Alert**, **Show Cancel Button ON**. Title literal **Complete this one task?** Message: literal **Title:** + **SelectedTask → Title** token, newline, literal **ID:** + **SelectedTask → ID** token, then literal **Continue only if this is your disposable, non-repeating test task. Changes cannot be undone by this shortcut.**
7. **Edit Items** (Things): **Set**, **Status**, **Completed**. Explicitly set Items to the stored **SelectedTask** token as a whole Item. Inspect its source: it must not be Find Items, all candidates, the alert text, or a Title string.
8. **Show Items** (Things): input **SelectedTask**, then verify that exact task is completed in Things. If navigation differs, find it in Logbook and compare its ID. Reaching the end is not independent proof of the resulting state.

Test cancellation at the picker and alert first; verify nothing changed. Then select the identified task, confirm, and verify only it changed. Duplicate titles require inspecting the displayed stable ID, not selecting the first match.

Cultured Code explicitly says **Edit Items changes cannot be undone**. Cancel works only before editing. Manually setting a task back to Open is another mutation and may not restore logging, dates, or recurrence effects; archived-heading items can remain in Logbook. [Things editing and known issues](https://culturedcode.com/things/support/articles/9596775/), [Apple: cancelable alerts](https://support.apple.com/guide/shortcuts/use-the-show-alert-action-apdb9661c761/ios).

No rescheduling recipe is included: Start and Deadline are distinct, but their device-specific behavior has not been exercised here. First establish completion on the disposable non-repeating item.

## C. Optional outbound Telegram

Follow [phone Telegram delivery](iphone-telegram.md) after the local briefing works. It adds an external data destination; replies will not edit Things.

## Optional calendar appendix — unverified recipe

Calendar events are separate objects. Things deadlines are not appointments, and changing a task does not edit an event.

Explore native Calendar actions separately, with Calendar permission and explicit selection of the intended calendars. The desired overlap condition is **event start < next local midnight AND event end > current local midnight**. A start-date-is-today query misses events in progress across midnight. Preserve all-day status, account for all-day end boundaries, and display multi-day events once per daily section.

Exact current Calendar action fields, overlap filtering, recurrence expansion, and all-day boundary behavior were not verified. This is a specification for a later manual check, not an exact UI recipe. Test an all-day event, an event crossing midnight, a multi-day event, and an event ending exactly at midnight before adding output. Keep calendar output separate from Things.
