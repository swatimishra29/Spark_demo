from typing import Dict, List, Any
import pyspark.sql
import pyspark.sql.functions as F
from common.etl_job import ETLJob  # must be imported after spark has been set up


class Job(ETLJob):
    target_table = "target_wealth_index"
    business_key = ["trgt_perf_type_key", "day_key", "fund_key"]
    primary_key = {"trgt_wlth_idx_key": "int"}
    sources: Dict[str, Dict[str, Any]] = {
        "wt": {
            "type": "table",
            "source": "target_weights"
        },
        "tf": {
            "type": "table",
            "source": "fund"
        },
        "f": {
            "type": "table",
            "source": "fund"
        },
        "rl": {
            "type": "table",
            "source": "fund_index_rltn"
        },
        "bi": {
            "type": "table",
            "source": "benchmark_index"
        },
        "fr": {
            "type": "table",
            "source": "fund_return"
        },
        "perf": {
            "type": "table",
            "source": "perf_run_type"
        },
        "cal": {
            "type": "table",
            "source": "calendar"
        },
        "rp": {
            "type": "table",
            "source": "return_periods"
            },
        "idr": {
            "type": "table",
            "source": "index_return"
        },
        "tpt": {
            "type": "table",
            "source": "target_performance_type"
        },
        "prev_twi": {
            "type": "table",
            "source": "target_wealth_index"
        },
        "tog": {
            "type": "table",
            "source": "target_orig_glidepath"
        }
    }
    joins: List[Dict[str, Any]] = [
        {
            "source": "f"
        },
        {
            "source": "rl",
            "conditions": [
                F.col("f.fund_compst_key") == F.col("rl.fund_compst_key"),
                F.col("rl.prim_bmk_flg") == 'Y',
                F.col("rl.link_prio") == 1]
        },
        {
            "source": "bi",
            "conditions": [
                F.col("rl.bmk_idx_key") == F.col("bi.bmk_idx_key")]
        },
        {
            "source": "perf",
            "conditions": [
                F.col("rl.perf_run_type_key") == F.col("perf.perf_run_type_key"),
                F.col("perf.run_type_cd") == 'REPORTING']
        },
        {
            "source": "idr",
            "conditions": [
                F.col("rl.bmk_idx_key") == F.col("idr.bmk_idx_key"),
                F.col("rl.fund_compst_key") == F.col("idr.fund_compst_key")

            ]
        },
        {
            "source": "cal",
            "conditions": [
                F.col("idr.day_key") == F.col("cal.day_key")]
        },
        {
            "source": "rp",
            "conditions": [
                F.col("idr.per_key") == F.col("rp.per_key"),
                F.col("rp.per_nm") == '1DY']
        }
    ]
    target_mappings: List[Dict[str, Any]] = [
        {"source": F.col("output.trgt_perf_type_key"), "target": "trgt_perf_type_key"},
        {"source": F.col("output.day_key"), "target": "day_key"},
        {"source": F.col("output.fund_key"), "target": "fund_key"},
        {"source": F.col("output.wlth_idx"), "target": "wlth_idx"},
        {"source": F.col("output.daily_ret"), "target": "daily_ret"},
        {"source": F.lit("Y"), "target": "curr_row_flg"},
        {"source": F.lit(4), "target": "src_sys_id"},
        {"source": F.lit(None), "target": "etl_load_cyc_key"}
    ]

    def join(self, inputs: Dict[str, pyspark.sql.DataFrameReader]) -> pyspark.sql.DataFrame:
        p_wi_date = self._args["p_wi_date"]
        f = inputs["tf"].alias("f")

        df_joined = super().join(inputs)

        df_joined_1=df_joined.join(inputs["wt"], [F.col("wt.fund_key") == F.col("f.fund_key")])\
        .join(inputs["tf"], [F.col("wt.trgt_fund_key") == F.col("tf.fund_key")])\
        .join(inputs["fr"],[F.col("f.fund_key") == F.col("fr.fund_key"),\
                F.col("cal.day_key") == F.col("fr.day_key"),F.col("rp.per_key") == F.col("fr.per_key")],how="left")

        df_index = df_joined_1.where(F.col("wt.wgt_type").isin('FIRM', 'MODEL')).where(
            (F.col("wt.efftv_strt_dt") <= F.lit(p_wi_date)) & (F.col("wt.efftv_end_dt") >= F.lit(p_wi_date))) \
            .where(F.col("cal.cal_day") == F.lit(p_wi_date)) \
            .where((F.col("tf.fund_stat_cd").isin(1, 5) | ((F.col("tf.fund_incpn_dt") <= F.lit(p_wi_date))
                                                           & (F.col("tf.fund_clos_dt") >= F.lit(p_wi_date))))) \
            .select("trgt_fund_key", "cal.day_key", "wgt_type",
                    F.expr("fund_ret * trgt_fund_wgt").alias("tgt_fund_dly_ret"),
                    F.expr("idx_ret * trgt_fund_wgt").alias("tgt_idx_dly_ret")) \
            .groupBy("trgt_fund_key", "cal.day_key", "wgt_type") \
            .agg(F.expr("sum(tgt_fund_dly_ret)").alias("tgt_fund_dly_ret"),
                 F.expr("sum(tgt_idx_dly_ret)").alias("tgt_idx_dly_ret")) \
            .select("trgt_fund_key", "cal.day_key", "wgt_type", "tgt_fund_dly_ret", "tgt_idx_dly_ret")

        df_union_index = df_index.withColumn("columnNo", F.lit(1)).union(df_index.withColumn("columnNo", F.lit(2)))\
            .alias("cursor")

        df_union_index = df_union_index\
            .withColumn("t_recType",
                        F.when((F.col("cursor.wgt_type") == 'FIRM') & (F.col("cursor.columnNo") == 1), F.lit('RFWT')).\
                        otherwise(F.when((F.col("cursor.wgt_type") == 'MODEL') & (F.col("cursor.columnNo") == 1),
                                         F.lit('RFWM')).\
                                  otherwise(F.when((F.col("cursor.wgt_type") == 'FIRM') & (F.col("cursor.columnNo") == 2),
                                                   F.lit('RBWT')).
                                            otherwise(F.lit('RBWM'))))). \
            withColumn("t_dly_ret", F.when((F.col("cursor.wgt_type") == 'FIRM') & (F.col("cursor.columnNo") == 1),
                                           F.col('cursor.tgt_fund_dly_ret')).\
                       otherwise(F.when((F.col("cursor.wgt_type") == 'MODEL') & (F.col("cursor.columnNo") == 1),
                                        F.col('cursor.tgt_fund_dly_ret'))\
                                 .otherwise(F.when((F.col("cursor.wgt_type") == 'FIRM') & (F.col("cursor.columnNo") == 2),
                                                   F.col('cursor.tgt_idx_dly_ret')).
                                            otherwise(F.col('cursor.tgt_idx_dly_ret'))))). \
            join(inputs["tpt"], [F.col("tpt.trgt_perf_type") == F.col("t_recType")])

        last_bus_day = inputs["cal"].where(F.col("cal_day") <= F.lit(p_wi_date)) \
            .selectExpr("max(cal_day) as t_last_bus_day").rdd.max()[0]

        t_prev_bus_day = inputs["prev_twi"].join(inputs["cal"], [F.col("prev_twi.DAY_KEY") == F.col("CAL.DAY_KEY")]). \
            where(F.col("cal_day") < F.lit(last_bus_day)) \
            .groupBy(F.col("prev_twi.trgt_perf_type_key")) \
            .agg(F.expr("max(cal_day)").alias("max_cal_day")).alias("tpbd")

        df_out_index = df_union_index.join(t_prev_bus_day, [F.col("tpt.trgt_perf_type_key") == F.col("tpbd.trgt_perf_type_key")]). \
            join(inputs["cal"], [F.col("cal.cal_day") == F.col("tpbd.max_cal_day")]). \
            join(inputs["prev_twi"], [F.col("prev_twi.trgt_perf_type_key") == F.col("tpt.trgt_perf_type_key"),
                            F.col("prev_twi.day_key") == F.col("cal.day_key"),
                            F.col("prev_twi.fund_key") == F.col("trgt_fund_key")]). \
            withColumn("t_new_wi_rfwt", F.lit(1) * F.col("prev_twi.wlth_idx").cast("double") * (F.lit(1) + F.col("t_dly_ret").cast("double"))). \
            where(F.col("t_new_wi_rfwt").isNotNull()). \
            selectExpr("tpt.trgt_perf_type_key as  trgt_perf_type_key", "cursor.day_key as day_key",
                       "cursor.trgt_fund_key as fund_key", "t_new_wi_rfwt as wlth_idx",
                       "cursor.tgt_fund_dly_ret as daily_ret")

        # load gp_target_wealth_index

        df_joined_2=df_joined.join(inputs["tog"], [F.col("tog.fund_key") == F.col("f.fund_key")]) \
            .join(inputs["tf"], [F.col("tog.trgt_fund_key") == F.col("tf.fund_key")]) \
            .join(inputs["fr"], [F.col("f.fund_key") == F.col("fr.fund_key"), \
                                                  F.col("cal.day_key") == F.col("fr.day_key"),
                                                  F.col("rp.per_key") == F.col("fr.per_key")])
        df_gp_index = df_joined_2.where(
            (F.col("tog.efftv_strt_dt") <= F.lit(p_wi_date)) & (F.col("tog.efftv_end_dt") >= F.lit(p_wi_date))) \
            .where(F.col("cal.cal_day") == F.lit(p_wi_date)) \
            .where((F.col("tf.fund_stat_cd").isin(1, 5) | ((F.col("tf.fund_incpn_dt") <= F.lit(p_wi_date))
                                                           & (F.col("tf.fund_clos_dt") >= F.lit(p_wi_date))))) \
            .select("trgt_fund_key", "cal.day_key",F.expr("fund_ret * gp_wgt").alias("tgt_fund_dly_ret"),F.expr("idx_ret * gp_wgt").alias("tgt_idx_dly_ret")) \
            .groupBy("trgt_fund_key", "cal.day_key")\
            .agg(F.expr("sum(tgt_fund_dly_ret)").alias("tgt_fund_dly_ret"),F.expr("sum(tgt_idx_dly_ret)").alias("tgt_idx_dly_ret")) \
            .select("trgt_fund_key", "cal.day_key", "tgt_fund_dly_ret", "tgt_idx_dly_ret")

        df_union_gp_index = df_gp_index.withColumn("columnNo", F.lit(1))\
            .union(df_gp_index.withColumn("columnNo", F.lit(2))).alias("cursor")

        prev_bus_day = inputs["cal"].where(F.col("cal_day") < F.lit(p_wi_date)) \
            .selectExpr("max(cal_day) as t_last_bus_day").rdd.max()[0]

        bus_day_flg = inputs["cal"].where(F.col("cal_day") == F.lit(prev_bus_day))\
            .select("bus_day_flg").rdd.collect()[0].bus_day_flg

        pre_day_key = inputs["cal"].where(F.col("cal_day") == F.lit(prev_bus_day))\
            .select("day_key").rdd.collect()[0].day_key

        t_prev_bus_day1 = inputs["prev_twi"].join(inputs["cal"], [F.col("prev_twi.DAY_KEY") == F.col("CAL.DAY_KEY")]). \
            where(F.col("cal_day") < F.lit(prev_bus_day)) \
            .groupBy(F.col("prev_twi.trgt_perf_type_key")) \
            .agg(F.expr("max(cal_day)").alias("max_cal_day")).alias("tpbd")

        df_out_gp_index = df_union_gp_index.withColumn("t_recType", F.when(F.col("columnNo") == 1, F.lit("RFOG"))
                                                       .otherwise(F.lit("RBOG"))). \
            withColumn("t_dly_ret", F.when(F.col("columnNo") == 1, F.col("tgt_fund_dly_ret")).
                       otherwise(F.col("tgt_idx_dly_ret"))). \
            join(inputs["tpt"], [F.col("tpt.trgt_perf_type") == F.col("t_recType")]) \
            .join(t_prev_bus_day1, [F.col("tpt.trgt_perf_type_key") == F.col("tpbd.trgt_perf_type_key")]). \
            join(inputs["cal"], [F.col("cal.cal_day") == F.col("tpbd.max_cal_day")]). \
            join(inputs["prev_twi"], [F.col("prev_twi.trgt_perf_type_key") == F.col("tpt.trgt_perf_type_key"),
                            F.col("prev_twi.day_key") == (F.when(F.lit(bus_day_flg) == 'Y', F.lit(pre_day_key)).
                                                          otherwise(F.col("cal.day_key"))),
                            F.col("prev_twi.fund_key") == F.col("trgt_fund_key")]). \
            withColumn("t_new_wi_rfwt", F.lit(1) * F.col("prev_twi.wlth_idx").cast("double") *
                       (F.lit(1) + F.col("t_dly_ret").cast("double"))). \
            where(F.col("t_new_wi_rfwt").isNotNull()). \
            selectExpr("tpt.trgt_perf_type_key as trgt_perf_type_key", "cursor.day_key as day_key",
                       "cursor.trgt_fund_key as fund_key", "t_new_wi_rfwt as wlth_idx", "tgt_fund_dly_ret as daily_ret")

        df_wlth_index = df_out_index.union(df_out_gp_index).alias("output")

        return df_wlth_index
