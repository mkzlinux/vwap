//+------------------------------------------------------------------+
//|                                                 WeltradeVWAP.mq5 |
//|                                                                  |
//|  Session VWAP on typical price (O+H+L+C)/4.                      |
//|  Line only - no upper or lower deviation bands.                  |
//+------------------------------------------------------------------+
#property copyright   "Weltrade VWAP + 9 EMA signal suite"
#property version     "1.00"
#property description "Session anchored VWAP on (O+H+L+C)/4. No bands."
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   1
#property indicator_label1  "VWAP"
#property indicator_type1   DRAW_COLOR_LINE
#property indicator_color1  clrDodgerBlue,clrOrangeRed
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

#include <WeltradeVWAP/VwapCore.mqh>

input group "VWAP session"
input ENUM_VWAP_ANCHOR InpAnchor        = VWAP_ANCHOR_DAILY_CUSTOM; // VWAP anchor
input int              InpSessionHour   = 0;      // Session start hour (server time)
input int              InpSessionMinute = 0;      // Session start minute
input int              InpRollingBars   = 240;    // Rolling lookback bars (rolling anchor)
input bool             InpUseRealVolume = false;  // Use real volume if the feed provides it

input group "Appearance"
input bool             InpColorBySlope  = true;          // Colour by VWAP slope
input color            InpColorUp       = clrDodgerBlue; // Rising colour
input color            InpColorDown     = clrOrangeRed;  // Falling colour

double BufVwap[];
double BufColor[];

datetime g_cache_bar   = 0;
int      g_cache_start = -1;
int      g_cache_total = -1;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0,BufVwap,INDICATOR_DATA);
   SetIndexBuffer(1,BufColor,INDICATOR_COLOR_INDEX);

   PlotIndexSetInteger(0,PLOT_COLOR_INDEXES,2);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,0,(long)InpColorUp);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,1,(long)InpColorDown);
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME,"VWAP "+VwapAnchorText(InpAnchor,InpSessionHour,InpSessionMinute,InpRollingBars));
   IndicatorSetInteger(INDICATOR_DIGITS,_Digits);

   return(INIT_SUCCEEDED);
  }

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
   if(rates_total<2)
      return(0);

   bool full=(prev_calculated<=0);
   if(full)
     {
      g_cache_total=-1;
      g_cache_start=-1;
     }

   int start=0;
   if(!full)
     {
      datetime last_bar=time[rates_total-1];
      if(InpAnchor==VWAP_ANCHOR_ROLLING)
        {
         start=rates_total-1-(MathMax(2,InpRollingBars)-1);
        }
      else if(last_bar==g_cache_bar && rates_total==g_cache_total && g_cache_start>=0)
        {
         start=g_cache_start;
        }
      else
        {
         datetime key=VwapSessionStart(last_bar,InpAnchor,InpSessionHour,InpSessionMinute);
         start=rates_total-1;
         while(start>0 &&
               VwapSessionStart(time[start-1],InpAnchor,InpSessionHour,InpSessionMinute)==key)
            start--;
         g_cache_bar=last_bar;
         g_cache_total=rates_total;
         g_cache_start=start;
        }
      if(start<0)
         start=0;
      if(start>prev_calculated-1)
         start=prev_calculated-1;
      if(start<0)
         start=0;
     }

   int build_from=start;
   if(InpAnchor==VWAP_ANCHOR_ROLLING)
     {
      build_from=start-(MathMax(2,InpRollingBars)-1);
      if(build_from<0)
         build_from=0;
     }

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
      for(int i=build_from;i<rates_total;i++)
         tot+=volume[i];
      use_real=(tot>0);
     }

   for(int i=build_from;i<rates_total;i++)
     {
      tp[i]=VwapTypicalPrice(open[i],high[i],low[i],close[i]);
      vol[i]=(use_real?volume[i]:tick_volume[i]);
     }

   if(!VwapFill(tp,vol,time,start,rates_total-1,
                InpAnchor,InpSessionHour,InpSessionMinute,InpRollingBars,BufVwap))
      return(0);

   for(int i=start;i<rates_total;i++)
     {
      if(InpColorBySlope && i>0 && BufVwap[i-1]!=EMPTY_VALUE)
         BufColor[i]=(BufVwap[i]<BufVwap[i-1]?1:0);
      else
         BufColor[i]=0;
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
