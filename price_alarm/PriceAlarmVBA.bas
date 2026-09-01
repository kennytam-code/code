Attribute VB_Name = "PriceAlarmVBA"
' Price Alarm - the Excel version. One file, no workbook to ship with it.
'
' Import this into a blank workbook and run Setup: it builds the Watchlist,
' Config and Log sheets, writes the BDP formulas, and puts the four buttons on
' the sheet. Then save as .xlsm and press Start.
'
' Watches the day move on each name and speaks when it crosses a threshold you
' set. Same rules as the Python app (price_alarm.py):
'   * a threshold fires once, then is spent until the move pulls back past it
'     by RearmBuffer - which is what stops a name sitting on +3.00 talking
'     every few seconds;
'   * each threshold speaks at most MaxRepeats times a day (per ticker, blank
'     falls back to DefaultMaxRepeats);
'   * negative thresholds mirror the positive ones on the way down.
'
' Run SelfTest at any time - it checks the crossing rules in five seconds.

Option Explicit

Private Const SHEET_WATCH As String = "Watchlist"
Private Const SHEET_CONFIG As String = "Config"
Private Const SHEET_LOG As String = "Log"
Private Const FIRST_ROW As Long = 3
Private Const WATCH_ROWS As Long = 30
Private Const COL_TICKER As Long = 1
Private Const COL_NICK As Long = 2
Private Const COL_THRESH As Long = 3
Private Const COL_MAXREP As Long = 4
Private Const COL_PRICE As Long = 5
Private Const COL_CHG As Long = 6
Private Const COL_STATUS As Long = 7
Private Const COL_TODAY As Long = 8

' State lives in memory, keyed "TICKER|threshold" -> Array(armed, count)
Private gState As Object
Private gRunning As Boolean
Private gNextTick As Date
Private gDay As Date

' ================================================================== SETUP ===
' Run this once, on a blank workbook, straight after importing the module.

Public Sub Setup()
    Dim ws As Worksheet

    Application.ScreenUpdating = False
    BuildWatchSheet
    BuildConfigSheet
    BuildLogSheet
    AddButtons
    DropBlankDefaultSheets
    Application.ScreenUpdating = True

    ThisWorkbook.Worksheets(SHEET_WATCH).Activate
    MsgBox "Price Alarm is set up." & vbCrLf & vbCrLf & _
           "1. Type your tickers in the blue columns." & vbCrLf & _
           "2. Save as .xlsm (File > Save As > Excel Macro-Enabled Workbook)." & vbCrLf & _
           "3. Press Start." & vbCrLf & vbCrLf & _
           "Paste this into ThisWorkbook so the timer stops on close:" & vbCrLf & _
           "    Private Sub Workbook_BeforeClose(Cancel As Boolean)" & vbCrLf & _
           "        StopAlarm" & vbCrLf & _
           "    End Sub", vbInformation, "Price Alarm"
End Sub

Private Function SheetNamed(nm As String) As Worksheet
    ' Reuse the sheet if Setup is run twice; otherwise make it.
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(nm)
    On Error GoTo 0
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Worksheets.Add(After:= _
                 ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.count))
        ws.name = nm
    Else
        ws.Cells.Clear
        ClearShapes ws
    End If
    Set SheetNamed = ws
End Function

Private Sub DropBlankDefaultSheets()
    ' The empty "Sheet1" a new workbook starts with, left over after Setup.
    ' Only ever an untouched default-named sheet - never anything with content.
    Dim ws As Worksheet, i As Long
    Application.DisplayAlerts = False
    For i = ThisWorkbook.Worksheets.count To 1 Step -1
        Set ws = ThisWorkbook.Worksheets(i)
        If ThisWorkbook.Worksheets.count > 1 Then
            If (ws.name Like "Sheet#" Or ws.name Like "Sheet##") And _
               Application.WorksheetFunction.CountA(ws.Cells) = 0 And _
               ws.Shapes.count = 0 Then
                ws.Delete
            End If
        End If
    Next i
    Application.DisplayAlerts = True
End Sub

Private Sub ClearShapes(ws As Worksheet)
    Dim i As Long
    For i = ws.Shapes.count To 1 Step -1
        ws.Shapes(i).Delete
    Next i
End Sub

Private Sub StyleHeader(rng As Range)
    rng.Font.Bold = True
    rng.Font.color = RGB(255, 255, 255)
    rng.Interior.color = RGB(31, 56, 100)
    rng.HorizontalAlignment = xlCenter
End Sub

Private Sub BuildWatchSheet()
    Dim ws As Worksheet, r As Long, heads As Variant, widths As Variant, i As Long
    Set ws = SheetNamed(SHEET_WATCH)

    ws.Range("A1").Value = "Price Alarm - watchlist"
    ws.Range("A1").Font.Bold = True
    ws.Range("A1").Font.Size = 12
    ws.Range("E1").Value = "Type in the blue columns. Thresholds are day-move %, " & _
                           "semicolons between, minus for downside."
    ws.Range("E1").Font.Italic = True
    ws.Range("E1").Font.color = RGB(128, 128, 128)

    heads = Array("Ticker", "NickName", "Thresholds", "MaxRepeats", _
                  "Price", "Chg %", "Status", "Announced today")
    widths = Array(22, 16, 18, 12, 12, 10, 26, 30)
    For i = 0 To UBound(heads)
        ws.Cells(2, i + 1).Value = heads(i)
        ws.Columns(i + 1).ColumnWidth = widths(i)
    Next i
    StyleHeader ws.Range(ws.Cells(2, 1), ws.Cells(2, 8))

    ws.Cells(FIRST_ROW, COL_TICKER).Value = "700 HK Equity"
    ws.Cells(FIRST_ROW, COL_NICK).Value = "Tencent"
    ws.Cells(FIRST_ROW, COL_THRESH).Value = "3;5;-3;-5"
    ws.Cells(FIRST_ROW + 1, COL_TICKER).Value = "2330 TT Equity"
    ws.Cells(FIRST_ROW + 1, COL_NICK).Value = "TSMC"
    ws.Cells(FIRST_ROW + 1, COL_THRESH).Value = "3;-3"
    ws.Cells(FIRST_ROW + 1, COL_MAXREP).Value = 2

    For r = FIRST_ROW To FIRST_ROW + WATCH_ROWS - 1
        ' The same two fields the Python app pulls, written the way the desk
        ' already types them. IF() keeps empty rows from firing a BDP call.
        ws.Cells(r, COL_PRICE).Formula = _
            "=IF($A" & r & "="""","""",BDP($A" & r & ",""LAST_PRICE""))"
        ws.Cells(r, COL_CHG).Formula = _
            "=IF($A" & r & "="""","""",BDP($A" & r & ",""CHG_PCT_1D""))"
        ws.Cells(r, COL_PRICE).NumberFormat = "#,##0.00"
        ws.Cells(r, COL_CHG).NumberFormat = "+0.00;-0.00;0.00"
    Next r

    ws.Range(ws.Cells(FIRST_ROW, COL_TICKER), _
             ws.Cells(FIRST_ROW + WATCH_ROWS - 1, COL_MAXREP)).Interior.color _
             = RGB(221, 235, 247)
    ws.Range(ws.Cells(FIRST_ROW, COL_PRICE), _
             ws.Cells(FIRST_ROW + WATCH_ROWS - 1, COL_TODAY)).Interior.color _
             = RGB(242, 242, 242)
    ' FreezePanes works off the active window, so the sheet has to be in front.
    ws.Activate
    ActiveWindow.FreezePanes = False
    ws.Range("A" & FIRST_ROW).Select
    ActiveWindow.FreezePanes = True
End Sub

Private Sub BuildConfigSheet()
    Dim ws As Worksheet, rows As Variant, i As Long, r As Long
    Set ws = SheetNamed(SHEET_CONFIG)

    ws.Range("A1").Value = "Settings"
    ws.Range("A1").Font.Bold = True
    ws.Range("A1").Font.Size = 12
    ws.Range("A2").Value = "Setting"
    ws.Range("B2").Value = "Value"
    ws.Range("C2").Value = "What it does"
    StyleHeader ws.Range("A2:C2")
    ws.Columns(1).ColumnWidth = 22
    ws.Columns(2).ColumnWidth = 12
    ws.Columns(3).ColumnWidth = 86

    rows = Array( _
        Array("PollSeconds", 4, "How often the alarm re-reads the prices."), _
        Array("DefaultMaxRepeats", 2, "Announcements per threshold per day when MaxRepeats is blank."), _
        Array("RearmBuffer", 0.25, "The move must pull back this far past a level before it can speak again. 0 makes a name resting on the level chatter."), _
        Array("Muted", False, "TRUE keeps the log but silences the voice. The Mute button flips it."))

    For i = 0 To UBound(rows)
        r = 3 + i
        ws.Cells(r, 1).Value = rows(i)(0)
        ws.Cells(r, 2).Value = rows(i)(1)
        ws.Cells(r, 2).Interior.color = RGB(221, 235, 247)
        ws.Cells(r, 3).Value = rows(i)(2)
        ws.Cells(r, 3).Font.Italic = True
        ws.Cells(r, 3).Font.color = RGB(128, 128, 128)
        ' Named so the macros can find them wherever the sheet ends up.
        ThisWorkbook.Names.Add name:=rows(i)(0), _
            RefersTo:="='" & SHEET_CONFIG & "'!$B$" & r
    Next i
    ws.Cells(3, 2).NumberFormat = "0"
    ws.Cells(4, 2).NumberFormat = "0"
    ws.Cells(5, 2).NumberFormat = "0.00"
End Sub

Private Sub BuildLogSheet()
    Dim ws As Worksheet, heads As Variant, widths As Variant, i As Long
    Set ws = SheetNamed(SHEET_LOG)
    ws.Range("A1").Value = "Announcement log"
    ws.Range("A1").Font.Bold = True
    ws.Range("A1").Font.Size = 12
    heads = Array("Time", "Ticker", "Threshold", "Price", "Chg %", "Spoken")
    widths = Array(20, 22, 12, 12, 10, 62)
    For i = 0 To UBound(heads)
        ws.Cells(2, i + 1).Value = heads(i)
        ws.Columns(i + 1).ColumnWidth = widths(i)
    Next i
    StyleHeader ws.Range("A2:F2")
End Sub

Private Sub AddButtons()
    Dim ws As Worksheet, labels As Variant, macros As Variant, i As Long
    Dim btn As Object, topPos As Double
    Set ws = ThisWorkbook.Worksheets(SHEET_WATCH)
    labels = Array("Start", "Stop", "Mute", "Reset counts")
    macros = Array("StartAlarm", "StopAlarm", "ToggleMute", "ResetCounts")
    topPos = ws.Range("J2").Top
    For i = 0 To UBound(labels)
        Set btn = ws.Buttons.Add(ws.Range("J2").Left + (i * 92), topPos, 88, 26)
        btn.Caption = labels(i)
        btn.OnAction = macros(i)
    Next i
End Sub

' ================================================================ BUTTONS ===

Public Sub StartAlarm()
    If gRunning Then
        MsgBox "The alarm is already running.", vbInformation, "Price Alarm"
        Exit Sub
    End If
    If Not Ready() Then Exit Sub
    ResetCounts
    gDay = Date
    gRunning = True
    LogLine "", "", "", "", "alarm started"
    ScheduleNext
End Sub

Public Sub StopAlarm()
    If Not gRunning Then Exit Sub
    gRunning = False
    ' An OnTime that is never cancelled will re-open this workbook later.
    On Error Resume Next
    Application.OnTime EarliestTime:=gNextTick, Procedure:="PollTick", Schedule:=False
    On Error GoTo 0
    LogLine "", "", "", "", "alarm stopped"
End Sub

Public Sub ToggleMute()
    Dim muted As Boolean
    If Not Ready() Then Exit Sub
    muted = Not CBool(CfgValue("Muted"))
    CfgSet "Muted", muted
    If muted Then
        LogLine "", "", "", "", "muted - alarms still logged"
    Else
        LogLine "", "", "", "", "unmuted"
    End If
End Sub

Public Sub ResetCounts()
    Dim ws As Worksheet, r As Long, thr As Variant, levels As Variant
    If Not Ready() Then Exit Sub
    Set gState = CreateObject("Scripting.Dictionary")
    Set ws = ThisWorkbook.Worksheets(SHEET_WATCH)
    For r = FIRST_ROW To LastWatchRow()
        If Trim$(CStr(ws.Cells(r, COL_TICKER).Value)) <> "" Then
            levels = ParseThresholds(CStr(ws.Cells(r, COL_THRESH).Value))
            If IsArray(levels) Then
                For Each thr In levels
                    gState(StateKey(ws.Cells(r, COL_TICKER).Value, CDbl(thr))) _
                        = Array(True, 0)
                Next thr
            End If
            ws.Cells(r, COL_TODAY).Value = ""
        End If
    Next r
End Sub

Private Function Ready() As Boolean
    ' Setup has to have run, or every name lookup below fails confusingly.
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(SHEET_WATCH)
    On Error GoTo 0
    If ws Is Nothing Then
        MsgBox "Run Setup first (Alt+F8 > Setup) - it builds the sheets.", _
               vbExclamation, "Price Alarm"
        Ready = False
    Else
        Ready = True
    End If
End Function

' ============================================================== THE TIMER ===

Private Sub ScheduleNext()
    Dim secs As Long
    If Not gRunning Then Exit Sub
    secs = CLng(CfgValue("PollSeconds"))
    If secs < 1 Then secs = 1
    gNextTick = Now + TimeSerial(0, 0, secs)
    Application.OnTime EarliestTime:=gNextTick, Procedure:="PollTick"
End Sub

Public Sub PollTick()
    Dim ws As Worksheet, r As Long, lastR As Long
    Dim ticker As String, nick As String
    Dim pct As Double, price As Double
    Dim levels As Variant, thr As Variant
    Dim maxRep As Long, buffer As Double
    Dim fired As Boolean, deepest As Double

    If Not gRunning Then Exit Sub

    ' New day: every cap and every level starts fresh.
    If Date <> gDay Then
        ResetCounts
        gDay = Date
        LogLine "", "", "", "", "new day - counts reset"
    End If

    On Error GoTo TickDone
    Set ws = ThisWorkbook.Worksheets(SHEET_WATCH)
    buffer = CDbl(CfgValue("RearmBuffer"))
    lastR = LastWatchRow()

    For r = FIRST_ROW To lastR
        ticker = Trim$(CStr(ws.Cells(r, COL_TICKER).Value))
        If ticker <> "" Then
            ' BDP shows #N/A before the open and on a bad ticker - skip, do not
            ' guess. A blank cell is not a zero move.
            If IsError(ws.Cells(r, COL_CHG).Value) Then
                ws.Cells(r, COL_STATUS).Value = "no data (check ticker)"
            ElseIf Not IsNumeric(ws.Cells(r, COL_CHG).Value) Then
                ws.Cells(r, COL_STATUS).Value = "waiting for first print"
            Else
                pct = CDbl(ws.Cells(r, COL_CHG).Value)
                price = 0
                If IsNumeric(ws.Cells(r, COL_PRICE).Value) Then
                    price = CDbl(ws.Cells(r, COL_PRICE).Value)
                End If
                ws.Cells(r, COL_STATUS).Value = "live " & Format$(Now, "hh:mm:ss")

                maxRep = RowMaxRepeats(ws, r)
                levels = ParseThresholds(CStr(ws.Cells(r, COL_THRESH).Value))
                fired = False
                deepest = 0
                If IsArray(levels) Then
                    For Each thr In levels
                        If CheckOne(ticker, CDbl(thr), maxRep, pct, buffer) Then
                            fired = True
                            If Abs(CDbl(thr)) > Abs(deepest) Then deepest = CDbl(thr)
                        End If
                    Next thr
                End If

                If fired Then
                    ' One jump can clear +3 and +5 at once: both are spent, one
                    ' sentence is spoken - it quotes the real move anyway.
                    nick = Trim$(CStr(ws.Cells(r, COL_NICK).Value))
                    If nick = "" Then nick = DefaultNick(ticker)
                    Announce nick, ticker, deepest, price, pct
                    ws.Cells(r, COL_TODAY).Value = CountsSummary(ticker, levels, maxRep)
                End If
            End If
        End If
    Next r

TickDone:
    ScheduleNext          ' always at the end, so a slow tick never stacks up
End Sub

' ======================================================= THE STATE MACHINE ===

Public Function CheckOne(ticker As String, thr As Double, maxRep As Long, _
                         pct As Double, buffer As Double) As Boolean
    ' Returns True when this threshold should speak now.
    Dim key As String, armed As Boolean, count As Long
    Dim through As Boolean, back As Boolean, st As Variant

    If gState Is Nothing Then Set gState = CreateObject("Scripting.Dictionary")
    key = StateKey(ticker, thr)
    If Not gState.Exists(key) Then gState(key) = Array(True, 0)
    st = gState(key)
    armed = CBool(st(0))
    count = CLng(st(1))

    If thr > 0 Then
        through = (pct >= thr)
        back = (pct <= thr - buffer)
    Else
        through = (pct <= thr)
        back = (pct >= thr + buffer)
    End If

    If through Then
        If armed And count < maxRep Then
            gState(key) = Array(False, count + 1)
            CheckOne = True
        End If
    ElseIf back And Not armed Then
        gState(key) = Array(True, count)
    End If
End Function

Private Sub Announce(nick As String, ticker As String, thr As Double, _
                     price As Double, pct As Double)
    Dim text As String
    text = SpokenText(nick, price, pct)
    LogLine ticker, Format$(thr, "+0.##;-0.##"), Format$(price, "#,##0.00"), _
            Format$(pct, "+0.00;-0.00"), text
    If Not CBool(CfgValue("Muted")) Then
        ' SpeakAsync so a long name never freezes the sheet; SAPI queues them
        ' internally, so two alarms in one tick still read one after the other.
        Application.Speech.Speak text, SpeakAsync:=True
    End If
End Sub

Public Function SpokenText(nick As String, price As Double, pct As Double) As String
    Dim way As String
    If pct >= 0 Then way = "up" Else way = "down"
    SpokenText = nick & " is trading at " & Format$(price, "#,##0.00") & _
                 ", " & way & " " & Format$(Abs(pct), "0.0") & " percent"
End Function

Public Function ParseThresholds(raw As String) As Variant
    ' "3;5;-3" -> array of doubles. Blanks skipped, zero and junk ignored.
    Dim parts As Variant, i As Long, n As Long, piece As String
    Dim out() As Double, val As Double
    parts = Split(raw, ";")
    ReDim out(0 To UBound(parts) + 1)
    n = -1
    For i = LBound(parts) To UBound(parts)
        piece = Replace(Trim$(CStr(parts(i))), "%", "")
        If piece <> "" And IsNumeric(piece) Then
            val = CDbl(piece)
            If val <> 0 Then
                n = n + 1
                out(n) = val
            End If
        End If
    Next i
    If n < 0 Then
        ParseThresholds = Empty
    Else
        ReDim Preserve out(0 To n)
        ParseThresholds = out
    End If
End Function

' ================================================================ HELPERS ===

Private Function StateKey(ticker As String, thr As Double) As String
    StateKey = UCase$(Trim$(ticker)) & "|" & Format$(thr, "0.###")
End Function

Private Function DefaultNick(ticker As String) As String
    Dim t As String
    t = Trim$(ticker)
    If UCase$(Right$(t, 7)) = " EQUITY" Then t = Trim$(Left$(t, Len(t) - 7))
    If UCase$(Right$(t, 6)) = " INDEX" Then t = Trim$(Left$(t, Len(t) - 6))
    DefaultNick = t
End Function

Private Function RowMaxRepeats(ws As Worksheet, r As Long) As Long
    Dim v As Variant
    v = ws.Cells(r, COL_MAXREP).Value
    If Not IsEmpty(v) Then
        If IsNumeric(v) Then
            If CLng(v) >= 1 Then
                RowMaxRepeats = CLng(v)
                Exit Function
            End If
        End If
    End If
    RowMaxRepeats = CLng(CfgValue("DefaultMaxRepeats"))
End Function

Private Function LastWatchRow() As Long
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets(SHEET_WATCH)
    LastWatchRow = ws.Cells(ws.Rows.count, COL_TICKER).End(xlUp).Row
    If LastWatchRow < FIRST_ROW Then LastWatchRow = FIRST_ROW
End Function

Private Function CountsSummary(ticker As String, levels As Variant, _
                               maxRep As Long) As String
    Dim thr As Variant, out As String, key As String, st As Variant
    If Not IsArray(levels) Then Exit Function
    For Each thr In levels
        key = StateKey(ticker, CDbl(thr))
        If gState.Exists(key) Then
            st = gState(key)
            out = out & Format$(CDbl(thr), "+0.##;-0.##") & "% " & _
                  CStr(st(1)) & "/" & CStr(maxRep) & "   "
        End If
    Next thr
    CountsSummary = Trim$(out)
End Function

' OnTime fires whatever workbook happens to be in front, so every setting is
' read through ThisWorkbook - an unqualified Range() would look at the wrong
' book and either fail or read someone else's cell.
Private Function CfgValue(settingName As String) As Variant
    CfgValue = ThisWorkbook.Names(settingName).RefersToRange.Value
End Function

Private Sub CfgSet(settingName As String, v As Variant)
    ThisWorkbook.Names(settingName).RefersToRange.Value = v
End Sub

Private Sub LogLine(ticker As String, thr As String, price As String, _
                    pct As String, text As String)
    Dim ws As Worksheet, r As Long
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(SHEET_LOG)
    On Error GoTo 0
    If ws Is Nothing Then Exit Sub
    r = ws.Cells(ws.Rows.count, 1).End(xlUp).Row + 1
    If r < 3 Then r = 3
    ws.Cells(r, 1).Value = Format$(Now, "yyyy-mm-dd hh:mm:ss")
    ws.Cells(r, 2).Value = ticker
    ws.Cells(r, 3).Value = thr
    ws.Cells(r, 4).Value = price
    ws.Cells(r, 5).Value = pct
    ws.Cells(r, 6).Value = text
End Sub

' ============================================================== SELF TEST ===
' Same paths as the Python engine tests. Results print to the Immediate window
' (Ctrl+G). Run it after importing, and after any edit to CheckOne.

Public Sub SelfTest()
    Dim fails As Long

    ' 1. a clean cross speaks once, and holding above stays quiet
    Set gState = CreateObject("Scripting.Dictionary")
    fails = fails + Chk("cross up once", _
        Fires("AAA", 3, 2, 0.25, Array(0.5, 1.8, 3.1, 3.4, 3.9)), 1)

    ' 2. chatter inside the buffer stays quiet
    Set gState = CreateObject("Scripting.Dictionary")
    fails = fails + Chk("chatter quiet", _
        Fires("BBB", 3, 2, 0.25, Array(3.05, 2.95, 3.05, 2.9, 3.1)), 1)

    ' 3. a real pull-back past the buffer re-arms it
    Set gState = CreateObject("Scripting.Dictionary")
    fails = fails + Chk("recross speaks again", _
        Fires("CCC", 3, 2, 0.25, Array(3.1, 2.5, 3.2)), 2)

    ' 4. the daily cap holds
    Set gState = CreateObject("Scripting.Dictionary")
    fails = fails + Chk("cap of 2", _
        Fires("DDD", 3, 2, 0.25, Array(3.1, 2#, 3.2, 2#, 3.3, 2#, 3.4)), 2)

    ' 5. the downside mirrors
    Set gState = CreateObject("Scripting.Dictionary")
    fails = fails + Chk("down cross once", _
        Fires("EEE", -3, 2, 0.25, Array(-1#, -3.4, -3.6)), 1)
    Set gState = CreateObject("Scripting.Dictionary")
    fails = fails + Chk("down chatter quiet", _
        Fires("FFF", -3, 2, 0.25, Array(-3.05, -2.95, -3.05)), 1)

    ' 6. already through on the first read is information, so it speaks
    Set gState = CreateObject("Scripting.Dictionary")
    fails = fails + Chk("starts through", _
        Fires("GGG", 3, 2, 0.25, Array(4#)), 1)

    ' 7. threshold parsing matches the CSV rules
    fails = fails + Chk("parse count", UBound(ParseThresholds("3;5;-3;-5")) + 1, 4)
    fails = fails + Chk("parse skips junk", UBound(ParseThresholds("3;;abc;0;-3")) + 1, 2)

    ' 8. the sentence reads the way the Python app says it
    If SpokenText("Nvidia", 1234.5, 3.14) <> "Nvidia is trading at 1,234.50, up 3.1 percent" Then
        Debug.Print "  FAIL  wording: " & SpokenText("Nvidia", 1234.5, 3.14)
        fails = fails + 1
    Else
        Debug.Print "  PASS  wording"
    End If

    Set gState = Nothing
    If fails = 0 Then
        Debug.Print "SelfTest: all checks pass"
        MsgBox "SelfTest: all checks pass.", vbInformation, "Price Alarm"
    Else
        Debug.Print "SelfTest: " & fails & " FAILED"
        MsgBox "SelfTest: " & fails & " check(s) FAILED - see the Immediate " & _
               "window (Ctrl+G).", vbExclamation, "Price Alarm"
    End If
End Sub

Private Function Fires(ticker As String, thr As Double, maxRep As Long, _
                       buffer As Double, path As Variant) As Long
    Dim i As Long, n As Long
    For i = LBound(path) To UBound(path)
        If CheckOne(ticker, thr, maxRep, CDbl(path(i)), buffer) Then n = n + 1
    Next i
    Fires = n
End Function

Private Function Chk(label As String, got As Long, want As Long) As Long
    If got = want Then
        Debug.Print "  PASS  " & label
        Chk = 0
    Else
        Debug.Print "  FAIL  " & label & ": got " & got & ", want " & want
        Chk = 1
    End If
End Function
