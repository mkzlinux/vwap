//+------------------------------------------------------------------+
//|                                  WeltradeVWAP_9EMA_Signals.mq5   |
//|                                                                  |
//|  Session VWAP ((O+H+L+C)/4, no bands) + 9 EMA.                   |
//|  SIGNALS ONLY - this is an indicator, it cannot place, modify    |
//|  or close any order. Each signal paints a TradingView-style      |
//|  risk box: red = stop loss zone, green = take profit zone.       |
//+------------------------------------------------------------------+
#property copyright   "Weltrade VWAP + 9 EMA signal suite"
#property link        ""
#property version     "1.00"
#property description "Session VWAP ((O+H+L+C)/4, no bands) crossed with a 9 EMA."
#property description "Signals only - no order is ever sent. Draws SL/TP boxes at a chosen R:R."
#property indicator_chart_window
#property indicator_buffers 5
#property indicator_plots   4
//--- VWAP line (2-colour, coloured by slope)
#property indicator_label1  "VWAP"
#property indicator_type1   DRAW_COLOR_LINE
#property indicator_color1  clrDodgerBlue,clrOrangeRed
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2
//--- 9 EMA
#property indicator_label2  "EMA 9"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrGold
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1
//--- Buy signal arrow
#property indicator_label3  "Long signal"
#property indicator_type3   DRAW_ARROW
#property indicator_color3  clrLime
#property indicator_width3  2
//--- Sell signal arrow
#property indicator_label4  "Short signal"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrRed
#property indicator_width4  2

#include <WeltradeVWAP/VwapCore.mqh>

//+------------------------------------------------------------------+
//| Entry modes                                                      |
//+------------------------------------------------------------------+
enum ENUM_VWAP_ENTRY_MODE
  {
   ENTRY_EMA_CROSS_VWAP = 0,  // EMA(9) crosses VWAP
   ENTRY_TREND_STACK    = 1,  // Price + EMA + VWAP aligned
   ENTRY_VWAP_PULLBACK  = 2   // Pullback to VWAP, EMA filter
  };

//+------------------------------------------------------------------+
//| Price the 9 EMA is calculated on                                 |
//+------------------------------------------------------------------+
enum ENUM_VWAP_EMA_PRICE
  {
   EMA_ON_CLOSE   = 0,  // Close
   EMA_ON_TYPICAL = 1   // Typical (O+H+L+C)/4
  };

//+------------------------------------------------------------------+
//| ENUM_VWAP_AMBIG (how to treat a bar that touches both levels)    |
//| lives in VwapCore.mqh alongside VwapEvaluateOutcome(), so the    |
//| outcome rule is shared rather than duplicated here.              |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "VWAP session"
input ENUM_VWAP_ANCHOR   InpAnchor         = VWAP_ANCHOR_DAILY_CUSTOM; // VWAP anchor
input int                InpSessionHour    = 0;      // Session start hour (server time)
input int                InpSessionMinute  = 0;      // Session start minute
input int                InpRollingBars    = 240;    // Rolling lookback bars (rolling anchor)
input bool               InpUseRealVolume  = false;  // Use real volume if the feed provides it

input group "Signals"
input ENUM_VWAP_ENTRY_MODE InpEntryMode    = ENTRY_EMA_CROSS_VWAP; // Entry mode
input int                InpEmaPeriod      = 9;      // EMA period
input ENUM_VWAP_EMA_PRICE InpEmaPrice      = EMA_ON_CLOSE;  // EMA applied price
input double             InpTouchTolerancePoints = 10; // Pullback mode: points from VWAP that count as a touch
input bool               InpRequireReclaim = true;   // Pullback mode: require close back through VWAP

input group "Risk / reward box"
input int                InpAtrPeriod      = 14;     // ATR period for the stop distance
input double             InpSlAtrMult      = 1.5;    // Stop loss = ATR x this
input double             InpRewardR        = 3.0;    // Reward in R (1 : N)
input int                InpBoxWidthBars   = 24;     // Box width, in bars
input bool               InpShowRMultiples = true;   // Dotted line at each whole R
input bool               InpZonesBehindPrice = true; // Draw boxes behind the candles

input group "Colours"
input color              InpColorProfit    = clrSeaGreen;  // Take profit zone
input color              InpColorLoss      = clrFireBrick; // Stop loss zone
input color              InpColorUp        = clrDodgerBlue;// VWAP rising
input color              InpColorDown      = clrOrangeRed; // VWAP falling
input bool               InpUseTransparency = false;       // Blend the boxes with ARGB alpha
input uchar              InpFillAlpha      = 55;           // Alpha when blending is on (0 solid - 255 clear)

input group "Alerts (signals only)"
input bool               InpAlertPopup     = true;   // Popup alert
input bool               InpAlertSound     = false;  // Sound alert
input string             InpSoundFile      = "alert.wav"; // Sound file
input bool               InpAlertPush      = false;  // Push notification
input bool               InpAlertEmail     = false;  // Email

input group "Outcome marking"
input bool               InpMarkOutcome    = true;           // Mark when SL or TP is hit
input bool               InpTruncateOnHit  = true;           // End the box at the hit bar
input ENUM_VWAP_AMBIG    InpAmbiguousFirst = AMBIG_SL_FIRST; // One bar touches both
input bool               InpShowStats      = true;           // Hit rate and expectancy in the panel

input group "Display"
input int                InpMaxSignals     = 40;     // Max boxes on the chart
input int                InpHistoryBars    = 500;    // Bars back to search for boxes
input bool               InpShowPanel      = true;   // Show the status panel
input bool               InpDeleteOnRemove = true;   // Delete all objects when the indicator is removed

//+------------------------------------------------------------------+
//| Buffers                                                          |
//+------------------------------------------------------------------+
double BufVwap[];
double BufVwapColor[];
double BufEma[];
double BufArrowUp[];
double BufArrowDn[];

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
string   g_prefix        = "WTVWAP9_";
datetime g_cache_bar     = 0;
int      g_cache_start   = -1;
int      g_cache_total   = -1;
datetime g_last_alert    = 0;
int      g_box_count     = 0;
int      g_tp_hits       = 0;
int      g_sl_hits       = 0;
int      g_open_sigs     = 0;

//+------------------------------------------------------------------+
//| Object-name stem for the signal on bar time t. Shared by the box |
//| drawing, the outcome marking and the trimming, so the three can  |
//| never disagree about which objects belong to which signal.       |
//+------------------------------------------------------------------+
string SignalBoxName(const datetime t,const int dir)
  {
   return(g_prefix+IntegerToString((long)t)+"_"+(dir>0?"L":"S"));
  }

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0,BufVwap,INDICATOR_DATA);
   SetIndexBuffer(1,BufVwapColor,INDICATOR_COLOR_INDEX);
   SetIndexBuffer(2,BufEma,INDICATOR_DATA);
   SetIndexBuffer(3,BufArrowUp,INDICATOR_DATA);
   SetIndexBuffer(4,BufArrowDn,INDICATOR_DATA);

   PlotIndexSetInteger(0,PLOT_COLOR_INDEXES,2);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,0,(long)InpColorUp);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,1,(long)InpColorDown);
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,EMPTY_VALUE);

   PlotIndexSetDouble(1,PLOT_EMPTY_VALUE,EMPTY_VALUE);

   PlotIndexSetInteger(2,PLOT_ARROW,233);
   PlotIndexSetInteger(2,PLOT_ARROW_SHIFT,-12);
   PlotIndexSetDouble(2,PLOT_EMPTY_VALUE,EMPTY_VALUE);

   PlotIndexSetInteger(3,PLOT_ARROW,234);
   PlotIndexSetInteger(3,PLOT_ARROW_SHIFT,12);
   PlotIndexSetDouble(3,PLOT_EMPTY_VALUE,EMPTY_VALUE);

   if(InpEmaPeriod<1)
     {
      Print("EMA period must be 1 or more.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpRewardR<=0.0)
     {
      Print("Reward (R) must be greater than zero.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   IndicatorSetString(INDICATOR_SHORTNAME,
                      "VWAP+EMA("+IntegerToString(InpEmaPeriod)+") 1:"+DoubleToString(InpRewardR,1));
   IndicatorSetInteger(INDICATOR_DIGITS,_Digits);

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(InpDeleteOnRemove)
      ObjectsDeleteAll(0,g_prefix,-1,-1);
   Comment("");
  }

//+------------------------------------------------------------------+
//| Small drawing helpers                                            |
//+------------------------------------------------------------------+
void MakeLine(const string name,const datetime t1,const double p1,const datetime t2,const double p2,
              const color clr,const ENUM_LINE_STYLE style,const int width)
  {
   if(ObjectFind(0,name)<0)
      if(!ObjectCreate(0,name,OBJ_TREND,0,t1,p1,t2,p2))
         return;
   ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,name,OBJPROP_STYLE,style);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,width);
   ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,false);
   ObjectSetInteger(0,name,OBJPROP_RAY_LEFT,false);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }

void MakeZone(const string name,const datetime t1,const double p1,const datetime t2,const double p2,const color clr)
  {
   if(ObjectFind(0,name)<0)
      if(!ObjectCreate(0,name,OBJ_RECTANGLE,0,t1,p1,t2,p2))
         return;
   //--- ARGB alpha on a chart object is a documented MQL5 feature, but it is
   //--- not the default here: solid fill + draw order is the behaviour that is
   //--- reproducible on every build. Turn blending on if you prefer it.
   if(InpUseTransparency)
      ObjectSetInteger(0,name,OBJPROP_COLOR,ColorToARGB(clr,InpFillAlpha));
   else
      ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,name,OBJPROP_FILL,true);
   ObjectSetInteger(0,name,OBJPROP_BACK,InpZonesBehindPrice);
   ObjectSetInteger(0,name,OBJPROP_STYLE,STYLE_SOLID);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,1);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }

void MakeText(const string name,const datetime t,const double p,const string txt,
              const color clr,const int size,const ENUM_ANCHOR_POINT anchor)
  {
   if(ObjectFind(0,name)<0)
      if(!ObjectCreate(0,name,OBJ_TEXT,0,t,p))
         return;
   ObjectSetString(0,name,OBJPROP_TEXT,txt);
   ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,anchor);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
  }

//+------------------------------------------------------------------+
//| Draw one signal box. Returns true only when it was NEWLY created |
//+------------------------------------------------------------------+
bool DrawSignalBox(const int dir,const datetime t,const double entry,const double sl,const double tp)
  {
   string base=SignalBoxName(t,dir);
   if(ObjectFind(0,base+"_e")>=0)
      return(false);

   datetime t2=t+(datetime)(MathMax(2,InpBoxWidthBars)*PeriodSeconds(_Period));

   //--- like TradingView's position tool the loss zone is always red and the
   //--- profit zone always green; the side is shown by the arrow, the label
   //--- and which side of the entry line each zone sits on.
   color pc=InpColorProfit;
   color lc=InpColorLoss;

   //--- loss zone (entry -> SL) and profit zone (entry -> TP)
   MakeZone(base+"_lz",t,entry,t2,sl,lc);
   MakeZone(base+"_pz",t,entry,t2,tp,pc);

   //--- entry / stop / target rails
   MakeLine(base+"_e", t,entry,t2,entry,clrSilver,STYLE_SOLID,1);
   MakeLine(base+"_sl",t,sl,   t2,sl,   lc,STYLE_DASH,1);
   MakeLine(base+"_tp",t,tp,   t2,tp,   pc,STYLE_DASH,1);

   //--- dotted rail at every whole R inside the profit zone
   if(InpShowRMultiples)
     {
      double risk=MathAbs(entry-sl);
      int    steps=(int)MathFloor(InpRewardR+1e-8);
      for(int r=1;r<steps;r++)
        {
         double lvl=(dir>0? entry+risk*r : entry-risk*r);
         MakeLine(base+"_r"+IntegerToString(r),t,lvl,t2,lvl,pc,STYLE_DOT,1);
        }
     }

   //--- labels
   string rr=RewardText();
   string risk_txt=DoubleToString(MathAbs(entry-sl)/_Point,0)+" pts";
   string tag=(dir>0?"LONG  ":"SHORT ")+rr+"  ("+risk_txt+" risk)";

   MakeText(base+"_tag",t,entry,tag,clrWhite,8,ANCHOR_LEFT_LOWER);
   MakeText(base+"_tpl",t2,tp,"TP +"+DoubleToString(InpRewardR,1)+"R  "+DoubleToString(tp,_Digits),pc,8,
            (dir>0?ANCHOR_LEFT_UPPER:ANCHOR_LEFT_LOWER));
   MakeText(base+"_sll",t2,sl,"SL -1R  "+DoubleToString(sl,_Digits),lc,8,
            (dir>0?ANCHOR_LEFT_LOWER:ANCHOR_LEFT_UPPER));

   ChartRedraw(0);
   return(true);
  }

//+------------------------------------------------------------------+
//| Walk forward from the signal bar and report which level price    |
//| reached first. Returns +1 take profit, -1 stop loss, 0 neither.  |
//| Only closed bars are considered, so an outcome never flickers.   |
//+------------------------------------------------------------------+
//| Resolve a signal against later price action. The scan itself is  |
//| VwapEvaluateOutcome() in VwapCore.mqh, which is covered by       |
//| tools/test_vwap_core.py - this wrapper only supplies the inputs. |
//+------------------------------------------------------------------+
int EvaluateOutcome(const int dir,
                    const int sig_bar,
                    const int last_closed,
                    const double sl,
                    const double tp,
                    const double &high[],
                    const double &low[],
                    int &hit_bar)
  {
   return(VwapEvaluateOutcome(dir,sig_bar,last_closed,sl,tp,high,low,
                              InpAmbiguousFirst,hit_bar));
  }

//+------------------------------------------------------------------+
//| Move every rail and zone of a box so it ends at t_end            |
//+------------------------------------------------------------------+
void SetBoxEnd(const string base,const datetime t_end)
  {
   ObjectSetInteger(0,base+"_lz",OBJPROP_TIME,1,t_end);
   ObjectSetInteger(0,base+"_pz",OBJPROP_TIME,1,t_end);
   ObjectSetInteger(0,base+"_e", OBJPROP_TIME,1,t_end);
   ObjectSetInteger(0,base+"_sl",OBJPROP_TIME,1,t_end);
   ObjectSetInteger(0,base+"_tp",OBJPROP_TIME,1,t_end);

   int steps=(int)MathFloor(InpRewardR+1e-8);
   for(int r=1;r<steps;r++)
      ObjectSetInteger(0,base+"_r"+IntegerToString(r),OBJPROP_TIME,1,t_end);

   //--- the two right-edge labels travel with the rails
   ObjectSetInteger(0,base+"_tpl",OBJPROP_TIME,0,t_end);
   ObjectSetInteger(0,base+"_sll",OBJPROP_TIME,0,t_end);
  }

//+------------------------------------------------------------------+
//| Mark the result of a signal once price has resolved it.          |
//| Idempotent: safe to call on every pass, it only ever moves       |
//| objects to where they already are.                               |
//+------------------------------------------------------------------+
void MarkOutcome(const string base,
                 const int dir,
                 const int sig_bar,
                 const int last_closed,
                 const double sl,
                 const double tp,
                 const datetime &time[],
                 const double &high[],
                 const double &low[])
  {
   int hit_bar=0;
   int outcome=EvaluateOutcome(dir,sig_bar,last_closed,sl,tp,high,low,hit_bar);

   if(outcome==0)
     {
      g_open_sigs++;
      //--- nothing resolved yet: drop any stale mark and restore full width
      if(ObjectFind(0,base+"_mk")>=0)
        {
         ObjectDelete(0,base+"_mk");
         ObjectDelete(0,base+"_mktx");
         SetBoxEnd(base,time[sig_bar]+(datetime)(MathMax(2,InpBoxWidthBars)*PeriodSeconds(_Period)));
        }
      return;
     }

   if(outcome>0)
      g_tp_hits++;
   else
      g_sl_hits++;

   color   clr=(outcome>0?InpColorProfit:InpColorLoss);
   double  lvl=(outcome>0?tp:sl);
   datetime ht=time[hit_bar];

   //--- arrow marker: up = target reached, down = stop reached
   string mk=base+"_mk";
   if(ObjectFind(0,mk)<0)
      if(!ObjectCreate(0,mk,OBJ_ARROW,0,ht,lvl))
         return;
   ObjectSetInteger(0,mk,OBJPROP_ARROWCODE,outcome>0?233:234);
   ObjectSetInteger(0,mk,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,mk,OBJPROP_WIDTH,2);
   ObjectSetInteger(0,mk,OBJPROP_BACK,false);
   ObjectSetInteger(0,mk,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,mk,OBJPROP_HIDDEN,true);

   //--- text marker
   string txt=(outcome>0?"TP +":"SL -")+DoubleToString(InpRewardR,1)+"R";
   MakeText(base+"_mktx",ht,lvl,txt,clr,8,
            (outcome>0?ANCHOR_LEFT_UPPER:ANCHOR_LEFT_LOWER));

   //--- end the box where the trade ended
   if(InpTruncateOnHit)
      SetBoxEnd(base,ht);
  }

//+------------------------------------------------------------------+
//| Keep only the newest InpMaxSignals boxes on the chart.           |
//| The bar time is embedded in every object name, so trimming is    |
//| deterministic and does not depend on the object list order.      |
//+------------------------------------------------------------------+
void TrimBoxes(void)
  {
   int keep=MathMax(1,InpMaxSignals);

   long   times[];
   string bases[];
   int    found=0;

   int total=ObjectsTotal(0,-1,OBJ_RECTANGLE);
   for(int i=0;i<total;i++)
     {
      string nm=ObjectName(0,i,-1,OBJ_RECTANGLE);
      if(StringFind(nm,g_prefix)!=0)
         continue;
      if(StringFind(nm,"_lz")<0)
         continue;

      string rest=StringSubstr(nm,StringLen(g_prefix));
      int    us=StringFind(rest,"_");
      if(us<=0)
         continue;

      found++;
      if(ArrayResize(times,found)!=found)
         return;
      if(ArrayResize(bases,found)!=found)
         return;
      times[found-1]=StringToInteger(StringSubstr(rest,0,us));
      bases[found-1]=StringSubstr(nm,0,StringLen(nm)-3);
     }

   g_box_count=found;
   if(found<=keep)
      return;

   //--- delete the (found-keep) oldest signal groups
   int excess=found-keep;
   for(int d=0;d<excess;d++)
     {
      int    oldest=-1;
      long   oldest_time=0;
      for(int j=0;j<found;j++)
        {
         if(bases[j]=="")
            continue;
         if(oldest<0 || times[j]<oldest_time)
           {
            oldest=j;
            oldest_time=times[j];
           }
        }
      if(oldest<0)
         break;
      ObjectsDeleteAll(0,bases[oldest],-1,-1);
      bases[oldest]="";
     }

   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| Signal on bar i using bars i (new) and i-1 (old)                 |
//+------------------------------------------------------------------+
int SignalAt(const int i,
             const double &vwap[],
             const double &ema[],
             const double &open[],
             const double &high[],
             const double &low[],
             const double &close[])
  {
   double v1=vwap[i];
   double v2=vwap[i-1];
   double e1=ema[i];
   double e2=ema[i-1];

   double tol=InpTouchTolerancePoints*_Point;

   switch(InpEntryMode)
     {
      case ENTRY_EMA_CROSS_VWAP:
        {
         if(e2<=v2 && e1>v1) return(1);
         if(e2>=v2 && e1<v1) return(-1);
         return(0);
        }

      case ENTRY_TREND_STACK:
        {
         bool up1=(close[i]>v1) && (close[i]>e1) && (e1>v1);
         bool up2=(close[i-1]>v2) && (close[i-1]>e2) && (e2>v2);
         bool dn1=(close[i]<v1) && (close[i]<e1) && (e1<v1);
         bool dn2=(close[i-1]<v2) && (close[i-1]<e2) && (e2<v2);
         if(up1 && !up2) return(1);
         if(dn1 && !dn2) return(-1);
         return(0);
        }

      case ENTRY_VWAP_PULLBACK:
        {
         bool up_trend=(e1>v1);
         bool dn_trend=(e1<v1);
         bool touched_up  =(low[i] <=v1+tol);
         bool touched_down=(high[i]>=v1-tol);
         bool long_sig =up_trend && touched_up   && (!InpRequireReclaim || close[i]>v1);
         bool short_sig=dn_trend && touched_down && (!InpRequireReclaim || close[i]<v1);
         if(long_sig && !short_sig)  return(1);
         if(short_sig && !long_sig)  return(-1);
         return(0);
        }
     }
   return(0);
  }

//+------------------------------------------------------------------+
//| Signal plus its entry/SL/TP for bar i.                           |
//| Returns false when bar i carries no usable signal.               |
//+------------------------------------------------------------------+
bool SignalBoxAt(const int i,
                 const double &open[],
                 const double &high[],
                 const double &low[],
                 const double &close[],
                 int    &dir,
                 double &entry,
                 double &sl,
                 double &tp,
                 double &atr)
  {
   dir=0;
   if(BufVwap[i]==EMPTY_VALUE || BufVwap[i-1]==EMPTY_VALUE)
      return(false);
   if(BufEma[i]==EMPTY_VALUE  || BufEma[i-1]==EMPTY_VALUE)
      return(false);

   dir=SignalAt(i,BufVwap,BufEma,open,high,low,close);
   if(dir==0)
      return(false);

   //--- ATR-based stop distance, measured on the signal bar
   double a=AtrAt(i,InpAtrPeriod,high,low,close);
   if(a<=0.0)
     {
      dir=0;
      return(false);
     }

   atr=a;
   entry=close[i];
   double risk=a*InpSlAtrMult;
   if(dir>0)
     {
      sl=entry-risk;
      tp=entry+risk*InpRewardR;
     }
   else
     {
      sl=entry+risk;
      tp=entry-risk*InpRewardR;
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Friendly name of the active entry mode                           |
//+------------------------------------------------------------------+
string ModeText(void)
  {
   switch(InpEntryMode)
     {
      case ENTRY_EMA_CROSS_VWAP: return("EMA cross VWAP");
      case ENTRY_TREND_STACK:    return("Price+EMA+VWAP stack");
      case ENTRY_VWAP_PULLBACK:  return("VWAP pullback");
     }
   return("EMA cross VWAP");
  }

//+------------------------------------------------------------------+
//| "1:3" style reward text                                          |
//+------------------------------------------------------------------+
string RewardText(void)
  {
   return("1:"+DoubleToString(InpRewardR,(InpRewardR==MathRound(InpRewardR)?0:1)));
  }

//+------------------------------------------------------------------+
//| Alert plumbing                                                   |
//+------------------------------------------------------------------+
void FireAlert(const int dir,const datetime t,const double entry,const double sl,const double tp)
  {
   if(t==g_last_alert)
      return;
   g_last_alert=t;

   string side=(dir>0?"LONG":"SHORT");
   string risk_pts=DoubleToString(MathAbs(entry-sl)/_Point,0);
   string body=StringFormat("VWAP+EMA%d %s  %s  %s   entry %s   SL %s   TP %s   %s",
                            InpEmaPeriod,side,_Symbol,ModeText(),
                            DoubleToString(entry,_Digits),
                            DoubleToString(sl,_Digits),
                            DoubleToString(tp,_Digits),
                            RewardText());

   if(InpAlertPopup)
      Alert(body+"   ("+risk_pts+" pts risk)");
   if(InpAlertSound)
      PlaySound(InpSoundFile);
   if(InpAlertPush)
      SendNotification(body);
   if(InpAlertEmail)
      SendMail("VWAP+EMA "+side+" "+_Symbol,body);
  }

//+------------------------------------------------------------------+
//| OnCalculate                                                      |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total<InpEmaPeriod+3)
      return(0);

   bool full=(prev_calculated<=0);
   if(full)
     {
      //--- a full pass rebuilds everything, so clear the arrow plots completely
      ArrayInitialize(BufArrowUp,EMPTY_VALUE);
      ArrayInitialize(BufArrowDn,EMPTY_VALUE);
      //--- cached session start belongs to the previous series length
      g_cache_total=-1;
      g_cache_start=-1;
     }

   //--- EMA needs a contiguous run, so fall back to a full pass inside the warm-up
   int ema_start=0;
   if(!full && prev_calculated-1>=InpEmaPeriod)
      ema_start=prev_calculated-1;

   //--- VWAP must be recomputed from the start of the session it belongs to
   int vwap_start=0;
   if(!full)
     {
      datetime last_bar=time[rates_total-1];
      if(InpAnchor==VWAP_ANCHOR_ROLLING)
        {
         vwap_start=rates_total-1-(MathMax(2,InpRollingBars)-1);
        }
      else if(last_bar==g_cache_bar && rates_total==g_cache_total && g_cache_start>=0)
        {
         vwap_start=g_cache_start;
        }
      else
        {
         datetime key=VwapSessionStart(last_bar,InpAnchor,InpSessionHour,InpSessionMinute);
         vwap_start=rates_total-1;
         while(vwap_start>0 &&
               VwapSessionStart(time[vwap_start-1],InpAnchor,InpSessionHour,InpSessionMinute)==key)
            vwap_start--;
         g_cache_bar=last_bar;
         g_cache_total=rates_total;
         g_cache_start=vwap_start;
        }
      if(vwap_start<0)
         vwap_start=0;
      //--- Never recompute fewer bars than have appeared since last time. But
      //--- when we reach back we must land on a session boundary: stopping on
      //--- an arbitrary bar would accumulate that bar's VWAP from the wrong
      //--- anchor and overwrite a value an earlier pass had already got right.
      //--- This is exactly what happens on the first bar of a new session,
      //--- where the session start is the current bar itself.
      int need_from=prev_calculated-1;
      if(need_from<0)
         need_from=0;
      if(vwap_start>need_from)
        {
         if(InpAnchor==VWAP_ANCHOR_ROLLING)
           {
            //--- VwapFill reads back InpRollingBars-1 on its own, so the bar
            //--- itself is a valid anchor here
            vwap_start=need_from;
           }
         else
           {
            datetime nkey=VwapSessionStart(time[need_from],InpAnchor,
                                           InpSessionHour,InpSessionMinute);
            vwap_start=need_from;
            while(vwap_start>0 &&
                  VwapSessionStart(time[vwap_start-1],InpAnchor,
                                   InpSessionHour,InpSessionMinute)==nkey)
               vwap_start--;
           }
        }
      if(vwap_start<0)
         vwap_start=0;
     }

   //--- the rolling anchor reads further back than the range we write to
   int build_from=vwap_start;
   if(InpAnchor==VWAP_ANCHOR_ROLLING)
     {
      build_from=vwap_start-(MathMax(2,InpRollingBars)-1);
      if(build_from<0)
         build_from=0;
     }
   int tp_from=MathMin(build_from,ema_start);
   if(tp_from<0)
      tp_from=0;

   //--- typical price (O+H+L+C)/4 and the volume series
   double tp[];
   long   vol[];
   if(ArrayResize(tp,rates_total)!=rates_total)
      return(0);
   if(ArrayResize(vol,rates_total)!=rates_total)
      return(0);

   bool use_real=false;
   if(InpUseRealVolume)
     {
      long tot=0;
      for(int i=tp_from;i<rates_total;i++)
         tot+=volume[i];
      use_real=(tot>0);
     }

   for(int i=tp_from;i<rates_total;i++)
     {
      tp[i]=VwapTypicalPrice(open[i],high[i],low[i],close[i]);
      vol[i]=(use_real?volume[i]:tick_volume[i]);
     }

   if(!VwapFill(tp,vol,time,vwap_start,rates_total-1,
                InpAnchor,InpSessionHour,InpSessionMinute,InpRollingBars,BufVwap))
      return(0);

   //--- VWAP slope colouring
   for(int i=vwap_start;i<rates_total;i++)
     {
      if(i>0 && BufVwap[i-1]!=EMPTY_VALUE)
         BufVwapColor[i]=(BufVwap[i]<BufVwap[i-1]?1:0);
      else
         BufVwapColor[i]=0;
     }

   //--- 9 EMA, SMA seeded so the first value matches the classic definition
   double k=2.0/(InpEmaPeriod+1.0);
   double sum=0.0;
   for(int i=ema_start;i<rates_total;i++)
     {
      double s=(InpEmaPrice==EMA_ON_TYPICAL?tp[i]:close[i]);
      if(i<InpEmaPeriod-1)
        {
         sum+=s;
         BufEma[i]=EMPTY_VALUE;
        }
      else if(i==InpEmaPeriod-1)
        {
         sum+=s;
         BufEma[i]=sum/InpEmaPeriod;
        }
      else
         BufEma[i]=BufEma[i-1]+k*(s-BufEma[i-1]);
     }

   //--- signals on closed bars only
   int sig_start=MathMax(MathMax(vwap_start,ema_start),1);
   int last_closed=rates_total-2;

   //--- on an incremental pass clear only the range we are about to rewrite,
   //--- otherwise every arrow left by an earlier pass would be wiped
   if(!full)
     {
      for(int i=sig_start;i<rates_total;i++)
        {
         BufArrowUp[i]=EMPTY_VALUE;
         BufArrowDn[i]=EMPTY_VALUE;
        }
     }

   datetime newest=0;
   int      newest_dir=0;
   double   newest_entry=0.0,newest_sl=0.0,newest_tp=0.0;

   //--- pass 1: arrows over the whole recalculated range, plus the newest
   //--- signal for the alert. No chart objects are created here.
   for(int i=sig_start;i<=last_closed;i++)
     {
      int    dir=0;
      double entry=0.0,sl=0.0,tp=0.0,atr=0.0;
      if(!SignalBoxAt(i,open,high,low,close,dir,entry,sl,tp,atr))
         continue;

      if(dir>0)
         BufArrowUp[i]=low[i]-atr*0.35;
      else
         BufArrowDn[i]=high[i]+atr*0.35;

      if(i==last_closed)
        {
         newest=time[i];
         newest_dir=dir;
         newest_entry=entry;
         newest_sl=sl;
         newest_tp=tp;
        }
     }

   //--- pass 2: draw boxes newest-first, bounded by InpHistoryBars and by
   //--- InpMaxSignals. Drawing every historical signal on a full recalculation
   //--- would create tens of thousands of chart objects before TrimBoxes()
   //--- could remove them, which is enough to stall the terminal.
   //--- The counter tracks signals SEEN, not boxes newly created: counting
   //--- creations would keep scanning the whole window on every tick and
   //--- resurrect the boxes TrimBoxes() had just removed, churning objects
   //--- forever once the window holds more signals than InpMaxSignals.
   int    seen=0;
   int    keep=MathMax(1,InpMaxSignals);
   int    oldest_box=last_closed-MathMax(1,InpHistoryBars)+1;
   if(oldest_box<sig_start)
      oldest_box=sig_start;

   //--- tallies cover exactly the boxes on the chart, so they are rebuilt
   //--- from scratch every pass rather than accumulated
   g_tp_hits=0;
   g_sl_hits=0;
   g_open_sigs=0;

   for(int i=last_closed;i>=oldest_box && seen<keep;i--)
     {
      int    dir=0;
      double entry=0.0,sl=0.0,tp=0.0,atr=0.0;
      if(!SignalBoxAt(i,open,high,low,close,dir,entry,sl,tp,atr))
         continue;
      seen++;
      DrawSignalBox(dir,time[i],entry,sl,tp);   // idempotent by object name

      if(InpMarkOutcome)
         MarkOutcome(SignalBoxName(time[i],dir),dir,i,last_closed,sl,tp,time,high,low);
      else
         g_open_sigs++;
     }

   if(newest!=0)
      FireAlert(newest_dir,newest,newest_entry,newest_sl,newest_tp);

   TrimBoxes();

   if(InpShowPanel)
      UpdatePanel(rates_total);

   return(rates_total);
  }

//+------------------------------------------------------------------+
//| True Range / simple ATR of bar i, computed from the chart arrays |
//+------------------------------------------------------------------+
double AtrAt(const int i,const int period,
             const double &high[],const double &low[],const double &close[])
  {
   if(period<1)
      return(0.0);
   int from=i-period+1;
   if(from<1)
      from=1;
   if(i-from+1<1)
      return(0.0);

   double s=0.0;
   int    cnt=0;
   for(int j=from;j<=i;j++)
     {
      double tr=high[j]-low[j];
      double a=MathAbs(high[j]-close[j-1]);
      double b=MathAbs(low[j]-close[j-1]);
      if(a>tr) tr=a;
      if(b>tr) tr=b;
      s+=tr;
      cnt++;
     }
   if(cnt<=0)
      return(0.0);
   return(s/cnt);
  }

//+------------------------------------------------------------------+
//| Status panel                                                     |
//+------------------------------------------------------------------+
void UpdatePanel(const int rates_total)
  {
   int i=rates_total-2;
   if(i<1)
      return;

   double vwap=BufVwap[i];
   double ema=BufEma[i];
   if(vwap==EMPTY_VALUE || ema==EMPTY_VALUE)
      return;

   string bias=(ema>vwap?"EMA above VWAP - long bias":"EMA below VWAP - short bias");

   string txt="VWAP ("+VwapAnchorText(InpAnchor,InpSessionHour,InpSessionMinute,InpRollingBars)+")  "+
              DoubleToString(vwap,_Digits)+"\n"+
              "EMA "+IntegerToString(InpEmaPeriod)+"  "+DoubleToString(ema,_Digits)+"\n"+
              bias+"\n"+
              "Mode: "+ModeText()+"     Target "+RewardText()+"\n";

   if(InpShowStats && InpMarkOutcome)
     {
      int resolved=g_tp_hits+g_sl_hits;
      if(resolved>0)
        {
         //--- expectancy in R: a win pays InpRewardR, a loss costs 1R
         double exp_r=((double)g_tp_hits*InpRewardR-(double)g_sl_hits)/(double)resolved;
         txt+="Last "+IntegerToString(g_box_count)+" signals:  "+
              IntegerToString(g_tp_hits)+" TP / "+
              IntegerToString(g_sl_hits)+" SL / "+
              IntegerToString(g_open_sigs)+" open\n"+
              "Hit rate "+DoubleToString(100.0*(double)g_tp_hits/(double)resolved,1)+"%"+
              "     Expectancy "+(exp_r>=0.0?"+":"")+DoubleToString(exp_r,2)+"R\n";
        }
      else
         txt+="No resolved signals yet ("+IntegerToString(g_open_sigs)+" open)\n";
     }

   txt+="Signals only - no orders are placed";

   Comment(txt);
  }
//+------------------------------------------------------------------+
