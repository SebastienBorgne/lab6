from api_service import BirdApiService
from db_service import insert_data



if __name__ == "__main__":
    service = BirdApiService()
    raw = service.extract_data()
    dataframe = service.transform_data(raw)
    written = insert_data(dataframe)
    print(f"Processed {len(dataframe)} bird observations; wrote {written} rows to Cassandra.")