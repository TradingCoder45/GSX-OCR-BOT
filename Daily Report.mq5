//+------------------------------------------------------------------+
//|                                                  OCR_Report.mq5  |
//|         Daily report grouped by opening comment                  |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

input bool TodayOnly = true;
input long MAGIC_ME = 100100;
input long MAGIC_LIMIT = 100200;
//===============================================================
// Structure holding statistics for one bot/comment
//===============================================================
struct SBotStats
{
   string comment;

   int trades;
   int wins;
   int losses;

   double grossProfit;
   double grossLoss;
   double netProfit;

   void Reset()
   {
      comment="";

      trades=0;
      wins=0;
      losses=0;

      grossProfit=0;
      grossLoss=0;
      netProfit=0;
   }

   double WinRate() const
   {
      if(trades==0)
         return 0.0;

      return 100.0*wins/trades;
   }

   double AvgWin() const
   {
      if(wins==0)
         return 0.0;

      return grossProfit/wins;
   }

   double AvgLoss() const
   {
      if(losses==0)
         return 0.0;

      return grossLoss/losses;
   }

   double ProfitFactor() const
   {
      if(grossLoss==0)
         return 0.0;

      return grossProfit/MathAbs(grossLoss);
   }
};

//===============================================================
// Global array of statistics
//===============================================================
SBotStats Stats[];

//===============================================================
// Find opening comment and magic number for a position
//===============================================================
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

      if((ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID)
         != positionID)
         continue;

      ENUM_DEAL_ENTRY entry=
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(
            deal,
            DEAL_ENTRY
         );

      if(entry==DEAL_ENTRY_IN)
      {
         openComment=
            HistoryDealGetString(deal,DEAL_COMMENT);

         openMagic=
            HistoryDealGetInteger(deal,DEAL_MAGIC);

         return true;
      }
   }

   return false;
}

//===============================================================
// Find statistics index by comment
//===============================================================
int FindComment(const string comment)
{
   for(int i=0;i<ArraySize(Stats);i++)
   {
      if(Stats[i].comment==comment)
         return i;
   }

   return -1;
}

//===============================================================
// Create new statistics record
//===============================================================
int AddComment(const string comment)
{
   int size=ArraySize(Stats);

   ArrayResize(Stats,size+1);

   Stats[size].Reset();
   Stats[size].comment=comment;

   return size;
}

//===============================================================
// Get existing statistics or create one
//===============================================================
int GetCommentIndex(const string comment)
{
   int idx=FindComment(comment);

   if(idx>=0)
      return idx;

   return AddComment(comment);
}

//===============================================================
// Add one closed trade to statistics
//===============================================================
void AddTrade(const string comment,
              const double netProfit)
{
   int idx=GetCommentIndex(comment);

   Stats[idx].trades++;
   Stats[idx].netProfit+=netProfit;

   if(netProfit>=0)
   {
      Stats[idx].wins++;
      Stats[idx].grossProfit+=netProfit;
   }
   else
   {
      Stats[idx].losses++;
      Stats[idx].grossLoss+=netProfit;
   }
}

//===============================================================
// Check whether a magic number is allowed
//===============================================================
bool IsAllowedMagic(const long magic)
{
   if(magic == MAGIC_ME)
      return true;

   if(magic == MAGIC_LIMIT)
      return true;

   return false;
}

//===============================================================
// Script entry
//===============================================================
void OnStart()
{
   datetime from,to;

   if(TodayOnly)
   {
      from=StringToTime(TimeToString(TimeCurrent(),TIME_DATE));
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

   //===========================================================
   // Scan today's closed trades
   //===========================================================
   for(int i=0;i<totalDeals;i++)
   {
      ulong deal=HistoryDealGetTicket(i);

      if(deal==0)
         continue;

      ENUM_DEAL_ENTRY entry=
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);

      if(entry!=DEAL_ENTRY_OUT)
         continue;

      ulong positionID=
         (ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);

      string openComment="";
      long openMagic=0;
      
      //-----------------------------------------------------------
      // Find the original opening deal
      //-----------------------------------------------------------
      if(!GetOpenInfo(positionID,openComment,openMagic))
         continue;
      
      //-----------------------------------------------------------
      // MAGIC FILTER
      //-----------------------------------------------------------
      // Ignore the position completely if its opening magic
      // number is not one of our allowed OCR magic numbers.
      //-----------------------------------------------------------
      if(!IsAllowedMagic(openMagic))
         continue;
      
      //-----------------------------------------------------------
      // Ignore positions without a proper OCR comment
      //-----------------------------------------------------------
      if(openComment=="")
         continue;
      
      //-----------------------------------------------------------
      // Calculate net result of closing deal
      //-----------------------------------------------------------
      double profit=
         HistoryDealGetDouble(deal,DEAL_PROFIT);
      
      double commission=
         HistoryDealGetDouble(deal,DEAL_COMMISSION);
      
      double swap=
         HistoryDealGetDouble(deal,DEAL_SWAP);
      
      double net=profit+commission+swap;
      
      AddTrade(openComment,net);
   }

   Print("Groups found: ",ArraySize(Stats));

   // ===== Part 2 starts here =====
      //===========================================================
   // Sort by comment (OCR TP1, OCR TP2, ...)
   //===========================================================
   int groups = ArraySize(Stats);

   for(int i=0; i<groups-1; i++)
   {
      for(int j=i+1; j<groups; j++)
      {
         if(StringCompare(Stats[i].comment, Stats[j].comment) > 0)
         {
            SBotStats tmp = Stats[i];
            Stats[i] = Stats[j];
            Stats[j] = tmp;
         }
      }
   }

   //===========================================================
   // Create CSV
   //===========================================================
   
   // Create file name: OCR_Report-DD-MM-YYYY.csv
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   
   string fileName = StringFormat(
      "OCR_Report-%02d-%02d-%04d.csv",
      dt.day,
      dt.mon,
      dt.year
   );

   int file = FileOpen(fileName,
                       FILE_WRITE|FILE_CSV|FILE_ANSI);

   if(file == INVALID_HANDLE)
   {
      Print("Cannot create ", fileName);
      return;
   }

   FileWrite(file,
             "Comment",
             "Trades",
             "Wins",
             "Losses",
             "Win %",
             "Gross Profit",
             "Gross Loss",
             "Net Profit",
             "Average Win",
             "Average Loss",
             "Profit Factor");

   double totalGrossProfit = 0;
   double totalGrossLoss   = 0;
   double totalNetProfit   = 0;

   int totalTrades = 0;
   int totalWins   = 0;
   int totalLosses = 0;

   //===========================================================
   // Write one row per bot
   //===========================================================
   for(int i=0;i<groups;i++)
   {
      FileWrite(file,
                Stats[i].comment,
                Stats[i].trades,
                Stats[i].wins,
                Stats[i].losses,
                DoubleToString(Stats[i].WinRate(),2),
                DoubleToString(Stats[i].grossProfit,2),
                DoubleToString(Stats[i].grossLoss,2),
                DoubleToString(Stats[i].netProfit,2),
                DoubleToString(Stats[i].AvgWin(),2),
                DoubleToString(Stats[i].AvgLoss(),2),
                DoubleToString(Stats[i].ProfitFactor(),2));

      totalTrades      += Stats[i].trades;
      totalWins        += Stats[i].wins;
      totalLosses      += Stats[i].losses;
      totalGrossProfit += Stats[i].grossProfit;
      totalGrossLoss   += Stats[i].grossLoss;
      totalNetProfit   += Stats[i].netProfit;
   }

   //===========================================================
   // Totals row
   //===========================================================
   double totalWinRate = 0.0;
   if(totalTrades > 0)
      totalWinRate = 100.0 * totalWins / totalTrades;

   double totalAvgWin = 0.0;
   if(totalWins > 0)
      totalAvgWin = totalGrossProfit / totalWins;

   double totalAvgLoss = 0.0;
   if(totalLosses > 0)
      totalAvgLoss = totalGrossLoss / totalLosses;

   double totalPF = 0.0;
   if(totalGrossLoss != 0.0)
      totalPF = totalGrossProfit / MathAbs(totalGrossLoss);

   FileWrite(file,
             "TOTAL",
             totalTrades,
             totalWins,
             totalLosses,
             DoubleToString(totalWinRate,2),
             DoubleToString(totalGrossProfit,2),
             DoubleToString(totalGrossLoss,2),
             DoubleToString(totalNetProfit,2),
             DoubleToString(totalAvgWin,2),
             DoubleToString(totalAvgLoss,2),
             DoubleToString(totalPF,2));

   FileClose(file);

   //===========================================================
   // Print summary to Experts tab
   //===========================================================
   Print("");
   Print("===============================================================");
   Print("                 OCR BOT DAILY REPORT");
   Print("===============================================================");

   PrintFormat("%-15s %6s %6s %6s %8s %12s %12s %12s",
               "Comment",
               "Trades",
               "Wins",
               "Loss",
               "Win%",
               "Gross+",
               "Gross-",
               "Net");

   for(int i=0;i<groups;i++)
   {
      PrintFormat("%-15s %6d %6d %6d %7.2f%% %12.2f %12.2f %12.2f",
                  Stats[i].comment,
                  Stats[i].trades,
                  Stats[i].wins,
                  Stats[i].losses,
                  Stats[i].WinRate(),
                  Stats[i].grossProfit,
                  Stats[i].grossLoss,
                  Stats[i].netProfit);
   }

   Print("---------------------------------------------------------------");

   PrintFormat("%-15s %6d %6d %6d %7.2f%% %12.2f %12.2f %12.2f",
               "TOTAL",
               totalTrades,
               totalWins,
               totalLosses,
               totalWinRate,
               totalGrossProfit,
               totalGrossLoss,
               totalNetProfit);

   Print("===============================================================");
   Print("CSV exported to:");
   Print(TerminalInfoString(TERMINAL_DATA_PATH) +
         "\\MQL5\\Files\\" + fileName);
}


