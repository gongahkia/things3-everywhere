use framework "Foundation"
use scripting additions

-- Fixed executable source. All task content arrives as JSON on stdin.
-- No eval, run script, do shell script, URL dispatch, or database access.
on jsonText(value)
    set encoded to current application's NSJSONSerialization's dataWithJSONObject:value options:0 |error|:(missing value)
    return (current application's NSString's alloc()'s initWithData:encoded encoding:4) as text
end jsonText

on calendarDate(value)
    set d to current date
    set day of d to 1
    set year of d to (text 1 thru 4 of value) as integer
    set month of d to (text 6 thru 7 of value) as integer
    set day of d to (text 9 thru 10 of value) as integer
    set time of d to 12 * hours
    return d
end calendarDate

on dateText(d)
    if d is missing value then return current application's NSNull's |null|()
    set yy to (year of d as integer) as text
    set mm to text -2 thru -1 of ("0" & ((month of d as integer) as text))
    set dd to text -2 thru -1 of ("0" & ((day of d as integer) as text))
    return (text -4 thru -1 of ("0000" & yy)) & "-" & mm & "-" & dd
end dateText

on requireHandoffKind(itemClass, taskCount)
    if taskCount is not 1 then error number 7104
    -- dictionary class codes: to do (tstk), selected to do (tslt).
    if itemClass is not «class tstk» and itemClass is not «class tslt» then error number 7104
end requireHandoffKind

on taskRow(t)
    tell application id "com.culturedcode.ThingsMac"
        set itemID to id of t
        set itemTitle to name of t
        set itemNotes to notes of t
        set itemStatus to status of t as text
        set itemTags to name of tags of t
        set itemDeadline to my dateText(due date of t)
    end tell
    return {itemID, itemTitle, itemNotes, itemStatus, itemTags, itemDeadline}
end taskRow

on run
    set writeStarted to false
    try
        set raw to current application's NSFileHandle's fileHandleWithStandardInput()'s readDataToEndOfFile()
        set request to current application's NSJSONSerialization's JSONObjectWithData:raw options:0 |error|:(missing value)
        set operation to (request's objectForKey:"operation") as text
        set response to current application's NSMutableDictionary's dictionary()
        response's setObject:true forKey:"ok"
        with timeout of 15 seconds
            if operation is "create" then
                set optIn to (current application's NSProcessInfo's processInfo()'s environment()'s objectForKey:"THINGS_ALLOW_WRITES")
                if optIn is missing value then error number 7101
                if (optIn as text) is not "true" then error number 7101
                if ((request's objectForKey:"execution") as text) is not "execute" then error number 7101
                set fields to request's objectForKey:"fields"
                set fieldKeys to (fields's allKeys()) as list
                set newTitle to (fields's objectForKey:"title") as text
                set newNotes to ""
                if fieldKeys contains "notes" then set newNotes to (fields's objectForKey:"notes") as text
                set newTags to ""
                if fieldKeys contains "tags" then
                    set requestedTags to (fields's objectForKey:"tags") as list
                    repeat with tagName in requestedTags
                        set tagValue to tagName as text
                        tell application id "com.culturedcode.ThingsMac"
                            if (count of (tags whose name is tagValue)) is not 1 then error number 7102
                        end tell
                        if newTags is not "" then set newTags to newTags & ", "
                        set newTags to newTags & tagValue
                    end repeat
                end if
                if fieldKeys contains "deadline" then set newDeadline to my calendarDate((fields's objectForKey:"deadline") as text)
                -- Validate all inputs/tags before the single make command.
                set writeStarted to true
                tell application id "com.culturedcode.ThingsMac"
                    if fieldKeys contains "deadline" then
                        set createdTask to make new to do with properties {name:newTitle, notes:newNotes, tag names:newTags, due date:newDeadline} at beginning of list "Inbox"
                    else
                        set createdTask to make new to do with properties {name:newTitle, notes:newNotes, tag names:newTags} at beginning of list "Inbox"
                    end if
                    set createdID to id of createdTask
                end tell
                response's setObject:createdID forKey:"id"
            else if operation is "inspect_task" or operation is "show_task" then
                set targetID to (request's objectForKey:"id") as text
                tell application id "com.culturedcode.ThingsMac"
                    set targetTask to to do id targetID
                    if (id of targetTask) is not targetID then error number 7105
                    -- id lookup can wrap projects as selected to do; require typed collection membership.
                    set taskCount to count of (to dos whose id is targetID)
                    my requireHandoffKind(class of targetTask, taskCount)
                    if operation is "show_task" then
                        show targetTask
                        activate
                    end if
                end tell
                response's setObject:"to do" forKey:"kind"
                response's setObject:targetID forKey:"id"
                if operation is "inspect_task" then response's setObject:(my taskRow(targetTask)) forKey:"row"
            else if operation is "get" then
                set targetID to (request's objectForKey:"id") as text
                tell application id "com.culturedcode.ThingsMac"
                    set targetTask to to do id targetID
                end tell
                response's setObject:(my taskRow(targetTask)) forKey:"row"
            else
                set resultLimit to (request's objectForKey:"limit") as integer
                if resultLimit < 1 or resultLimit > 100 then error number 7103
                tell application id "com.culturedcode.ThingsMac"
                    if operation is "today" then
                        set candidates to to dos of list "Today"
                    else if operation is "inbox" then
                        set candidates to to dos of list "Inbox"
                    else if operation is "search" then
                        set queryText to (request's objectForKey:"query") as text
                        set candidates to to dos whose name contains queryText and status is open
                    else
                        error number 7103
                    end if
                end tell
                set rows to current application's NSMutableArray's array()
                set returnedCount to 0
                repeat with candidate in candidates
                    if returnedCount is resultLimit then exit repeat
                    rows's addObject:(my taskRow(candidate))
                    set returnedCount to returnedCount + 1
                end repeat
                response's setObject:rows forKey:"rows"
                response's setObject:((count of candidates) > resultLimit) forKey:"has_more"
            end if
        end timeout
        return my jsonText(response)
    on error number errorNumber
        -- Do not return error text: Things may embed personal content in it.
        set response to current application's NSMutableDictionary's dictionary()
        response's setObject:false forKey:"ok"
        response's setObject:errorNumber forKey:"error_number"
        response's setObject:writeStarted forKey:"write_started"
        return my jsonText(response)
    end try
end run
