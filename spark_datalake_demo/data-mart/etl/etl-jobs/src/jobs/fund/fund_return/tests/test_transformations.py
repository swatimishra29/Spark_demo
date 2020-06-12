from pyspark.sql.types import *
import pandas as pd
from datetime import datetime
from pyspark.sql import SparkSession
import logging
import os
import common.pytest_utils
import pyspark.sql.functions as F
import pyspark.sql.types as T


def test_first_day_weekday(request, tmpdir):
    #
    # set up spark
    #
    spark = SparkSession \
        .builder \
        .appName("Python Spark SQL basic example") \
        .getOrCreate()
    # spark.sparkContext.addFile('./common',recursive=True)
    env = {
        "file_prefix": os.path.join(request.fspath.dirname, "data"),
        # use parquet files at the job level
        "folders": {
            "datamart": os.path.join(request.fspath.dirname, "data", "datamart")
        },
    }
    logging.basicConfig()
    logger = logging.getLogger("test_fund_return")

    import jobs.fund.fund_return.job
    job = jobs.fund.fund_return.job.Job(spark, env, logger)
    # load csv file
    df_test = common.pytest_utils.load_test_csv(spark, os.path.join(request.fspath.dirname, "data", "test_fund_return.csv"))
    # cast columns
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="per_msr", col_type="int", alias="tbl_per")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="day_key", col_type="int")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="fund_key", col_type="int", alias="tbl_fund")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="t_annl", col_type="double")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="t_annl", col_type="double", alias="expected")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="t_asof_ret", col_type="double", alias="expected")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="t_return", col_type="double", alias="expected")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="fund_incpn_dt", col_type='timestamp', alias="tbl_fund", date_format="MM/dd/yyyy")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="sba_incpn_dt_t", col_type='timestamp', alias="tbl_fund", date_format="MM/dd/yyyy")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="return_date", col_type='timestamp', date_format="MM/dd/yyyy")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="t_gen_incpn_dt", col_type='timestamp', date_format="MM/dd/yyyy")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="t_gen_incpn_dt", col_type='timestamp', alias="expected", date_format="MM/dd/yyyy")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="t_beg_dt", col_type='timestamp', date_format="MM/dd/yyyy")
    df_test = common.pytest_utils.cast_nested_col(df_test, col_name="t_beg_dt", col_type='timestamp', alias="expected", date_format="MM/dd/yyyy")

    df_result = job.calc_transformed(df_test)
    # columns to test:

    common.pytest_utils.assert_df_matches_expected(df_result, column_name="t_annl", precision=1e-8)
    common.pytest_utils.assert_df_matches_expected(df_result, column_name="t_gen_incpn_dt", column_type="timestamp", precision=1e-12)
    common.pytest_utils.assert_df_matches_expected(df_result, column_name="t_beg_dt", column_type="timestamp", precision=1e-12)
    common.pytest_utils.assert_df_matches_expected(df_result, "t_asof_ret", precision=1e-12)
    common.pytest_utils.assert_df_matches_expected(df_result, "t_return", precision=1e-12)
