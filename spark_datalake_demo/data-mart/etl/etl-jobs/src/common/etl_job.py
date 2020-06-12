from functools import reduce
from typing import Dict, List, Any, Set
from datetime import datetime
import pkg_resources
import pyspark.sql
import common.utils
import common.parsers
import os, glob
import pyspark.sql.functions as F
import pyspark.sql.types as T
import importlib
import logging
import pkgutil
import jobs

class ETLJob:
    class DataClassification:
        PII:str = "pii"
        CONFIDENTIAL:str = "confidential"
        NONSENSITIVE:str = "nonsensitive"
    """
    Attributes
    ----------
    sources : dict
        Keys are the aliases
        Example:
            "input-file-1":
            {
                "type": "table/file/dimension" # if table, taken from datamart snapshot repository, if file from the raw folder. if 'dimension' taken from metadata folder
                "delimiter": ",",
                "path": "myfile_[0-9]{8}" # regexp of path. [0-9]{8} find file with yyyyMMdd suffix. relative path (no heading /)
                "skip_header_rows": 5 # num rows to skip, default 0
                "skip_footer_rows": 1 # num rows to skip, default 0
                "format": "csv" / "cobol" / "custom" # default = csv
                "copybook": "name of file" # name of copybook file. placed under metadata/copybooks. applicable if cobol format
            }
    target_table: name of the datamart target table
    business_key: list of business key(s) to use for primary file
    primary_key: list of primary key(s) and their types to be used for upsert
    business_key_props: dictionary of properties for business keys. Currently supports: 
    - case_sensitive: True (default) / False
        Example:
        { "bkey1": {
            case_sensitive: False
        }}
    """
    sources:Dict[str,Dict[str,str]] = {}
    target_table = "tbl"
    joins:List[Dict[str,Any]] = []
    target_mappings:List[Dict[str,Any]] = []
    business_key:List[str] = ["bk"]
    business_key_props:Dict[str,Dict[str,Any]] = {}
    primary_key:Dict[str,str] = {"PK": "int"}

    # metadata
    data_classification:str = DataClassification.NONSENSITIVE
    trigger_on_file_arrival:bool = False
    processed_files_retention_period:int = -1 # in days. -1=infinite
    _processed_files:Set[str] = set()
    _args:Dict[str,str] = {}

    def __init__(self,spark,env,logger,args:Dict[str,str]={}):
        self._spark = spark # spark context
        self._env = env # environment definition
        self._logger = logger 
        self._timestamp:datetime = datetime.now()
        self._args = args

    """Returns the timestamp for keeping track of processing. Will be used in upsert
    """
    def get_timestamp(self) -> datetime:
        return self._timestamp

    def run(self):
        self._logger.info("running")
        # load the input sources
        inputs:Dict[str,pyspark.sql.DataFrame] = self.extract(self._env["catalog"])
        # join the dataframe
        df_joined:pyspark.sql.DataFrame = self.join(inputs)
        # transform to target structure
        df_target:pyspark.sql.DataFrame = self.transform(df_joined)
        # load
        self.load(df_target)
        

    def extract(self,catalog:Dict[str,Any]) -> Dict[str,pyspark.sql.DataFrame]:
        """Extracts the files for this job.
        The default implementation uses the inputs dict structure:
        - Files are loaded from the staging directory
        - Tables are loaded from the data-lake repository
        More complex jobs should override this method (e.g. VSAM files)
        Parameters
        ----------
        Returns
        -------
        dict
            a dict where the keys are aliases of the dataframe and the values are DataFrameReaders
        """
        self._logger.info("extract start")
        inputs:Dict[str,pyspark.sql.DataFrame] = {}
        for alias,properties in self.sources.items():
            #
            # load each source
            #
            if properties["type"] == "file":
                # get the entry from the catalog
                if properties["source"] not in catalog:
                    raise ValueError(f"{properties['source']} not found in catalog")

                source:Dict[Any,Any] = catalog[properties["source"]]
                file_locations, all_files = common.utils.get_file_locations(
                    self._env["file_prefix"],
                    source["path"],
                    limit=properties.get("limit",1),
                    sort=properties.get("sort",'last_modified'),
                    ascending=properties.get("ascending",True)
                )

                self._logger.debug("loading %s" % file_locations)
                self._processed_files.update(all_files) # type: ignore
                # custom
                if source["format"] == "custom":
                    continue
                # parse text
                if (source["format"] == "txt"):
                    df_input_segments = []
                    for file_location in file_locations:
                        raw = self._spark.sparkContext.textFile(file_location)
                        footer_line = source.get("skip_footer_rows", 0)
                        if (int(source.get("skip_header_rows", 0)) > 0 or
                                int(source.get("skip_footer_rows", 0)) > 0):
                            rdd = raw.zipWithIndex()\
                                .filter(lambda line_index: line_index[1] >= int(source.get("skip_header_rows", 0)))
                            if int(source.get("skip_footer_rows",0)) > 0:
                                line_count = rdd.count()-1
                                rdd = rdd\
                                    .filter(lambda line_index: line_index[1] <= line_count-footer_line)
                        rdd = rdd.map(lambda row: row[0])

                        reader = rdd.map(lambda row: row.split(source.get("delimiter", ",")))
                        # parse columns
                        l = []
                        for column, metadata in source.get("columns", {}).items():
                            pos = "_" + str(metadata["position"])
                            l.append(pos)

                        reader_cols = reader.toDF().select(l).collect()
                        fields = []
                        for column, coltype in source.get("columns", {}).items():
                            if coltype == 'Integer':
                                Field = T.StructField(column, T.IntegerType())
                            elif coltype == 'Date':
                                Field = T.StructField(column, T.DateType())
                            elif coltype == 'Double':
                                Field = T.StructField(column, T.DoubleType())
                            else:
                                Field = T.StructField(column, T.StringType())
                            fields.append(Field)
                            schema = T.StructType(fields)
                        df_input_segment = self._spark.createDataFrame(reader_cols, schema)
                    df_input_segments.append(df_input_segment)
                # parse CSV
                if (source["format"]=="csv"):
                    df_input_segments = []
                    for file_location in file_locations:
                        # TODO enhance conf to support all options
                        reader = self._spark.read\
                            .option("inferSchema", "true")\
                            .option("header", source.get("header",True))\
                            .option("quote", "\"")\
                            .option("escape", "\"")\
                            .option("multiLine", "true")\
                            .option("mode","DROPMALFORMED")\
                            .option("ignoreTrailingWhiteSpace", True)\
                            .option("ignoreLeadingWhiteSpace", True)\
                            .option("delimiter",source.get("delimiter",","))
                        if (int(source.get("skip_header_rows",0))>0 or
                            int(source.get("skip_footer_rows",0))>0):
                            df_input_segment = common.parsers.read_csv_remove_header_footer(
                                self._spark,
                                file_location,
                                reader,
                                source.get("skip_header_rows",0),
                                source.get("skip_footer_rows",0)
                            )
                        else:
                            df_input_segment = reader.csv(file_location)
                        # if we didn't get a header, take it from the metadata and rename the columns
                        if not source.get("header",True):
                            df_input_segment = df_input_segment.toDF(*source.get("columns",{}).keys())
                        # drop records that are completely null
                        df_input_segments.append(df_input_segment)

                elif source["format"]=="cobol":
                    df_input_segments = []
                    for file_location in file_locations:
                        df_input = common.parsers.read_cobol_file(
                            self._spark,
                            file_location,
                            copybook_location=source.get("copybook",None),
                            row_prefix=source.get("row_prefix",None), # if multiline, specify start of new row
                            multiline=source.get("multiline",False), # if has a row prefix this is multiline file
                            record_selector_field=source.get("record_selector_field",None),
                            record_types=source.get("record_types",None),
                            header_lines=source.get("skip_header_rows",0),
                            footer_lines=source.get("skip_footer_rows",0),
                            use_header=source.get("skip_header",False),
                            trim=source.get("trim",False)
                        )
                        df_input_segments.append(df_input)

                # reduce the input segments of multiple files to a single dataframe
                df_input = reduce(pyspark.sql.DataFrame.unionAll, df_input_segments)
                    
                # parse any columns
                for column,metadata in source.get("columns",{}).items():
                    if metadata["type"]=="date":
                        df_input = df_input.withColumn(
                            column,F.to_date(F.col(column).cast("string"),format=metadata["format"]))


            elif properties["type"]=="table":
                self._logger.debug(f"checking for existing table => {properties['source']}")
                try:
                    # read from the data mart snapshot mirror files
                    df_input = common.utils.read_table_snapshot(
                        table_name=properties["source"],
                        env=self._env,
                        spark=self._spark)
                except FileNotFoundError:
                    # create an empty data frame with dummy schema
                    self._logger.debug('existing table not found, creating an empty one')

                    # first, we import the job to read its target mappings
                    # for this, we traverse all jobs to find the one that populates this target table
                    found = False
                    for importer, modname, ispkg in pkgutil.walk_packages(path=jobs.__path__,prefix='jobs.'): # type: ignore
                        if not ispkg:
                            # find the job class
                            job_name = ".".join(modname.split(".")[1:-1]) # take the middle part of the job package (without prefix or suffix)
                            job_module = importlib.import_module("jobs.%s.job" % job_name)
                            job_class = getattr(job_module, "Job")
                            job_target_table = getattr(job_class,"target_table")

                            if job_target_table==properties["source"]:
                                found = True
                                break

                    if not found:
                        # there is no way to populate this table from source jobs
                        raise ValueError(f"table parquet for {properties['source']} not found and we can't find a job to populate its schema")

                    job_target_mappings:List[Dict[str,Any]] = getattr(job_class, "target_mappings")
                    # create schema for empty dataframe by reading the target mappings and business keys
                    metadata_columns = [
                        T.StructField("row_strt_dttm",T.TimestampType()),
                        T.StructField("row_stop_dttm",T.TimestampType()),
                        T.StructField("curr_row_flg",T.StringType())
                    ]
                    schema = T.StructType([T.StructField(mapping["target"],T.StringType()) for mapping in job_target_mappings]+metadata_columns)
                    # add primary key
                    for colname,coltype in job_class.primary_key.items():
                        if not colname in map(lambda x: x["target"],job_target_mappings):
                            schema.add(colname,T.IntegerType()) 

                    df_input = self._spark.createDataFrame(self._spark.sparkContext.emptyRDD(),schema)

            elif properties["type"]=="dimension":
                # this is an internal 'dimension' table. load as csv from metadata folder
                file_location = pkg_resources.resource_filename("metadata.dimension_tables",f"{properties['source'].lower()}.csv")
                # load into an RDD
                reader = self._spark.read\
                    .option("inferSchema", "true")\
                    .option("header", True)\
                    .option("quote", "\"")\
                    .option("escape", "\"")\
                    .option("multiLine", "true")\
                    .option("ignoreTrailingWhiteSpace", True)\
                    .option("delimiter",",")
                df_input = reader.csv(file_location)

            inputs[alias] =  df_input.alias(alias)

        self._logger.debug("extract done")

        return inputs
        
    def join(self,inputs:Dict[str,pyspark.sql.DataFrameReader]) -> pyspark.sql.DataFrame:
        """
        Joins the dataframes to create one long dataframe.
        Column names will be aliases according to the keys of the inputs dict

        Parameters
        ----------
        inputs
            a dict where the keys are aliases of the dataframe and the values are DataFrameReaders

        Raises
        ------
        ValueError
            If the dataframes can not be joined correctly

        Returns
        -------
        DataFrame
            a dataframe of the joined inputs
        """
        self._logger.debug("join: start")

        # if we have no joins, return the input frame. 
        if len(self.joins)==0:
            return list(inputs.values())[0]

        # set base dataframe
        source_alias:str = self.joins[0]["source"]
        df_joined:pyspark.sql.DataFrame = inputs[source_alias]
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("join: total records in df %s: %s" % (source_alias,df_joined.count()) )
        # loop over join conditions and join dfs
        for join_op in self.joins[1:]:
            df_joined = df_joined.join(inputs[join_op["source"]],
                                        join_op.get("conditions"),
                                        how=join_op.get("type","inner")
            )
            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug("join: total records in df after join with %s: %s" % (join_op["source"],df_joined.count()))

        self._logger.debug("join: done")
        return df_joined

    def transform(self,df_joined:pyspark.sql.DataFrame) -> pyspark.sql.DataFrame:
        """Transform the joined dataframe and return the target dataframe to be loaded into the DB

        Parameters
        ----------
        inputs
            a dataframe of the joined inputs

        Raises
        ------

        Returns
        -------
        DataFrame
            a dataframe in the format of the target table
        """
        self._logger.info("transform start")
        columns = [mapping["source"].alias(mapping.get("target")) for mapping in self.target_mappings]
        df_target = df_joined.select(columns)
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("target schema of df")
            self._logger.debug(df_target.printSchema())
        self._logger.info("transform done")
        return df_target

    def load(self,df_target):
        """Load the new dataframe into the datamart and update datalake structures
        Default implementation performs the following:
        - Upsert into target table in DB
        - Write type2 history
        - Updates datalake repository mirror table

        Parameters
        ----------
        inputs
            a dataframe in the format of the target table

        Raises
        ------

        Returns
        -------
        """
        self._logger.info("load start")
        # load existing file from snapshot data store
        self._logger.info("loading existing table from datamart snapshot")
        try:
            df_existing:pyspark.sql.DataFrame = common.utils.read_table_snapshot(
                self.target_table,
                self._env,
                self._spark)
        except FileNotFoundError:
            self._logger.info("datamart snapshot does not exist. use empty data frame")
            df_existing = self._spark.createDataFrame([], df_target.schema)
            if (set(self.business_key)!=set(self.primary_key.keys())):
                # we need to add the primary key since the source table doesn't include it
                for primary_key_col,primary_key_type in self.primary_key.items():
                    df_existing = df_existing.withColumn(primary_key_col,F.lit(None).cast(primary_key_type))

        self._logger.info("identifying delta")
        # find deltas

        df_new,df_updated = common.utils.find_delta(
            df_existing,
            df_target,
            business_key=self.business_key,
            primary_key=self.primary_key,
            business_key_props=self.business_key_props)

        # logging
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("load: total rows to insert: %s" % df_new.count())
            self._logger.debug("load: total rows to update: %s" % df_updated.count())
        self._logger.info("updating datamart snapshot")

        # add autoincrement primary key for new records
        if (set(self.business_key)!=set(self.primary_key.keys())):
            # validate that this is a single column
            if (len(self.primary_key)!=1):
                raise ValueError("can't add autoincrement to complex primary key with more than one column: %s" % ",".join(self.primary_key))
            df_new = common.utils.fill_auto_increment(df_existing,df_new,list(self.primary_key.keys())[0])

        if (df_new.count()>0 or df_updated.count()>0):
            # upsert to db
            common.utils.upsert(self._spark,self._env,self.target_table,
                list(self.primary_key.keys()),df_new,df_updated,self._timestamp,self._logger)

        # we write the table snapshot even if we have no updates so we create an empty parquet the first time
        # update datamart snapshot
        table_tags = {
            'hca:dataclassification': self.data_classification,
            'hca:target_table': self.target_table,
        }
        common.utils.write_table_snapshot(common.utils.align_and_union(df_new,df_updated),
            self.target_table,
            self.primary_key,
            self._env,
            self._spark,
            self._logger,
            table_tags)
        # TODO: update type2 history

        self._logger.info("load done")

    def archive(self, archive_prefix:str):
        """Archive raw files into timestamped archive folder
        - copy job input files from raw to archive with timestamp folders
        - tag archive files

        Parameters
        ----------
          inputs
            archive prefix to move raw files

        Raises
        ------

        Returns
        -------
        """
        self._logger.info("archive start")

        archive_path = os.path.join(archive_prefix, self._timestamp.strftime('%Y/%m-%B/%Y%m%d_%H%M%S'))
        
        common.utils.s3_archive_raw_files(list(self._processed_files), archive_path)

        self._logger.info("archive done")
