//+------------------------------------------------------------------+
//|                                                     VwapCore.mqh |
//|        Shared session-VWAP maths for the Weltrade VWAP suite     |
//|                                                                  |
//|  VWAP typical price = (Open + High + Low + Close) / 4            |
//|  No standard-deviation bands - VWAP line only.                   |
//+------------------------------------------------------------------+
#ifndef __VWAP_CORE_MQH__
#define __VWAP_CORE_MQH__

//+------------------------------------------------------------------+
//| How the VWAP session is anchored (when the running totals reset) |
//+------------------------------------------------------------------+
enum ENUM_VWAP_ANCHOR
  {
   VWAP_ANCHOR_DAILY_CUSTOM  = 0,  // Daily @ custom hour
   VWAP_ANCHOR_DAILY_MIDNIGHT= 1,  // Daily @ 00:00 server time
   VWAP_ANCHOR_WEEKLY        = 2,  // Weekly (Monday)
   VWAP_ANCHOR_ROLLING       = 3   // Rolling N bars
  };

//+------------------------------------------------------------------+
//| Typical price used by this VWAP: (O+H+L+C)/4                     |
//+------------------------------------------------------------------+
double VwapTypicalPrice(const double o,const double h,const double l,const double c)
  {
   return((o+h+l+c)/4.0);
  }

//+------------------------------------------------------------------+
//| Midnight (00:00:00) of a server datetime                         |
//+------------------------------------------------------------------+
datetime VwapMidnight(const datetime t)
  {
   return(t-(t%86400));
  }

//+------------------------------------------------------------------+
//| Start of the VWAP session that contains bar time t.              |
//| For the rolling anchor there is no session, so midnight of the   |
//| bar's own day is returned and the caller ignores it.             |
//+------------------------------------------------------------------+
datetime VwapSessionStart(const datetime t,
                          const ENUM_VWAP_ANCHOR anchor,
                          const int start_hour,
                          const int start_minute)
  {
   int hh=start_hour;
   int mm=start_minute;
   if(hh<0)   hh=0;
   if(hh>23)  hh=23;
   if(mm<0)   mm=0;
   if(mm>59)  mm=0;

   int    secs=hh*3600+mm*60;

   switch(anchor)
     {
      case VWAP_ANCHOR_DAILY_MIDNIGHT:
         return(VwapMidnight(t));

      case VWAP_ANCHOR_DAILY_CUSTOM:
        {
         datetime day_start=VwapMidnight(t)+secs;
         if(t<day_start)
            day_start-=86400;
         return(day_start);
        }

      case VWAP_ANCHOR_WEEKLY:
        {
         MqlDateTime dt;
         TimeToStruct(t,dt);
         int back=(dt.day_of_week+6)%7;                 // days since Monday
         datetime wk=VwapMidnight(t)-back*86400+secs;
         if(t<wk)
            wk-=7*86400;
         return(wk);
        }
     }
   return(VwapMidnight(t));
  }

//+------------------------------------------------------------------+
//| Human readable description of the anchor (for on-chart panels)   |
//+------------------------------------------------------------------+
string VwapAnchorText(const ENUM_VWAP_ANCHOR anchor,
                      const int start_hour,
                      const int start_minute,
                      const int rolling_bars)
  {
   string hhmm=StringFormat("%02d:%02d",MathMax(0,MathMin(23,start_hour)),MathMax(0,MathMin(59,start_minute)));
   switch(anchor)
     {
      case VWAP_ANCHOR_DAILY_MIDNIGHT: return("Daily @ 00:00");
      case VWAP_ANCHOR_DAILY_CUSTOM:   return("Daily @ "+hhmm);
      case VWAP_ANCHOR_WEEKLY:         return("Weekly (Mon "+hhmm+")");
      case VWAP_ANCHOR_ROLLING:        return("Rolling "+IntegerToString(MathMax(2,rolling_bars))+" bars");
     }
   return("Daily @ 00:00");
  }

//+------------------------------------------------------------------+
//| Fill dst[from..to] with session VWAP values.                     |
//|                                                                  |
//| All arrays are indexed by ABSOLUTE bar index in NON-series order |
//| (index 0 = oldest bar), exactly like OnCalculate parameters.     |
//|                                                                  |
//| For the rolling anchor the routine reads back to from-(N-1), so  |
//| tp[]/vol[]/time[] must be populated from at least that far back. |
//|                                                                  |
//| Zero-volume bars simply do not contribute. If a window contains  |
//| no volume at all the typical price is used so the line never     |
//| breaks (some synthetic feeds publish zero volume on idle ticks). |
//+------------------------------------------------------------------+
bool VwapFill(const double   &tp[],
              const long     &vol[],
              const datetime &time[],
              const int       from,
              const int       to,
              const ENUM_VWAP_ANCHOR anchor,
              const int       start_hour,
              const int       start_minute,
              const int       rolling_bars,
              double          &dst[])
  {
   if(to<from)
      return(false);

   int rb=(rolling_bars>1?rolling_bars:2);

   int calc_from=from;
   if(anchor==VWAP_ANCHOR_ROLLING)
     {
      calc_from=from-(rb-1);
      if(calc_from<0)
         calc_from=0;
     }
   if(calc_from<0)
      calc_from=0;
   if(calc_from>from)
      calc_from=from;

   int n=to-calc_from+1;
   if(n<=0)
      return(false);

   double cp[];
   double cv[];
   int    win[];
   if(ArrayResize(cp,n+1)!=n+1)  return(false);
   if(ArrayResize(cv,n+1)!=n+1)  return(false);
   if(ArrayResize(win,n)!=n)     return(false);

   cp[0]=0.0;
   cv[0]=0.0;

   int sess=0;
   for(int j=0;j<n;j++)
     {
      int k=calc_from+j;

      if(anchor==VWAP_ANCHOR_ROLLING)
        {
         int b=j-(rb-1);
         win[j]=(b<0?0:b);
        }
      else
        {
         if(j>0)
           {
            if(VwapSessionStart(time[k],anchor,start_hour,start_minute)!=
               VwapSessionStart(time[k-1],anchor,start_hour,start_minute))
               sess=j;
           }
         win[j]=sess;
        }

      double v=(double)vol[k];
      if(v<0.0)
         v=0.0;
      cp[j+1]=cp[j]+tp[k]*v;
      cv[j+1]=cv[j]+v;
     }

   for(int i=from;i<=to;i++)
     {
      int    j=i-calc_from;
      int    b=win[j];
      double dv=cv[j+1]-cv[b];
      if(dv<=0.0)
         dst[i]=tp[i];
      else
         dst[i]=(cp[j+1]-cp[b])/dv;
     }

   return(true);
  }

#endif // __VWAP_CORE_MQH__
//+------------------------------------------------------------------+
