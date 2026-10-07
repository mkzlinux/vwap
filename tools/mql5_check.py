#!/usr/bin/env python3
"""
Static sanity checker for the MQL5 sources in this repository.

MetaEditor is Windows-only, so it cannot run in this sandbox. This script is
the substitute: it parses the real .mq5/.mqh files and verifies the things a
compiler would catch first.

  1. Comment / string literal stripping is balanced.
  2. ( ) { } [ ] are balanced, with line numbers for the offending opener.
  3. Every #property indicator_buffers N matches the SetIndexBuffer() calls.
  4. Every function call resolves to a definition (in-file or in the MQL5
     standard library headers) with a matching argument count.
  5. Every identifier resolves to a local declaration, an MQL5 builtin, or an
     MQL5 constant. Anything else is reported for review.

Usage:  python3 tools/mql5_check.py [--stdlib=DIR] [--corpus=DIR] [file ...]
Exit code 0 = clean, 1 = problems found.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- MQL5 builtins
# Functions and constants from the MQL5 language itself (not the standard
# library, which is discovered from the real headers passed to --stdlib).
BUILTIN_FUNCS = {
    # math
    "MathAbs", "MathMax", "MathMin", "MathFloor", "MathCeil", "MathRound",
    "MathLog10", "MathPow", "MathSqrt", "MathMod",
    # arrays
    "ArrayResize", "ArrayInitialize", "ArrayFree", "ArraySize", "ArraySort",
    "ArraySetAsSeries", "ArrayGetAsSeries", "ArrayCopy", "ArrayRange",
    # strings
    "StringLen", "StringFind", "StringSubstr", "StringSplit", "StringTrimLeft",
    "StringTrimRight", "StringFormat", "StringConcatenate", "StringGetCharacter",
    "StringReplace", "StringToUpper", "StringToLower",
    # conversion
    "IntegerToString", "DoubleToString", "StringToInteger", "StringToDouble",
    "TimeToString", "StringToTime", "TimeToStruct", "StructToTime",
    "ColorToARGB", "EnumToString", "CharToString", "ShortToString",
    # time
    "TimeCurrent", "TimeLocal", "TimeGMT", "PeriodSeconds", "Period",
    # series
    "CopyRates", "CopyBuffer", "CopyClose", "CopyOpen", "CopyHigh", "CopyLow",
    "CopyTime", "CopyTickVolume", "CopyRealVolume", "CopyVolumes", "CopySpread",
    "iTime", "iOpen", "iHigh", "iLow", "iClose", "iVolume", "iRealVolume",
    "iBarShift", "iSpread", "Bars",
    # indicators
    "iMA", "iATR", "iRSI", "iMACD", "iBands", "iCustom", "IndicatorRelease",
    "IndicatorCreate", "IndicatorBuffers", "IndicatorSetString",
    "IndicatorSetInteger", "IndicatorSetDouble",
    # indicator buffers / plots
    "SetIndexBuffer", "SetIndexStyle", "PlotIndexSetInteger", "PlotIndexSetDouble",
    "PlotIndexSetString", "PlotIndexGetInteger", "SetIndexShift", "SetIndexLabel",
    # symbols
    "SymbolInfoInteger", "SymbolInfoDouble", "SymbolInfoString", "SymbolSelect",
    "SymbolIsSynchronized", "SymbolsTotal", "SymbolName", "Symbol",
    # account / terminal
    "AccountInfoInteger", "AccountInfoDouble", "AccountInfoString",
    "TerminalInfoInteger", "TerminalInfoDouble", "TerminalInfoString",
    "MQLInfoInteger", "MQLInfoString",
    # trade info (read-only, allowed in indicators too)
    "PositionsTotal", "PositionGetTicket", "PositionGetSymbol",
    "PositionGetInteger", "PositionGetDouble", "PositionGetString",
    "PositionSelect", "PositionSelectByTicket", "OrdersTotal", "OrderCalcMargin",
    "HistorySelect", "HistoryDealsTotal",
    # chart / objects
    "ObjectCreate", "ObjectDelete", "ObjectFind", "ObjectSetInteger",
    "ObjectSetDouble", "ObjectSetString", "ObjectGetInteger", "ObjectGetDouble",
    "ObjectGetString", "ObjectName", "ObjectsTotal", "ObjectsDeleteAll",
    "ObjectMove", "ObjectType", "ObjectGetTimeByValue",
    "ChartRedraw", "ChartGetInteger", "ChartSetInteger", "ChartID",
    "ChartTimeOnCoordinate", "ChartPriceOnCoordinate",
    # user interaction / output
    "Print", "PrintFormat", "Alert", "Comment", "MessageBox", "PlaySound",
    "SendNotification", "SendMail", "SendFTP",
    # misc
    "GetLastError", "ResetLastError", "UninitializeReason", "GetTickCount",
    "Sleep", "DebugBreak", "ZeroMemory", "TerminalClose",
}

BUILTIN_CONSTS = {
    # predefined variables
    "_Point", "_Digits", "_Symbol", "_Period", "_RandomSeed", "_StopFlag",
    "_IsX64", "_MQL5BUILD",
    # limits
    "EMPTY_VALUE", "WHOLE_ARRAY", "ULONG_MAX", "LONG_MAX", "INT_MAX",
    "DBL_MAX", "DBL_MIN", "M_PI", "M_E", "CHAR_MAX", "UCHAR_MAX",
    # init/deinit return codes
    "INIT_SUCCEEDED", "INIT_FAILED", "INIT_PARAMETERS_INCORRECT",
    "INIT_AGENT_NOT_SUITABLE",
    "REASON_PROGRAM", "REASON_REMOVE", "REASON_RECOMPILE", "REASON_CHARTCHANGE",
    "REASON_CHARTCLOSE", "REASON_PARAMETERS", "REASON_ACCOUNT", "REASON_TEMPLATE",
    "REASON_INITFAILED", "REASON_CLOSE",
    # indicator buffer / plot props
    "INDICATOR_DATA", "INDICATOR_COLOR_INDEX", "INDICATOR_CALCULATIONS",
    "INDICATOR_DIGITS", "INDICATOR_SHORTNAME", "INDICATOR_LEVELS",
    "INDICATOR_MAXIMUM", "INDICATOR_MINIMUM", "INDICATOR_COLOR_INDEX",
    "PLOT_COLOR_INDEXES", "PLOT_LINE_COLOR", "PLOT_LINE_STYLE", "PLOT_LINE_WIDTH",
    "PLOT_DRAW_TYPE", "PLOT_ARROW", "PLOT_ARROW_SHIFT", "PLOT_EMPTY_VALUE",
    "PLOT_LABEL", "PLOT_SHIFT", "PLOT_DRAW_BEGIN", "PLOT_COLOR_INDEX",
    # draw types
    "DRAW_NONE", "DRAW_LINE", "DRAW_COLOR_LINE", "DRAW_SECTION", "DRAW_HISTOGRAM",
    "DRAW_ARROW", "DRAW_ZIGZAG", "DRAW_CANDLES", "DRAW_BARS", "DRAW_FILLING",
    # line styles
    "STYLE_SOLID", "STYLE_DASH", "STYLE_DOT", "STYLE_DASHDOT", "STYLE_DASHDOTDOT",
    # object types
    "OBJ_VLINE", "OBJ_HLINE", "OBJ_TREND", "OBJ_TREND_BY_ANGLE", "OBJ_RECTANGLE",
    "OBJ_RECTANGLE_LABEL", "OBJ_TEXT", "OBJ_LABEL", "OBJ_ARROW", "OBJ_ARROW_UP",
    "OBJ_ARROW_DOWN", "OBJ_ARROW_RIGHT_PRICE", "OBJ_PERIOD_LINE", "OBJ_CHANNEL",
    "OBJ_FIBO", "OBJ_CYCLES", "OBJ_REGRESSION", "OBJ_ELLIOT",
    # object properties
    "OBJPROP_TIME", "OBJPROP_PRICE", "OBJPROP_COLOR", "OBJPROP_STYLE",
    "OBJPROP_WIDTH", "OBJPROP_BACK", "OBJPROP_FILL", "OBJPROP_RAY_RIGHT",
    "OBJPROP_RAY_LEFT", "OBJPROP_SELECTABLE", "OBJPROP_SELECTED",
    "OBJPROP_HIDDEN", "OBJPROP_TEXT", "OBJPROP_TOOLTIP", "OBJPROP_ANCHOR",
    "OBJPROP_FONTSIZE", "OBJPROP_FONT", "OBJPROP_ANGLE", "OBJPROP_BGCOLOR",
    "OBJPROP_CORNER", "OBJPROP_XDISTANCE", "OBJPROP_YDISTANCE", "OBJPROP_NAME",
    "OBJPROP_TYPE", "OBJPROP_ZORDER", "OBJPROP_LEVELCOLOR", "OBJPROP_TIMEFRAMES",
    # anchors
    "ANCHOR_LEFT_UPPER", "ANCHOR_LEFT", "ANCHOR_LEFT_LOWER", "ANCHOR_RIGHT_UPPER",
    "ANCHOR_RIGHT", "ANCHOR_RIGHT_LOWER", "ANCHOR_UPPER", "ANCHOR_LOWER",
    "ANCHOR_CENTER",
    # timeframes
    "PERIOD_CURRENT", "PERIOD_M1", "PERIOD_M2", "PERIOD_M3", "PERIOD_M4",
    "PERIOD_M5", "PERIOD_M6", "PERIOD_M10", "PERIOD_M12", "PERIOD_M15",
    "PERIOD_M20", "PERIOD_M30", "PERIOD_H1", "PERIOD_H2", "PERIOD_H3",
    "PERIOD_H4", "PERIOD_H6", "PERIOD_H8", "PERIOD_H12", "PERIOD_D1",
    "PERIOD_W1", "PERIOD_MN1",
    # applied price
    "PRICE_CLOSE", "PRICE_OPEN", "PRICE_HIGH", "PRICE_LOW", "PRICE_MEDIAN",
    "PRICE_TYPICAL", "PRICE_WEIGHTED",
    # ma methods
    "MODE_SMA", "MODE_EMA", "MODE_SMMA", "MODE_LWMA",
    # symbol props
    "SYMBOL_DIGITS", "SYMBOL_POINT", "SYMBOL_ASK", "SYMBOL_BID",
    "SYMBOL_SPREAD", "SYMBOL_TRADE_STOPS_LEVEL", "SYMBOL_TRADE_FREEZE_LEVEL",
    "SYMBOL_VOLUME_MIN", "SYMBOL_VOLUME_MAX", "SYMBOL_VOLUME_STEP",
    "SYMBOL_TRADE_TICK_VALUE", "SYMBOL_TRADE_TICK_SIZE", "SYMBOL_SELECT",
    "SYMBOL_EXIST", "SYMBOL_FILLING_MODE", "SYMBOL_FILLING_FOK",
    "SYMBOL_FILLING_IOC", "SYMBOL_TRADE_MODE", "SYMBOL_TRADE_MODE_FULL",
    "SYMBOL_CURRENCY_PROFIT", "SYMBOL_DESCRIPTION", "SYMBOL_STARTING",
    "SYMBOL_EXPIRATION_TIME", "SYMBOL_VOLUME", "SYMBOL_VOLUMEHIGH",
    "SYMBOL_VOLUMELOW", "SYMBOL_TIME", "SYMBOL_TRADE_EXEMODE",
    "SYMBOL_CALC_MODE_FOREX", "SYMBOL_SWAP_LONG", "SYMBOL_SWAP_SHORT",
    # account props
    "ACCOUNT_EQUITY", "ACCOUNT_BALANCE", "ACCOUNT_MARGIN_FREE",
    "ACCOUNT_MARGIN_MODE", "ACCOUNT_CURRENCY", "ACCOUNT_LEVERAGE",
    "ACCOUNT_MARGIN_MODE_RETAIL_NETTING", "ACCOUNT_MARGIN_MODE_EXCHANGE",
    "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", "ACCOUNT_PROFIT",
    # terminal props
    "TERMINAL_TRADE_ALLOWED", "TERMINAL_CONNECTED", "TERMINAL_LANGUAGE",
    "TERMINAL_PATH", "TERMINAL_COMMONDATA_PATH",
    # mql props
    "MQL_TRADE_ALLOWED", "MQL_SIGNALS_ALLOWED", "MQL_TESTER", "MQL_VISUAL_MODE",
    "MQL_OPTIMIZATION", "MQL_PROGRAM_TYPE", "MQL_DEBUG", "MQL_PROFILER",
    "MQL_FRAME_MODE", "PROGRAM_ACCOUNT",
    # position props
    "POSITION_SYMBOL", "POSITION_MAGIC", "POSITION_TYPE", "POSITION_VOLUME",
    "POSITION_SL", "POSITION_TP", "POSITION_PRICE_OPEN", "POSITION_PRICE_CURRENT",
    "POSITION_TIME", "POSITION_TICKET", "POSITION_PROFIT", "POSITION_COMMENT",
    "POSITION_TYPE_BUY", "POSITION_TYPE_SELL", "POSITION_IDENTIFIER",
    # order types
    "ORDER_TYPE_BUY", "ORDER_TYPE_SELL", "ORDER_TYPE_BUY_LIMIT",
    "ORDER_TYPE_SELL_LIMIT", "ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP",
    "ORDER_FILLING_FOK", "ORDER_FILLING_IOC", "ORDER_FILLING_RETURN",
    "ORDER_TIME_GTC", "ORDER_TIME_DAY", "ORDER_TIME_SPECIFIED",
    # trade retcodes
    "TRADE_RETCODE_DONE", "TRADE_RETCODE_DONE_PARTIAL", "TRADE_RETCODE_REQUOTE",
    "TRADE_RETCODE_REJECT", "TRADE_RETCODE_INVALID_VOLUME", "TRADE_RETCODE_INVALID_STOP",
    # volume types
    "VOLUME_TICK", "VOLUME_REAL",
    # colours
    "clrBlack", "clrWhite", "clrRed", "clrGreen", "clrBlue", "clrGold",
    "clrLime", "clrSilver", "clrGray", "clrDodgerBlue", "clrOrangeRed",
    "clrFireBrick", "clrYellow", "clrAqua", "clrMagenta", "clrOrange",
    "clrTomato", "clrDarkGreen", "clrDimGray", "clrLightGray", "clrNone",
    "clrTransparent", "clrCrimson", "clrDeepSkyBlue", "clrSeaGreen",
    # other enums
    "LOG_LEVEL_NO", "LOG_LEVEL_ERRORS", "LOG_LEVEL_ALL",
    "CHAR_NULL", "SHORT_MAX",
}

BUILTIN_TYPES = {
    "int", "uint", "long", "ulong", "short", "ushort", "char", "uchar",
    "double", "float", "bool", "string", "color", "datetime", "void",
    "ENUM_TIMEFRAMES", "ENUM_APPLIED_PRICE", "ENUM_MA_METHOD", "ENUM_LINE_STYLE",
    "ENUM_OBJECT", "ENUM_OBJECT_PROPERTY_INTEGER", "ENUM_OBJECT_PROPERTY_DOUBLE",
    "ENUM_OBJECT_PROPERTY_STRING", "ENUM_ANCHOR_POINT", "ENUM_PLOT_PROPERTY_INTEGER",
    "ENUM_PLOT_PROPERTY_DOUBLE", "ENUM_PLOT_PROPERTY_STRING",
    "ENUM_SYMBOL_INFO_INTEGER", "ENUM_SYMBOL_INFO_DOUBLE", "ENUM_SYMBOL_INFO_STRING",
    "ENUM_ACCOUNT_INFO_INTEGER", "ENUM_ACCOUNT_INFO_DOUBLE",
    "ENUM_TERMINAL_INFO_INTEGER", "ENUM_MQL_INFO_INTEGER",
    "ENUM_POSITION_PROPERTY_INTEGER", "ENUM_POSITION_PROPERTY_DOUBLE",
    "ENUM_POSITION_PROPERTY_STRING", "ENUM_POSITION_TYPE", "ENUM_ORDER_TYPE",
    "ENUM_ORDER_TYPE_FILLING", "ENUM_ORDER_TYPE_TIME", "ENUM_VOLUME_TYPE",
    "ENUM_LOG_LEVELS", "ENUM_ACCOUNT_MARGIN_MODE", "ENUM_BASE_CORNER",
    "MqlRates", "MqlDateTime", "MqlTick", "MqlTradeRequest", "MqlTradeResult",
    "MqlBookInfo",
}

# Names defined by the preprocessor lines themselves
PREPROC_IGNORED = {"property", "include", "ifdef", "ifndef", "define", "endif",
                   "else", "import", "copyright", "link", "version", "strict",
                   "description", "indicator_chart_window", "indicator_separate_window",
                   "indicator_buffers", "indicator_plots", "script_show_inputs"}

MQL5_KEYWORDS = {
    "if", "else", "for", "while", "do", "switch", "case", "default", "break",
    "continue", "return", "goto", "struct", "class", "union", "enum", "template",
    "typename", "new", "delete", "operator", "this", "true", "false", "NULL",
    "const", "static", "extern", "virtual", "override", "final", "explicit",
    "public", "private", "protected", "input", "sinput", "group", "namespace",
    "void", "get", "set", "try", "catch", "throw", "sizeof", "dynamic_cast",
    "cast", "ref", "in", "out", "inout",
}


class Problem:
    def __init__(self, path, line, msg):
        self.path, self.line, self.msg = path, line, msg

    def __str__(self):
        return f"{self.path.name}:{self.line}: {self.msg}"


def strip_source(text):
    """Return (cleaned, linemap) where comments/strings are blanked but the
    line structure is preserved so line numbers stay valid."""
    out = []
    i, n = 0, len(text)
    state = "code"  # code | line_comment | block_comment | string | char
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == "/" and nxt == "/":
                state = "line_comment"
                out.append("  ")
                i += 2
                continue
            if c == "/" and nxt == "*":
                state = "block_comment"
                out.append("  ")
                i += 2
                continue
            if c == '"':
                state = "string"
                out.append(" ")
                i += 1
                continue
            if c == "'":
                state = "char"
                out.append(" ")
                i += 1
                continue
            out.append(c)
            i += 1
        elif state == "line_comment":
            if c == "\n":
                state = "code"
                out.append("\n")
            else:
                out.append(" ")
            i += 1
        elif state == "block_comment":
            if c == "*" and nxt == "/":
                state = "code"
                out.append("  ")
                i += 2
                continue
            out.append("\n" if c == "\n" else " ")
            i += 1
        elif state == "string":
            if c == "\\":
                out.append("  ")
                i += 2
                continue
            if c == '"':
                state = "code"
                out.append(" ")
                i += 1
                continue
            out.append("\n" if c == "\n" else " ")
            i += 1
        elif state == "char":
            if c == "\\":
                out.append("  ")
                i += 2
                continue
            if c == "'":
                state = "code"
                out.append(" ")
                i += 1
                continue
            out.append("\n" if c == "\n" else " ")
            i += 1
    if state != "code":
        raise ValueError(f"unterminated {state} at end of file")
    return "".join(out)


def line_of(cleaned, pos):
    return cleaned.count("\n", 0, pos) + 1


def check_balance(path, cleaned, problems):
    stack = []
    pairs = {")": "(", "}": "{", "]": "["}
    for idx, c in enumerate(cleaned):
        if c in "({[":
            stack.append((c, line_of(cleaned, idx)))
        elif c in ")}]":
            if not stack:
                problems.append(Problem(path, line_of(cleaned, idx),
                                        f"unmatched closing '{c}'"))
                continue
            opener, oline = stack.pop()
            if opener != pairs[c]:
                problems.append(Problem(path, line_of(cleaned, idx),
                                        f"'{c}' closes '{opener}' opened on line {oline}"))
    for opener, oline in stack:
        problems.append(Problem(path, oline, f"unclosed '{opener}'"))


def parse_params(param_text):
    """Split a parameter list on top-level commas, drop types, return names."""
    if not param_text.strip():
        return []
    depth, cur, parts = 0, "", []
    for c in param_text:
        if c in "([<":
            depth += 1
        elif c in ")]>":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur.strip():
        parts.append(cur)

    names = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        p = p.split("=")[0].strip()          # drop default value
        m = re.findall(r"[A-Za-z_]\w*", p)
        if m:
            names.append(m[-1])
    # MQL5:  void Foo(void)  declares zero parameters
    if names == ["void"]:
        return []
    return names


FUNC_DEF_RE = re.compile(
    r"(?:^|[\n;{}])\s*"
    r"(?:(?:const|static|inline|virtual)\s+)*"
    r"([A-Za-z_][\w:]*)\s+"            # return type
    r"(\*?\s*[A-Za-z_]\w*)\s*"          # function name
    r"\(([^;{}()]*(?:\([^()]*\)[^;{}()]*)*)\)\s*"
    r"(?:const\s*)?\{",
    re.M,
)

CALL_RE = re.compile(r"(?<![.\w])([A-Za-z_]\w*)\s*\(")


def split_args(arg_text):
    if not arg_text.strip():
        return []
    depth, cur, parts = 0, "", []
    for c in arg_text:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def find_call_args(cleaned, start_paren):
    """Given the index of '(' return the raw argument text."""
    depth, i = 0, start_paren
    while i < len(cleaned):
        c = cleaned[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return cleaned[start_paren + 1:i]
        i += 1
    return ""


def blank_preprocessor(cleaned):
    """Blank out lines that start with '#' so #property/#include tokens are not
    mistaken for identifiers. Line structure is preserved."""
    out_lines = []
    for ln in cleaned.split("\n"):
        if ln.lstrip().startswith("#"):
            out_lines.append(" " * len(ln))
        else:
            out_lines.append(ln)
    return "\n".join(out_lines)


def resolve_includes(path, raw):
    """Absolute paths of the angle-bracket includes that live in this
    repository's MQL5/Include tree. Does not track visited files - the caller
    owns the `seen` set."""
    found = []
    include_root = REPO / "MQL5" / "Include"
    for m in re.finditer(r"#\s*include\s+<([^>]+)>", raw):
        rel = m.group(1).replace("\\", "/")
        cand = include_root / rel
        if cand.exists() and cand not in found:
            found.append(cand)
    return found


def collect_stdlib(stdlib_dirs):
    """Harvest function names + enum members from real MQL5 headers."""
    funcs, consts = set(), set()
    for d in stdlib_dirs:
        for f in Path(d).rglob("*.mqh"):
            try:
                txt = strip_source(f.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            for m in FUNC_DEF_RE.finditer(txt):
                funcs.add(m.group(2).lstrip("* ").strip())
            for m in re.finditer(r"\b([A-Z][A-Z0-9_]{2,})\b", txt):
                consts.add(m.group(1))
    return funcs, consts


def collect_symbols(cleaned, raw=""):
    """Return (declared_names, funcs, def_spans) for one translation unit."""
    declared = set()
    funcs = {}      # name -> (min_args, max_args)

    for m in re.finditer(r"\benum\s+([A-Za-z_]\w*)", cleaned):
        declared.add(m.group(1))
    # enum members
    for m in re.finditer(r"\benum\s+[A-Za-z_]\w*\s*\{([^}]*)\}", cleaned, re.S):
        for part in m.group(1).split(","):
            mm = re.match(r"\s*([A-Za-z_]\w*)", part)
            if mm:
                declared.add(mm.group(1))

    # struct names
    for m in re.finditer(r"\bstruct\s+([A-Za-z_]\w*)", cleaned):
        declared.add(m.group(1))

    # function definitions
    def_spans = []
    for m in FUNC_DEF_RE.finditer(cleaned):
        name = m.group(2).lstrip("* ").strip()
        params = parse_params(m.group(3))
        raw_params = [p.strip() for p in split_args(m.group(3)) if p.strip()]
        optional = sum(1 for p in raw_params if "=" in p)
        funcs[name] = (len(params) - optional, len(params))
        declared.add(name)
        declared.update(params)
        def_spans.append(m.span())

    # variables, inputs, globals, for-loop counters
    var_re = re.compile(
        r"\b(?:input|static|const|extern)?\s*"
        r"(?:input\s+)?(?:group\s+)?"
        r"(?:const\s+|static\s+)*"
        r"(?:unsigned\s+)?(?:signed\s+)?"
        r"([A-Za-z_][\w:]*)\s+"
        r"(\*?\s*[A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*(?:=|;|,)")
    for m in var_re.finditer(cleaned):
        typ, name = m.group(1), m.group(2).lstrip("* ").strip()
        if typ in ("return", "else", "case"):
            continue
        declared.add(name)

    # multi-declarator lines like:  int a=0, b=1;   and  double x,y;
    for m in re.finditer(r"\b([A-Za-z_][\w:]*)\s+([^;{}()]*);", cleaned):
        if m.group(1) not in BUILTIN_TYPES and not re.match(r"^[A-Z]", m.group(1)):
            continue
        for part in m.group(2).split(","):
            mm = re.match(r"\s*(\*?\s*[A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*(?:=.*)?$", part)
            if mm:
                declared.add(mm.group(1).lstrip("* ").strip())

    # preprocessor-defined names
    for m in re.finditer(r"#\s*define\s+([A-Za-z_]\w*)", raw):
        declared.add(m.group(1))

    return declared, funcs, def_spans


def check_sets(indicator, set_dir):
    """Every key in a .set preset must be a declared input of the indicator,
    and every input should appear in the preset. Returns problems."""
    problems = []
    raw = indicator.read_text(encoding="utf-8", errors="replace")
    declared = {}
    for m in re.finditer(r"^\s*input\s+(?:group\s+)?"
                         r"(?!(?:group)\b)([A-Za-z_][\w:]*)\s+(Inp\w+)\s*=",
                         raw, re.M):
        declared[m.group(2)] = m.group(1)

    if not declared:
        return [Problem(indicator, 0, "no inputs found - cannot validate presets")]

    for f in sorted(set_dir.glob("*.set")):
        keys = []
        for ln, line in enumerate(f.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            if "=" not in line:
                problems.append(Problem(f, ln, f"malformed line: {line!r}"))
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            keys.append(key)
            if key not in declared:
                problems.append(Problem(f, ln, f"{key} is not an input of "
                                               f"{indicator.name}"))
            elif val.strip() == "":
                problems.append(Problem(f, ln, f"{key} has an empty value"))
        missing = [k for k in declared if k not in keys]
        if missing:
            problems.append(Problem(f, 1, f"missing input(s): {', '.join(sorted(missing))}"))
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            problems.append(Problem(f, 1, f"duplicate key(s): {', '.join(sorted(dupes))}"))
        print(f"  {f.name}: {len(keys)} keys, "
              f"{len(declared)} declared inputs, {len(missing)} missing")
    return problems


def display(path):
    """Path relative to the repo when possible, absolute otherwise."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def check_file(path, stdlib_funcs, stdlib_consts, extra_decls=None):
    problems = []
    extra_decls = extra_decls or set()
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        cleaned = strip_source(raw)
    except ValueError as e:
        return [Problem(path, 0, str(e))], set(), {}, set(), set()

    check_balance(path, cleaned, problems)

    # ---- declared names -------------------------------------------------
    declared, funcs, def_spans = collect_symbols(cleaned, raw)
    declared |= extra_decls

    # ---- #property indicator_buffers vs SetIndexBuffer ------------------
    prop_bufs = re.findall(r"#\s*property\s+indicator_buffers\s+(\d+)", raw)
    prop_plots = re.findall(r"#\s*property\s+indicator_plots\s+(\d+)", raw)
    setidx = re.findall(r"SetIndexBuffer\s*\(\s*(\d+)", cleaned)
    if prop_bufs:
        want = int(prop_bufs[-1])
        have = len(set(int(x) for x in setidx))
        if have != want:
            problems.append(Problem(path, 1,
                                    f"#property indicator_buffers {want} but "
                                    f"{have} distinct SetIndexBuffer indices "
                                    f"({sorted(set(int(x) for x in setidx))})"))
    if prop_plots and setidx:
        # a DRAW_COLOR_* plot consumes 2 buffers, everything else 1
        color_plots = len(re.findall(r"#\s*property\s+indicator_type\d+\s+DRAW_COLOR_", raw))
        n_plots = int(prop_plots[-1])
        expect = n_plots + color_plots
        have = len(set(int(x) for x in setidx))
        if have != expect:
            problems.append(Problem(path, 1,
                                    f"{n_plots} plots ({color_plots} colour) need "
                                    f"{expect} buffers but {have} are set"))

    # ---- call sites -----------------------------------------------------
    used = set()
    for m in CALL_RE.finditer(cleaned):
        # a definition matches CALL_RE too - only real call sites count
        if any(a <= m.start() < b for a, b in def_spans):
            continue
        name = m.group(1)
        used.add(name)
        paren = cleaned.index("(", m.end() - 1)
        args = find_call_args(cleaned, paren)
        n = len(split_args(args))
        if name in funcs:
            lo, hi = funcs[name]
            if not (lo <= n <= hi):
                problems.append(Problem(path, line_of(cleaned, m.start()),
                                        f"{name}() called with {n} arg(s), "
                                        f"defined to take {lo}-{hi}"))

    # ---- unknown identifiers -------------------------------------------
    known = (declared | BUILTIN_FUNCS | BUILTIN_CONSTS | BUILTIN_TYPES
             | PREPROC_IGNORED | MQL5_KEYWORDS | stdlib_funcs | stdlib_consts)
    unknown = {}
    all_ids = set()
    scan = blank_preprocessor(cleaned)
    for m in re.finditer(r"(?<![.\w#])([A-Za-z_]\w*)(?![\w])", scan):
        name = m.group(1)
        all_ids.add(name)
        if name in known:
            continue
        unknown.setdefault(name, line_of(scan, m.start()))

    return problems, unknown, funcs, used, all_ids


def collect_corpus(stdlib_dirs):
    """Every identifier that appears anywhere in the reference MQL5 corpus.
    A builtin found here is evidence it is real MQL5, not a guess."""
    corpus = set()
    files = 0
    for d in stdlib_dirs:
        for f in list(Path(d).rglob("*.mqh")) + list(Path(d).rglob("*.mq5")):
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            files += 1
            corpus.update(re.findall(r"[A-Za-z_]\w*", txt))
    return corpus, files


def include_closure(path, seen=None):
    """The file plus every repository-local header it pulls in, recursively."""
    if seen is None:
        seen = set()
    if path in seen:
        return []
    seen.add(path)
    out = [path]
    raw = path.read_text(encoding="utf-8", errors="replace")
    for inc in resolve_includes(path, raw):
        out.extend(include_closure(inc, seen))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    stdlib_dirs = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--stdlib=")]
    corpus_dirs = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--corpus=")]

    if args:
        files = [Path(a) for a in args]
    else:
        files = sorted(REPO.glob("MQL5/**/*.mq*"))

    stdlib_funcs, stdlib_consts = collect_stdlib(stdlib_dirs)
    corpus, corpus_files = collect_corpus(corpus_dirs or stdlib_dirs)
    print(f"reference corpus: {corpus_files} MQL5 file(s) -> {len(stdlib_funcs)} "
          f"stdlib functions, {len(corpus)} identifiers")

    all_problems = []
    all_unknown = {}
    used_builtins = {}
    for f in files:
        if not f.exists():
            all_problems.append(Problem(f, 0, "file not found"))
            continue
        # merge declarations from repository-local includes (VwapCore.mqh etc.)
        extra = set()
        units = include_closure(f)
        for u in units[1:]:
            uraw = u.read_text(encoding="utf-8", errors="replace")
            try:
                uclean = strip_source(uraw)
            except ValueError:
                continue
            d, _, _ = collect_symbols(uclean, uraw)
            extra |= d

        problems, unknown, funcs, used, all_ids = check_file(
            f, stdlib_funcs, stdlib_consts, extra)
        all_problems.extend(problems)
        inc = ", ".join(u.name for u in units[1:]) or "none"
        print(f"\n{display(f)}: includes=[{inc}] "
              f"{len(funcs)} functions defined, {len(used)} call sites, "
              f"{len(problems)} structural problem(s)")
        for k, v in sorted(unknown.items(), key=lambda kv: kv[1]):
            all_unknown.setdefault((f.name, k), v)
        for name in all_ids:
            if name in BUILTIN_FUNCS or name in BUILTIN_CONSTS:
                used_builtins.setdefault(name, f.name)

    # ---- verify the builtins we rely on are real -----------------------
    unverified = []
    print(f"\n--- builtin verification against the reference corpus "
          f"({len(used_builtins)} MQL5 builtins used) ---")
    if not corpus:
        print("  skipped - pass --corpus=DIR with real MQL5 sources to enable")
    else:
        unverified = sorted(n for n in used_builtins if n not in corpus)
        print(f"  confirmed present in real MQL5 source: {len(used_builtins) - len(unverified)}")
        if unverified:
            print("  NOT found in the corpus (verify by hand):")
            for n in unverified:
                print(f"    {n}   (first used in {used_builtins[n]})")

    set_dir = REPO / "Sets"
    if set_dir.is_dir():
        indicator = REPO / "MQL5" / "Indicators" / "WeltradeVWAP_9EMA_Signals.mq5"
        if indicator.exists():
            print("\n--- preset validation against declared inputs ---")
            all_problems.extend(check_sets(indicator, set_dir))

    if all_unknown:
        print("\n--- identifiers not resolved locally ---")
        for (fname, name), line in sorted(all_unknown.items()):
            print(f"  {fname}:{line}: {name}")

    if all_problems:
        print("\n--- structural problems ---")
        for p in all_problems:
            print(f"  {p}")

    print()
    fatal = len(all_problems) + len(all_unknown)
    if fatal:
        print(f"FAIL: {len(all_problems)} structural problem(s), "
              f"{len(all_unknown)} unresolved identifier(s)")
        return 1
    print(f"OK: {len(files)} file(s) clean - balanced delimiters, buffer/plot "
          f"counts consistent, every call resolves with a matching argument "
          f"count, every identifier declared; {len(used_builtins)} MQL5 "
          f"builtins used, all confirmed in the reference corpus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
