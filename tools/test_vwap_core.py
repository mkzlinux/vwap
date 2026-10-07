#!/usr/bin/env python3
"""
Turn MQL5/Include/WeltradeVWAP/VwapCore.mqh into C and run its real logic.

MetaEditor cannot run here, so the indicator itself is unverified. But the
arithmetic that decides every signal lives in VwapCore.mqh, and that file is
mechanically translatable to C: the only MQL5-isms it uses are array-reference
parameters, datetime, MqlDateTime/TimeToStruct and ArrayResize. This script
rewrites those and nothing else, so the branch structure, the prefix sums and
the session-anchor selection that get executed are the shipped ones.

Run:  python3 tools/test_vwap_core.py
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "MQL5" / "Include" / "WeltradeVWAP" / "VwapCore.mqh"
MAXB = 200000

PROLOGUE = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <stdbool.h>
#include <float.h>

#define MAXB %d
typedef long datetime;
typedef struct { int year,mon,day,hour,min,sec,day_of_week,day_of_year; } MqlDateTime;

static int  TimeToStruct(datetime t, MqlDateTime *d)
{
   time_t tt=(time_t)t; struct tm g = *gmtime(&tt);
   d->year=g.tm_year+1900; d->mon=g.tm_mon+1;  d->day=g.tm_mday;
   d->hour=g.tm_hour;      d->min=g.tm_min;    d->sec=g.tm_sec;
   d->day_of_week=g.tm_wday; d->day_of_year=g.tm_yday+1;
   return 1;
}
#define MathMax(a,b) ((a)>(b)?(a):(b))
#define MathMin(a,b) ((a)<(b)?(a):(b))
/* ArrayResize returns the new size on success, so the shipped
   "if(ArrayResize(x,n)!=n) return false" guards keep working. */
#define ArrayResize(a,n) (n)
#define EMPTY_VALUE DBL_MAX
""" % MAXB

HARNESS = r"""
/* ============================ tests ============================ */
static int failures = 0;

static void check_close(const char *what, double got, double want, double tol)
{
   if (fabs(got-want) > tol) {
      printf("  FAIL %-46s got %.10f want %.10f\n", what, got, want);
      failures++;
   } else {
      printf("  ok   %-46s %.10f\n", what, got);
   }
}
static void check_eq(const char *what, long got, long want)
{
   if (got != want) {
      printf("  FAIL %-46s got %ld want %ld\n", what, got, want);
      failures++;
   } else {
      printf("  ok   %-46s %ld\n", what, got);
   }
}

/* Independent textbook VWAP over an explicit window - deliberately naive so it
   shares no code with VwapFill. */
static double naive_vwap(const double *o,const double *h,const double *l,
                         const double *c,const long *v,int a,int b)
{
   double pv=0.0, vv=0.0;
   for (int i=a;i<=b;i++) { double vol=(double)v[i]; pv += ((o[i]+h[i]+l[i]+c[i])/4.0)*vol; vv += vol; }
   return vv>0.0 ? pv/vv : 0.0;
}

#define N 30
int main(void)
{
   double  open[N], high[N], low[N], close[N], tp[N], dst[N];
   long    vol[N];
   datetime tm[N];

   /* 2024-01-08 is a Monday. 30 hourly bars from 2024-01-08 00:00 UTC. */
   datetime t0 = 1704672000;
   for (int i=0;i<N;i++) {
      tm[i]    = t0 + i*3600;
      open[i]  = 100.0 + i*0.5;
      high[i]  = open[i] + 1.0;
      low[i]   = open[i] - 1.0;
      close[i] = open[i] + 0.25;
      tp[i]    = (open[i]+high[i]+low[i]+close[i])/4.0;
      vol[i]   = 10 + (i*7)%13;          /* varied, never zero */
      dst[i]   = EMPTY_VALUE;
   }

   printf("--- 1. typical price is (O+H+L+C)/4 ---\n");
   check_close("tp[0]", VwapTypicalPrice(open[0],high[0],low[0],close[0]),
               (open[0]+high[0]+low[0]+close[0])/4.0, 1e-12);

   printf("--- 2. session anchors ---\n");
   /* bar 0 = Mon 00:00. With a 00:00 daily session every bar is its own session. */
   check_eq("daily 00:00 -> bar0 is its own start",
            (long)VwapSessionStart(tm[0], VWAP_ANCHOR_DAILY_MIDNIGHT,0,0), (long)tm[0]);
   /* bar 23 = Mon 23:00, so its daily session started at Mon 00:00 = tm[0]. */
   check_eq("daily 00:00 -> bar23 anchors to bar0",
            (long)VwapSessionStart(tm[23], VWAP_ANCHOR_DAILY_MIDNIGHT,0,0), (long)tm[0]);

   /* Session start hour 13:00: bar 10 is Mon 10:00, which is BEFORE 13:00,
      so its session belongs to the previous day (Sun 13:00). */
   check_eq("daily 13:00 -> 10:00 bar rolls back a day",
            (long)VwapSessionStart(tm[10], VWAP_ANCHOR_DAILY_CUSTOM,13,0), (long)(t0-86400+13*3600));
   /* bar 13 is Mon 13:00 exactly -> its own session start. */
   check_eq("daily 13:00 -> 13:00 bar starts the session",
            (long)VwapSessionStart(tm[13], VWAP_ANCHOR_DAILY_CUSTOM,13,0), (long)tm[13]);
   /* bar 20 is Mon 20:00 -> same session as bar 13. */
   check_eq("daily 13:00 -> 20:00 bar shares bar13 session",
            (long)VwapSessionStart(tm[20], VWAP_ANCHOR_DAILY_CUSTOM,13,0), (long)tm[13]);

   /* Weekly: every bar of that Monday belongs to the Monday 00:00 session. */
   check_eq("weekly -> bar0 anchors to Monday 00:00",
            (long)VwapSessionStart(tm[0], VWAP_ANCHOR_WEEKLY,0,0), (long)t0);
   check_eq("weekly -> bar23 still anchors to Monday",
            (long)VwapSessionStart(tm[23], VWAP_ANCHOR_WEEKLY,0,0), (long)t0);
   /* A Wednesday 09:00 (2024-01-10) must roll back to that same Monday. */
   datetime wed = t0 + 2*86400 + 9*3600;
   check_eq("weekly -> Wednesday rolls back to Monday",
            (long)VwapSessionStart(wed, VWAP_ANCHOR_WEEKLY,0,0), (long)t0);
   /* A Sunday (2024-01-07, day_of_week 0) belongs to the PREVIOUS Monday. */
   datetime sun = t0 - 86400 + 12*3600;
   check_eq("weekly -> Sunday belongs to previous Monday",
            (long)VwapSessionStart(sun, VWAP_ANCHOR_WEEKLY,0,0), (long)(t0-7*86400));

   printf("--- 3. daily VWAP accumulates over the session ---\n");
   int ok = VwapFill(tp,vol,tm,0,N-1,VWAP_ANCHOR_DAILY_MIDNIGHT,0,0,240,dst);
   check_eq("VwapFill returned success", (long)ok, 1);
   /* bars 0..23 are all Monday -> one accumulating session;
      bars 24..29 are Tuesday -> a fresh session. */
   for (int i=0;i<24;i++) {
      char lbl[64]; sprintf(lbl,"daily VWAP bar %d (cumulative)", i);
      check_close(lbl, dst[i], naive_vwap(open,high,low,close,vol,0,i), 1e-9);
   }
   for (int i=24;i<N;i++) {
      char lbl[64]; sprintf(lbl,"daily VWAP bar %d (Tuesday reset)", i);
      check_close(lbl, dst[i], naive_vwap(open,high,low,close,vol,24,i), 1e-9);
   }

   printf("--- 4. custom 13:00 session resets mid-series ---\n");
   for (int i=0;i<N;i++) dst[i]=EMPTY_VALUE;
   VwapFill(tp,vol,tm,0,N-1,VWAP_ANCHOR_DAILY_CUSTOM,13,0,240,dst);
   for (int i=0;i<13;i++) {
      char lbl[64]; sprintf(lbl,"13:00 session, bar %d from bar0", i);
      check_close(lbl, dst[i], naive_vwap(open,high,low,close,vol,0,i), 1e-9);
   }
   for (int i=13;i<N;i++) {
      char lbl[64]; sprintf(lbl,"13:00 session, bar %d resets at bar13", i);
      check_close(lbl, dst[i], naive_vwap(open,high,low,close,vol,13,i), 1e-9);
   }

   printf("--- 5. weekly VWAP never resets inside the week ---\n");
   for (int i=0;i<N;i++) dst[i]=EMPTY_VALUE;
   VwapFill(tp,vol,tm,0,N-1,VWAP_ANCHOR_WEEKLY,0,0,240,dst);
   for (int i=0;i<N;i++) {
      char lbl[64]; sprintf(lbl,"weekly VWAP bar %d", i);
      check_close(lbl, dst[i], naive_vwap(open,high,low,close,vol,0,i), 1e-9);
   }

   printf("--- 6. rolling window of 5 bars ---\n");
   for (int i=0;i<N;i++) dst[i]=EMPTY_VALUE;
   VwapFill(tp,vol,tm,0,N-1,VWAP_ANCHOR_ROLLING,0,0,5,dst);
   for (int i=0;i<N;i++) {
      int a = i-4; if (a<0) a=0;
      char lbl[64]; sprintf(lbl,"rolling(5) VWAP bar %d window[%d..%d]", i, a, i);
      check_close(lbl, dst[i], naive_vwap(open,high,low,close,vol,a,i), 1e-9);
   }

   printf("--- 7. partial fill writes only [from..to] ---\n");
   for (int i=0;i<N;i++) dst[i]=EMPTY_VALUE;
   VwapFill(tp,vol,tm,24,N-1,VWAP_ANCHOR_DAILY_MIDNIGHT,0,0,240,dst);
   check_eq("bars before 'from' untouched",
            (long)(dst[10]==EMPTY_VALUE), 1);
   for (int i=24;i<N;i++) {
      char lbl[64]; sprintf(lbl,"partial fill bar %d", i);
      check_close(lbl, dst[i], naive_vwap(open,high,low,close,vol,24,i), 1e-9);
   }

   printf("--- 8. zero-volume bars do not break the line ---\n");
   long zv[N];
   for (int i=0;i<N;i++) zv[i]=vol[i];
   zv[0]=0; zv[1]=0; zv[2]=0;
   for (int i=0;i<N;i++) dst[i]=EMPTY_VALUE;
   VwapFill(tp,zv,tm,0,2,VWAP_ANCHOR_DAILY_MIDNIGHT,0,0,240,dst);
   for (int i=0;i<3;i++) {
      char lbl[64]; sprintf(lbl,"all-zero-volume bar %d falls back to TP", i);
      check_close(lbl, dst[i], tp[i], 1e-12);
   }
   /* a single zero-volume bar inside a live session is simply skipped */
   long zv2[N]; for (int i=0;i<N;i++) zv2[i]=vol[i]; zv2[2]=0;
   for (int i=0;i<N;i++) dst[i]=EMPTY_VALUE;
   VwapFill(tp,zv2,tm,0,5,VWAP_ANCHOR_DAILY_MIDNIGHT,0,0,240,dst);
   {
      double pv=0.0,vv=0.0;
      for (int i=0;i<=5;i++) if (zv2[i]>0) { pv+=tp[i]*(double)zv2[i]; vv+=(double)zv2[i]; }
      check_close("zero-volume bar 2 excluded, bar5 VWAP", dst[5], pv/vv, 1e-9);
   }

   printf("\n%s (%d failure(s))\n", failures? "FAILED":"ALL TESTS PASSED", failures);
   return failures?1:0;
}
"""


def strip_preproc_and_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    out = []
    for ln in text.split("\n"):
        if ln.lstrip().startswith("#"):
            continue
        out.append(ln)
    return "\n".join(out)


def drop_function(text, name):
    """Remove a whole function definition by brace matching."""
    m = re.search(r"\b(?:string|double|int|bool|void)\s+" + name + r"\s*\(", text)
    if not m:
        raise SystemExit(f"could not find function {name} to drop")
    i = text.index("{", m.end())
    depth, j = 0, i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[:m.start()] + text[j + 1:]
        j += 1
    raise SystemExit(f"unbalanced braces in {name}")


def transpile(src_text):
    c = strip_preproc_and_comments(src_text)
    # VwapAnchorText only exists for on-chart labels and uses MQL5 strings
    c = drop_function(c, "VwapAnchorText")
    # array-reference parameters -> pointers
    c = re.sub(r"\bconst\s+(double|long|int|datetime)\s*&\s*(\w+)\s*\[\s*\]", r"const \1 *\2", c)
    c = re.sub(r"\b(double|long|int|datetime)\s*&\s*(\w+)\s*\[\s*\]", r"\1 *\2", c)
    # local unsized array declarations -> fixed size
    c = re.sub(r"^\s*(double|long|int)\s+(\w+)\s*\[\s*\]\s*;", r"   \1 \2[MAXB];", c, flags=re.M)
    # C needs "enum NAME"; MQL5 lets you write the bare type name
    def add_typedef(m):
        return m.group(0) + "\ntypedef enum %s %s;" % (m.group(1), m.group(1))
    c = re.sub(r"\benum\s+(\w+)\s*\{[^}]*\};", add_typedef, c)
    # MQL5 passes MqlDateTime by reference; the C shim takes a pointer
    c = re.sub(r"\bTimeToStruct\(([^,()]+),\s*(\w+)\s*\)", r"TimeToStruct(\1,&\2)", c)
    # datetime is a typedef in the prologue
    c = c.replace("datetime ", "datetime ")
    return c


def main():
    if not SRC.exists():
        print(f"missing source: {SRC}")
        return 2

    body = transpile(SRC.read_text(encoding="utf-8"))
    program = PROLOGUE + "\n" + body + "\n" + HARNESS

    with tempfile.TemporaryDirectory() as d:
        c_file = Path(d) / "vwap_core.c"
        exe = Path(d) / "vwap_core_test"
        c_file.write_text(program)
        cc = subprocess.run(["gcc", "-std=c99", "-O1", "-Wall", "-Wextra",
                             "-Wno-unused-parameter", "-o", str(exe), str(c_file), "-lm"],
                            capture_output=True, text=True)
        if cc.returncode != 0:
            print("gcc failed to build the transpiled VwapCore.mqh:")
            print(cc.stdout)
            print(cc.stderr)
            return 2
        if cc.stderr.strip():
            print("gcc warnings:")
            print(cc.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        print(run.stdout, end="")
        if run.stderr.strip():
            print(run.stderr, end="")
        return run.returncode


if __name__ == "__main__":
    sys.exit(main())
