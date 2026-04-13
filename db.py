from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["studyplanner"]

users = db["users"]
marks = db["marks"]
plans = db["plans"]
tasks = db["tasks"]