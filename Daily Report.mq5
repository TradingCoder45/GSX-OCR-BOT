//+------------------------------------------------------------------+
//|                                             Daily Report.mq5     |
//|             OCR Bot Daily Report grouped by comment             |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

//===================================================================
// INPUTS
//===================================================================

input bool TodayOnly = true;

// Allowed magic numbers
input long MAGIC_ME    = 100100;
input long MAGIC_LIMIT = 100200;

// Breakeven tolerance in account currency
// Any net result between -BETolerance and +BETolerance = BE
input double BETolerance = 1;


//===================================================================
// STRUCTURE HOLDING STATISTICS FOR ONE BOT / COMMENT
//===================================================================

struct SBotStats
{
   string comment;

   int trades;
   int wins;
   int breakeven;
   int losses;

   double grossProfit;
   double grossLoss;
   double netProfit;


   //===============================================================
   // Reset
   //===============================================================

   void Reset()
   {
      comment="";

      trades=0;
      wins=0;
      breakeven=0;
      losses=0;

      grossProfit=0;
      grossLoss=0;
      netProfit=0;
   }


   //===============================================================
   // Win Rate
   //
   // BE trades are NOT included in the denominator.
   //===============================================================

   double WinRate() const
   {
      int decisiveTrades=wins+losses;

      if(decisiveTrades==0)
         return 0.0;

      return 100.0*wins/decisiveTrades;
   }


   //===============================================================
   // Average Win
   //===============================================================

   double AvgWin() const
   {
      if(wins==0)
         return 0.0;

      return grossProfit/wins;
   }


   //===============================================================
   // Average Loss
   //===============================================================

   double AvgLoss() const
   {
      if(losses==0)
         return 0.0;

      return grossLoss/losses;
   }


   //===============================================================
   // Profit Factor
   //===============================================================

   double ProfitFactor() const
   {
      if(grossLoss==0)
         return 0.0;

      return grossProfit/MathAbs(grossLoss);
   }
};


//===================================================================
// GLOBAL ARRAY
//===================================================================

SBotStats Stats[];


//===================================================================
// FIND OPENING COMMENT AND MAGIC NUMBER FOR A POSITION
//===================================================================

bool GetOpenInfo(const ulong positionID,
                 string &openComment,
                 long &openMagic)
{
   int total=HistoryDealsTotal();

   for(int i=0;i<total;i++)
   {
      ulong deal=HistoryDealGetTicket(i);

      if(deal==0)
         continue;


      if((ulong)HistoryDealGetInteger(
            deal,
            DEAL_POSITION_ID
         ) != positionID)
      {
         continue;
      }


      ENUM_DEAL_ENTRY entry=
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(
            deal,
            DEAL_ENTRY
         );


      if(entry==DEAL_ENTRY_IN)
      {
         openComment=
            HistoryDealGetString(
               deal,
               DEAL_COMMENT
            );

         openMagic=
            HistoryDealGetInteger(
               deal,
               DEAL_MAGIC
            );

         return true;
      }
   }

   return false;
}


//===================================================================
// FIND STATISTICS INDEX BY COMMENT
//===================================================================

int FindComment(const string comment)
{
   for(int i=0;i<ArraySize(Stats);i++)
   {
      if(Stats[i].comment==comment)
         return i;
   }

   return -1;
}


//===================================================================
// CREATE NEW STATISTICS RECORD
//===================================================================

int AddComment(const string comment)
{
   int size=ArraySize(Stats);

   ArrayResize(Stats,size+1);

   Stats[size].Reset();
   Stats[size].comment=comment;

   return size;
}


//===================================================================
// GET EXISTING STATISTICS OR CREATE ONE
//===================================================================

int GetCommentIndex(const string comment)
{
   int idx=FindComment(comment);

   if(idx>=0)
      return idx;

   return AddComment(comment);
}


//===================================================================
// ADD ONE CLOSED TRADE TO STATISTICS
//===================================================================

void AddTrade(const string comment,
              const double netProfit)
{
   int idx=GetCommentIndex(comment);

   Stats[idx].trades++;

   Stats[idx].netProfit+=netProfit;


   //===============================================================
   // WIN
   //===============================================================

   if(netProfit > BETolerance)
   {
      Stats[idx].wins++;

      Stats[idx].grossProfit+=netProfit;
   }


   //===============================================================
   // LOSS
   //===============================================================

   else if(netProfit < -BETolerance)
   {
      Stats[idx].losses++;

      Stats[idx].grossLoss+=netProfit;
   }


   //===============================================================
   // BREAKEVEN
   //===============================================================

   else
   {
      Stats[idx].breakeven++;
   }
}


//===================================================================
// CHECK WHETHER MAGIC NUMBER IS ALLOWED
//===================================================================

bool IsAllowedMagic(const long magic)
{
   if(magic==MAGIC_ME)
      return true;

   if(magic==MAGIC_LIMIT)
      return true;

   return false;
}


//===================================================================
// SCRIPT ENTRY
//===================================================================

void OnStart()
{
   datetime from;
   datetime to;


   //===============================================================
   // SELECT HISTORY
   //===============================================================

   if(TodayOnly)
   {
      from=
         StringToTime(
            TimeToString(
               TimeCurrent(),
               TIME_DATE
            )
         );

      to=TimeCurrent();
   }
   else
   {
      from=0;
      to=TimeCurrent();
   }


   if(!HistorySelect(from,to))
   {
      Print("HistorySelect failed.");
      return;
   }


   int totalDeals=HistoryDealsTotal();

   Print("Deals selected: ",totalDeals);


   //===============================================================
   // SCAN CLOSED TRADES
   //===============================================================

   for(int i=0;i<totalDeals;i++)
   {
      ulong deal=HistoryDealGetTicket(i);

      if(deal==0)
         continue;


      ENUM_DEAL_ENTRY entry=
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(
            deal,
            DEAL_ENTRY
         );


      // Only closing deals
      if(entry!=DEAL_ENTRY_OUT)
         continue;


      ulong positionID=
         (ulong)HistoryDealGetInteger(
            deal,
            DEAL_POSITION_ID
         );


      string openComment="";
      long openMagic=0;


      //============================================================
      // FIND ORIGINAL OPENING DEAL
      //============================================================

      if(!GetOpenInfo(
            positionID,
            openComment,
            openMagic
         ))
      {
         continue;
      }


      //============================================================
      // MAGIC FILTER
      //
      // Only positions opened with MAGIC_ME or MAGIC_LIMIT
      // are included.
      //============================================================

      if(!IsAllowedMagic(openMagic))
         continue;


      //============================================================
      // REQUIRE OPENING COMMENT
      //============================================================

      if(openComment=="")
         continue;


      //============================================================
      // GET CLOSING DEAL RESULT
      //============================================================

      double profit=
         HistoryDealGetDouble(
            deal,
            DEAL_PROFIT
         );


      double commission=
         HistoryDealGetDouble(
            deal,
            DEAL_COMMISSION
         );


      double swap=
         HistoryDealGetDouble(
            deal,
            DEAL_SWAP
         );


      double net=
         profit+
         commission+
         swap;


      //============================================================
      // ADD TO GROUP
      //============================================================

      AddTrade(
         openComment,
         net
      );
   }


   Print(
      "Groups found: ",
      ArraySize(Stats)
   );


   //===============================================================
   // SORT BY COMMENT
   //===============================================================

   int groups=ArraySize(Stats);


   for(int i=0;i<groups-1;i++)
   {
      for(int j=i+1;j<groups;j++)
      {
         if(
            StringCompare(
               Stats[i].comment,
               Stats[j].comment
            ) > 0
         )
         {
            SBotStats tmp=Stats[i];

            Stats[i]=Stats[j];

            Stats[j]=tmp;
         }
      }
   }


   //===============================================================
   // CREATE FILE NAME
   //
   // Example:
   // OCR_Report-05-08-2026.csv
   //===============================================================

   MqlDateTime dt;

   TimeToStruct(
      TimeCurrent(),
      dt
   );


   string fileName=
      StringFormat(
         "OCR_Report-%02d-%02d-%04d.csv",
         dt.day,
         dt.mon,
         dt.year
      );


   //===============================================================
   // OPEN CSV
   //===============================================================

   int file=
      FileOpen(
         fileName,
         FILE_WRITE|
         FILE_CSV|
         FILE_ANSI
      );


   if(file==INVALID_HANDLE)
   {
      Print(
         "Cannot create ",
         fileName
      );

      return;
   }


   //===============================================================
   // CSV HEADER
   //===============================================================

   FileWrite(
      file,
      "Comment",
      "Trades",
      "Wins",
      "BE",
      "Losses",
      "Win %",
      "Gross Profit",
      "Gross Loss",
      "Net Profit",
      "Average Win",
      "Average Loss",
      "Profit Factor"
   );


   //===============================================================
   // TOTALS
   //===============================================================

   double totalGrossProfit=0;
   double totalGrossLoss=0;
   double totalNetProfit=0;

   int totalTrades=0;
   int totalWins=0;
   int totalBE=0;
   int totalLosses=0;


   //===============================================================
   // WRITE ONE ROW PER COMMENT
   //===============================================================

   for(int i=0;i<groups;i++)
   {
      FileWrite(
         file,

         Stats[i].comment,

         Stats[i].trades,

         Stats[i].wins,

         Stats[i].breakeven,

         Stats[i].losses,

         DoubleToString(
            Stats[i].WinRate(),
            2
         ),

         DoubleToString(
            Stats[i].grossProfit,
            2
         ),

         DoubleToString(
            Stats[i].grossLoss,
            2
         ),

         DoubleToString(
            Stats[i].netProfit,
            2
         ),

         DoubleToString(
            Stats[i].AvgWin(),
            2
         ),

         DoubleToString(
            Stats[i].AvgLoss(),
            2
         ),

         DoubleToString(
            Stats[i].ProfitFactor(),
            2
         )
      );


      totalTrades+=Stats[i].trades;
      totalWins+=Stats[i].wins;
      totalBE+=Stats[i].breakeven;
      totalLosses+=Stats[i].losses;

      totalGrossProfit+=Stats[i].grossProfit;
      totalGrossLoss+=Stats[i].grossLoss;
      totalNetProfit+=Stats[i].netProfit;
   }


   //===============================================================
   // TOTAL STATISTICS
   //===============================================================

   int totalDecisive=
      totalWins+
      totalLosses;


   double totalWinRate=0.0;

   if(totalDecisive>0)
   {
      totalWinRate=
         100.0*
         totalWins/
         totalDecisive;
   }


   double totalAvgWin=0.0;

   if(totalWins>0)
   {
      totalAvgWin=
         totalGrossProfit/
         totalWins;
   }


   double totalAvgLoss=0.0;

   if(totalLosses>0)
   {
      totalAvgLoss=
         totalGrossLoss/
         totalLosses;
   }


   double totalPF=0.0;

   if(totalGrossLoss!=0.0)
   {
      totalPF=
         totalGrossProfit/
         MathAbs(totalGrossLoss);
   }


   //===============================================================
   // TOTAL CSV ROW
   //===============================================================

   FileWrite(
      file,

      "TOTAL",

      totalTrades,

      totalWins,

      totalBE,

      totalLosses,

      DoubleToString(
         totalWinRate,
         2
      ),

      DoubleToString(
         totalGrossProfit,
         2
      ),

      DoubleToString(
         totalGrossLoss,
         2
      ),

      DoubleToString(
         totalNetProfit,
         2
      ),

      DoubleToString(
         totalAvgWin,
         2
      ),

      DoubleToString(
         totalAvgLoss,
         2
      ),

      DoubleToString(
         totalPF,
         2
      )
   );


   //===============================================================
   // CLOSE CSV
   //===============================================================

   FileClose(file);


   //===============================================================
   // PRINT REPORT TO EXPERTS
   //===============================================================

   Print("");

   Print(
      "================================================================"
   );

   Print(
      "                     OCR BOT DAILY REPORT"
   );

   Print(
      "================================================================"
   );


   PrintFormat(
      "%-15s %6s %6s %6s %7s %8s %12s %12s %12s",

      "Comment",
      "Trades",
      "Wins",
      "BE",
      "Losses",
      "Win%",
      "Gross+",
      "Gross-",
      "Net"
   );


   //===============================================================
   // PRINT GROUPS
   //===============================================================

   for(int i=0;i<groups;i++)
   {
      PrintFormat(
         "%-15s %6d %6d %6d %7d %7.2f%% %12.2f %12.2f %12.2f",

         Stats[i].comment,

         Stats[i].trades,

         Stats[i].wins,

         Stats[i].breakeven,

         Stats[i].losses,

         Stats[i].WinRate(),

         Stats[i].grossProfit,

         Stats[i].grossLoss,

         Stats[i].netProfit
      );
   }


   //===============================================================
   // TOTAL LINE
   //===============================================================

   Print(
      "----------------------------------------------------------------"
   );


   PrintFormat(
      "%-15s %6d %6d %6d %7d %7.2f%% %12.2f %12.2f %12.2f",

      "TOTAL",

      totalTrades,

      totalWins,

      totalBE,

      totalLosses,

      totalWinRate,

      totalGrossProfit,

      totalGrossLoss,

      totalNetProfit
   );


   Print(
      "================================================================"
   );


   //===============================================================
   // REPORT INFORMATION
   //===============================================================

   Print("BE tolerance: ", DoubleToString(BETolerance, 2));

   Print("Allowed Magic #1: ", MAGIC_ME);

   Print("Allowed Magic #2: ", MAGIC_LIMIT);

   Print("CSV exported to:");

   Print(TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fileName);
}
