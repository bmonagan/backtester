import pyarrow.parquet as pq


data_source = "data/AAPL_1d.parquet"
schema = pq.read_schema(data_source)   # or whatever your path variable is
print(schema.names)

# output ['Close', 'High', 'Low', 'Open', 'Volume', 'Date'] 
