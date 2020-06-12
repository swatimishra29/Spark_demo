from typing import Dict, List, Any
import pyspark.sql
import common.utils
import pyspark.sql.functions as F
from common.etl_job import ETLJob # must be imported after spark has been set up

class Job(ETLJob):
    target_table = "sample"
    business_key = ["fund_nbr"]
    primary_key = {"fund_key":"int"}
    sources:Dict[str,Dict[str,Any]] = {
        "sample": {
            "type": "file",
            "source": "sample"
        },
        "fund_composite": {
            "type": "file",
            "source": "fund_composite"
        }
    }
    joins:List[Dict[str,Any]] = [
        {

            "source": "sample"
        },
        {
            "source": "fund_composite",
            "conditions": [
                F.col("fund_composite.st_str_fund_nbr") == F.col("sample.st_str_fund_nbr")
            ]
        }
    ]
    target_mappings:List[Dict[str,Any]] = [

        {"source": F.lit("All"), "target": "all_fund_cd" },
        {"source": F.lit("All Funds"), "target": "all_fund_desc" },
        {"source": F.col("fund_composite.fund_compst_key"), "target": "fund_compst_key" },
        {"source": F.col("sample.shr_cls_cd"), "target": "shr_cls_cd" },
        {"source": F.col("sample.shr_cls_desc"), "target": "shr_cls_desc" },
        {"source": F.col("sample.fund_nm"), "target": "fund_nm" },
        {"source": F.col("sample.fund_nbr"), "target": "fund_nbr"},
        {"source": F.lit("Y"), "target": "curr_row_flg" },
        {"source": F.lit(4), "target": "src_sys_id" },
        {"source": F.to_timestamp("sample.perf_incpn_dt","MM/dd/yyyy"), "target": "perf_incpn_dt" }

    ]
