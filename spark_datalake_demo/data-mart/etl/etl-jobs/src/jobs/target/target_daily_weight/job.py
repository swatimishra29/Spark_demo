from typing import Dict, List, Any
import pyspark.sql
import pyspark.sql.functions as F
from common.etl_job import ETLJob # must be imported after spark has been set up


class Job(ETLJob):
    target_table = "target_daily_weight"
    business_key = ["trgt_fund_key","day_key","fund_key"]
    primary_key = {"trgt_daily_wgt_key": "int"}
    sources:Dict[str,Dict[str,Any]] = {
        "raw": {
            "type": "file",
            "source": "ssb_hlds"
        },
        "cal": {
            "type": "table",
            "source": "calendar"
        },
        "fund": {
            "type": "table",
            "source": "fund"
        },
        "target_fund": {
            "type": "table",
            "source": "fund"
        },
        "fund_valuation": {
            "type": "table",
            "source": "fund_valuation"
        }

    }
    joins: List[Dict[str, Any]] = [
        {
            "source": "raw"
        },
        {
            "source": "cal",
            "conditions": [
                F.to_date(F.col("raw.calen_dt"), 'yyyyMMdd') == F.col("cal.cal_day")
            ]
        },
        {
            "source": "target_fund",
            "conditions": [
                F.col("raw.fund_id") == F.col("target_fund.st_str_fund_nbr"),
                F.col("target_fund.shr_cls_cd") == 1

            ]
        },
        {
            "source": "fund",
            "conditions": [
                F.col("raw.ticker_symbol") == F.col("fund.quot_sym"),
                F.col("fund.shr_cls_cd") == 1
            ]
        },
        {
            "source": "fund_valuation",
            "conditions": [
                F.col("fund.fund_key") == F.col("fund_valuation.fund_key"),
                F.col("cal.day_key") == F.col("fund_valuation.day_key")

            ]
        }
    ]
    target_mappings:List[Dict[str,Any]] = [
        {"source": F.col("target_fund.fund_key"), "target": "trgt_fund_key"},
        {"source": F.col("cal.day_key"), "target": "day_key"},
        {"source": F.col("fund.fund_key"), "target": "fund_key"},
        {"source": F.col("raw.shrpar_qty"), "target": "shr_qty"},
        {"source": F.col("raw.mktval_btl"), "target": "mkt_val"},
        {"source": F.lit("daily_holdg_wgt"), "target": "daily_holdg_wgt"},
        {"source": F.lit("Y"), "target": "curr_row_flg"}
    ]

    def join(self, inputs: Dict[str, pyspark.sql.DataFrameReader]) -> pyspark.sql.DataFrame:
        df_joined = super().join(inputs)

        df_joined = df_joined\
            .groupBy("calen_dt", "fund_id")\
            .agg(F.expr("(shrpar_qty * fund_valuation.pr_per_shr) "
                        "/ sum(shrpar_qty * fund_valuation.pr_per_shr)").alias("daily_holdg_wgt"))

        return df_joined

