from snowflake.snowpark import Session
from snowflake.core import Root, CreateMode
from snowflake.core.schema import Schema
from snowflake.snowpark.functions import lit, col

# Disable warnings from model registry when model from model registry is loaded into notebook
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

def setup_demo(session: Session):
    # Setting up data for demo
    database = session.get_current_database()
    root = Root(session)
    root.databases[database].schemas.create(schema=Schema(name="RETAIL_DATA"), mode=CreateMode.or_replace)
    root.databases[database].schemas.create(schema=Schema(name="FEATURE_STORE"), mode=CreateMode.or_replace)
    root.databases[database].schemas.create(schema=Schema(name="MODEL_REGISTRY"), mode=CreateMode.or_replace)
    session.table(f'{database}._DATA_GENERATION._TRANSACTIONS').filter(col('DATE') <= lit('2024-04-30')).write.save_as_table(table_name=f'{database}.RETAIL_DATA.TRANSACTIONS', mode='overwrite')
    session.table(f'{database}._DATA_GENERATION._CUSTOMERS').write.save_as_table(f'{database}.RETAIL_DATA.CUSTOMERS')
    print('Setup finished.')